"""Unit tests voor ollama_client: _build_chat_prompt, _ollama_request, analyze_document, generate_question, chat_stream."""
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

import ollama_client


def test_prompt_bevat_kennisbank_en_vraag():
    prompt = ollama_client._build_chat_prompt(
        message="Wat is de proeftijd?",
        history=[],
        knowledge_chunks="[Proeftijd | Bron: contract.docx]\nV: ...\nA: twee maanden",
    )
    assert "KENNISBANK" in prompt
    assert "Wat is de proeftijd?" in prompt
    assert "ANTWOORD" in prompt
    assert "twee maanden" in prompt


def test_prompt_geen_vorige_context_zonder_history():
    prompt = ollama_client._build_chat_prompt(
        message="vraag",
        history=[],
        knowledge_chunks="kennis",
    )
    assert "Vorige context" not in prompt


def test_prompt_filtert_geen_antwoord_uit_history():
    history = [
        {"role": "user", "content": "Vraag 1"},
        {"role": "assistant", "content": "Ik kan geen antwoord geven op deze vraag"},
        {"role": "user", "content": "Vraag 2"},
        {"role": "assistant", "content": "De proeftijd is twee maanden"},
    ]
    prompt = ollama_client._build_chat_prompt(
        message="Nieuwe vraag",
        history=history,
        knowledge_chunks="kennis",
    )
    assert "Ik kan geen antwoord geven" not in prompt
    assert "De proeftijd is twee maanden" in prompt


def test_prompt_filtert_niet_relevant_uit_history():
    history = [
        {"role": "user", "content": "Vraag"},
        {"role": "assistant", "content": "Er is geen relevante informatie beschikbaar"},
    ]
    prompt = ollama_client._build_chat_prompt(
        message="Nieuwe vraag",
        history=history,
        knowledge_chunks="kennis",
    )
    assert "geen relevante informatie" not in prompt


def test_prompt_trunceert_kennisbank_op_6000_tekens():
    lange_kennis = "k" * 7000
    prompt = ollama_client._build_chat_prompt(
        message="vraag",
        history=[],
        knowledge_chunks=lange_kennis,
    )
    kennis_in_prompt = "k" * 6000
    assert kennis_in_prompt in prompt
    assert "k" * 6001 not in prompt


def test_prompt_behoudt_geslaagde_history():
    history = [
        {"role": "user", "content": "Wat is een NDA?"},
        {"role": "assistant", "content": "Een NDA is een geheimhoudingsovereenkomst"},
    ]
    prompt = ollama_client._build_chat_prompt(
        message="En wat staat er in?",
        history=history,
        knowledge_chunks="kennis",
    )
    assert "Vorige context" in prompt
    assert "Een NDA is een geheimhoudingsovereenkomst" in prompt


# ── _strip_markdown ─────────────────────────────────────────────────────────


def test_strip_markdown_verwijdert_code_fences():
    raw = "```json\n{\"key\": \"value\"}\n```"
    result = ollama_client._strip_markdown(raw)
    assert result == '{"key": "value"}'


def test_strip_markdown_geen_fences():
    raw = '{"key": "value"}'
    result = ollama_client._strip_markdown(raw)
    assert result == '{"key": "value"}'


def test_strip_markdown_fences_zonder_json_prefix():
    raw = "```\n{\"key\": \"value\"}\n```"
    result = ollama_client._strip_markdown(raw)
    assert '{"key": "value"}' in result


# ── _ollama_request ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ollama_request_succes():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"response": "Antwoord van Ollama"}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await ollama_client._ollama_request("test prompt")

    assert result == "Antwoord van Ollama"


@pytest.mark.asyncio
async def test_ollama_request_connect_error():
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("geen verbinding"))

    with patch("httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(RuntimeError, match="Ollama"):
            await ollama_client._ollama_request("test")


# ── analyze_document ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_analyze_document_valide_json():
    payload = {"contract_type": "NDA", "detected_topics": []}
    with patch.object(ollama_client, "_ollama_request", AsyncMock(return_value=json.dumps(payload))):
        result = await ollama_client.analyze_document("tekst", ["geheimhouding"])
    assert result["contract_type"] == "NDA"


@pytest.mark.asyncio
async def test_analyze_document_json_fout_geeft_fallback():
    with patch.object(ollama_client, "_ollama_request", AsyncMock(return_value="geen json")):
        result = await ollama_client.analyze_document("tekst", [])
    assert result["contract_type"] == "anders"
    assert result["detected_topics"] == []


@pytest.mark.asyncio
async def test_analyze_document_analyseert_hele_lange_tekst_in_segmenten():
    """Een lang contract wordt in segmenten geanalyseerd zodat ook clausules
    achterin het document gevonden worden."""
    lange_tekst = "\n".join(f"Artikel {i}: bepaling nummer {i}." for i in range(150))
    # Precies twee segmenten: langer dan één, korter dan twee volle segmenten
    assert ollama_client._SEGMENT_GROOTTE < len(lange_tekst) <= 2 * ollama_client._SEGMENT_GROOTTE

    antwoorden = [
        json.dumps({
            "contract_type": "NDA",
            "detected_topics": [{"topic": "looptijd_bepalen", "passage": "vooraan"}],
        }),
        json.dumps({
            "contract_type": "NDA",
            "detected_topics": [{"topic": "boeteclausule_bedrag", "passage": "achteraan"}],
        }),
    ]
    mock = AsyncMock(side_effect=antwoorden)
    with patch.object(ollama_client, "_ollama_request", mock):
        result = await ollama_client.analyze_document(
            lange_tekst, ["looptijd_bepalen", "boeteclausule_bedrag"]
        )

    assert mock.await_count == 2
    topics = {t["topic"] for t in result["detected_topics"]}
    assert topics == {"looptijd_bepalen", "boeteclausule_bedrag"}


@pytest.mark.asyncio
async def test_analyze_document_filtert_onbekende_topic_sleutels():
    """Topics die het model verzint (niet in de catalogus) worden genegeerd."""
    payload = json.dumps({
        "contract_type": "NDA",
        "detected_topics": [
            {"topic": "verzonnen_onderwerp", "passage": "iets"},
            {"topic": "looptijd_bepalen", "passage": "looptijd van twee jaar"},
        ],
    })
    with patch.object(ollama_client, "_ollama_request", AsyncMock(return_value=payload)):
        result = await ollama_client.analyze_document("tekst", ["looptijd_bepalen"])
    topics = [t["topic"] for t in result["detected_topics"]]
    assert topics == ["looptijd_bepalen"]


@pytest.mark.asyncio
async def test_analyze_document_eerste_vindplaats_wint_bij_dubbel_topic():
    lange_tekst = "\n".join(f"Regel {i} " + "x" * 30 for i in range(150))
    assert ollama_client._SEGMENT_GROOTTE < len(lange_tekst) <= 2 * ollama_client._SEGMENT_GROOTTE
    antwoorden = [
        json.dumps({
            "contract_type": "NDA",
            "detected_topics": [{"topic": "looptijd_bepalen", "passage": "eerste"}],
        }),
        json.dumps({
            "contract_type": "NDA",
            "detected_topics": [{"topic": "looptijd_bepalen", "passage": "tweede"}],
        }),
    ]
    with patch.object(ollama_client, "_ollama_request", AsyncMock(side_effect=antwoorden)):
        result = await ollama_client.analyze_document(lange_tekst, ["looptijd_bepalen"])
    assert result["detected_topics"] == [{"topic": "looptijd_bepalen", "passage": "eerste"}]


def test_segmenteer_knipt_op_regelgrenzen():
    tekst = "\n".join("regel " + "a" * 100 for _ in range(100))
    segmenten = ollama_client._segmenteer(tekst)
    assert len(segmenten) > 1
    for segment in segmenten:
        assert len(segment) <= (
            ollama_client._SEGMENT_GROOTTE + 107 + ollama_client._MIN_STAART
        )
        # geen halve regels: elke segment eindigt op een regelgrens
        assert segment.endswith("\n")
    assert "".join(segmenten) == tekst + "\n"


def test_segmenteer_plakt_korte_staart_aan_vorig_segment():
    """Een restje van een paar regels krijgt geen eigen Ollama-aanroep."""
    tekst = "a" * 3400 + "\n" + "staartje"
    segmenten = ollama_client._segmenteer(tekst)
    assert len(segmenten) == 1
    assert "staartje" in segmenten[0]


@pytest.mark.asyncio
async def test_analyze_document_corrigeert_typefout_in_topic_sleutel():
    """'onslaggronden' (typefout van het model) telt gewoon als 'ontslaggronden'."""
    payload = json.dumps({
        "contract_type": "arbeidscontract",
        "detected_topics": [{"topic": "onslaggronden", "passage": "opzegging conform wet"}],
    })
    with patch.object(ollama_client, "_ollama_request", AsyncMock(return_value=payload)):
        result = await ollama_client.analyze_document(
            "tekst", ["ontslaggronden", "loon_bepalen"]
        )
    assert [t["topic"] for t in result["detected_topics"]] == ["ontslaggronden"]


@pytest.mark.asyncio
async def test_analyze_document_filtert_lege_passages():
    """Topics zonder letterlijke passage worden weggelaten — daar valt geen
    gegronde vraag over te stellen."""
    payload = json.dumps({
        "contract_type": "NDA",
        "detected_topics": [
            {"topic": "looptijd_bepalen", "passage": ""},
            {"topic": "boeteclausule_bedrag", "passage": "  "},
            {"topic": "geheimhouding_scope", "passage": "Partijen houden alles geheim."},
        ],
    })
    with patch.object(ollama_client, "_ollama_request", AsyncMock(return_value=payload)):
        result = await ollama_client.analyze_document(
            "tekst", ["looptijd_bepalen", "boeteclausule_bedrag", "geheimhouding_scope"]
        )
    assert [t["topic"] for t in result["detected_topics"]] == ["geheimhouding_scope"]


# ── generate_question ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_question_valide_json():
    payload = {"question": "Wat is de looptijd?"}
    with patch.object(ollama_client, "_ollama_request", AsyncMock(return_value=json.dumps(payload))):
        result = await ollama_client.generate_question("NDA", "passage", "Looptijd", [])
    assert result["question"] == "Wat is de looptijd?"


@pytest.mark.asyncio
async def test_generate_question_json_fout_geeft_fallback():
    with patch.object(ollama_client, "_ollama_request", AsyncMock(return_value="kapot")):
        result = await ollama_client.generate_question("NDA", "passage", "Looptijd", ["Vraag 1"])
    assert "Looptijd" in result["question"]


# ── chat_stream ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_chat_stream_yield_tokens():
    lines = [
        json.dumps({"response": "Hallo", "done": False}),
        json.dumps({"response": " wereld", "done": False}),
        json.dumps({"response": "", "done": True}),
    ]

    async def fake_aiter_lines():
        for line in lines:
            yield line

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.aiter_lines = fake_aiter_lines
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.stream = MagicMock(return_value=mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_client):
        tokens = []
        async for token in ollama_client.chat_stream("vraag", [], "kennis"):
            tokens.append(token)

    assert tokens == ["Hallo", " wereld"]


@pytest.mark.asyncio
async def test_chat_stream_sla_slechte_json_over():
    lines = [
        "GEEN_JSON",
        json.dumps({"response": "Token", "done": True}),
    ]

    async def fake_aiter_lines():
        for line in lines:
            yield line

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.aiter_lines = fake_aiter_lines
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.stream = MagicMock(return_value=mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_client):
        tokens = []
        async for token in ollama_client.chat_stream("vraag", [], "kennis"):
            tokens.append(token)

    assert tokens == ["Token"]


@pytest.mark.asyncio
async def test_chat_stream_connect_error():
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.stream = MagicMock(side_effect=httpx.ConnectError("geen verbinding"))

    with patch("httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(RuntimeError, match="Ollama"):
            async for _ in ollama_client.chat_stream("vraag", [], "kennis"):
                pass


@pytest.mark.asyncio
async def test_chat_stream_timeout_error():
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.stream = MagicMock(side_effect=httpx.TimeoutException("timeout"))

    with patch("httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(RuntimeError, match="verbindingsfout"):
            async for _ in ollama_client.chat_stream("vraag", [], "kennis"):
                pass
