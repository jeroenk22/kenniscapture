"""Ollama LLM client voor Kenniscapture."""

import difflib
import json
import logging
import os
from collections.abc import AsyncGenerator

import httpx

_log = logging.getLogger("app.ollama")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

ANALYSE_PROMPT = """Je analyseert een (deel van een) contract voor een contractspecialist.
Geef ALLEEN een JSON response terug, geen uitleg of markdown.

Contract tekst:
{contract_text}

Bekende onderwerpen (gebruik EXACT deze sleutels): {topics_list}

Instructies:
- Loop ALLE bekende onderwerpen één voor één langs en controleer of er in de
  tekst hierboven een clausule of passage over staat.
- Neem ALLEEN onderwerpen op die daadwerkelijk in de tekst voorkomen.
  Onderwerpen zonder passage laat je VOLLEDIG WEG uit de lijst — geen
  lege passages.
- "passage" moet een LETTERLIJK citaat uit de tekst zijn (max 200 tekens).
  Kies het citaat met de concrete keuze: bedragen, termijnen, percentages of
  voorwaarden. Verzin GEEN passages en parafraseer NIET.
- Verzin GEEN onderwerpen die niet in de lijst staan.

Geef terug:
{{
  "contract_type": "NDA|arbeidscontract|leverancier|anders",
  "detected_topics": [
    {{
      "topic": "topic_sleutel_uit_de_lijst",
      "passage": "het exacte stukje tekst uit het contract (max 200 chars)"
    }}
  ]
}}"""

QUESTION_PROMPT = """Je helpt bij het vastleggen van kennis van een contractspecialist.
Geef ALLEEN een JSON response terug, geen uitleg.

Context:
- Contracttype: {contract_type}
- Gevonden passage: "{passage}"
- Onderwerp: {topic_label}
- Al gestelde vragen over dit onderwerp: {asked_questions}

Genereer een concrete vraag die vraagt naar de WAAROM achter de passage.
De vraag moet:
- De concrete keuze uit de passage benoemen (het bedrag, de termijn, de
  voorwaarde die er LETTERLIJK staat) en vragen waarom daarvoor gekozen is,
  welke afwegingen er speelden en wanneer je hiervan zou afwijken
- Vragen naar beslislogica, niet naar feiten die al in de passage staan
- Een open vraag zijn (geen ja/nee-vraag)
- Duidelijk anders zijn dan de al gestelde vragen hierboven
- Kort zijn (max 2 zinnen)
- In het Nederlands zijn

BELANGRIJK: Doe GEEN aannames over de inhoud van het contract die niet
letterlijk uit de passage blijken. Verzin geen clausules, bedragen of
voorwaarden die niet gegeven zijn.

Geef terug:
{{
  "question": "de vraag"
}}"""

CHAT_PROMPT = """Je bent een assistent die uitsluitend antwoordt op basis van de KENNISBANK hieronder.
De kennisbank bevat vraag-en-antwoord paren van een contractspecialist.

STRIKTE REGELS — NOOIT overtreden:
1. Gebruik ALLEEN informatie die letterlijk in de kennisbank staat. Verzin NIETS en doe GEEN aannames.
2. Voeg GEEN algemene kennis, eigen juridische interpretatie of niet-onderbouwde aanvullingen toe.
3. Geef een UITGEBREID en volledig antwoord: gebruik ALLE kennisbank-items die relevant zijn voor de vraag en benoem de vastgelegde beslislogica (het "waarom") van de specialist.
4. Als meerdere kennisbank-items relevant zijn, combineer ze dan tot één samenhangend antwoord.
5. Alleen als er ECHT niets relevants in de kennisbank staat, zeg dan letterlijk: "De kennisbank bevat hierover geen verdere informatie." — zonder bronvermelding en zonder verdere toelichting.
6. Citeer bij een inhoudelijk antwoord aan het einde de bron(nen): topic + documentnaam.
7. Antwoord in het Nederlands.

KENNISBANK:
{knowledge_chunks}

VRAAG: {user_question}

ANTWOORD (uitgebreid, maar alleen op basis van bovenstaande kennisbank):"""


async def _ollama_request(prompt: str, temperature: float = 0.1) -> str:
    """Stuur een prompt naar Ollama en geef de response terug."""
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"num_ctx": 8192, "temperature": temperature},
    }
    try:
        async with httpx.AsyncClient(timeout=600.0) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")
    except httpx.ConnectError as exc:
        raise RuntimeError(
            f"Kan geen verbinding maken met Ollama op {OLLAMA_BASE_URL}. "
            "Zorg dat Ollama draait: `ollama serve`"
        ) from exc


def _strip_markdown(raw: str) -> str:
    """Verwijder markdown code fences uit Ollama response."""
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        if len(parts) >= 3:
            raw = parts[1]
        else:
            raw = parts[-1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()


# Segmentgrootte in tekens; klein genoeg voor betrouwbare topic-detectie per
# Ollama-aanroep, groot genoeg om hele clausules bij elkaar te houden.
_SEGMENT_GROOTTE = 3500
_MAX_SEGMENTEN = 6
# Een restje korter dan dit plakken we aan het vorige segment — een aparte
# Ollama-aanroep voor een paar regels is zonde van de (CPU-)tijd.
_MIN_STAART = 500


def _segmenteer(text: str) -> list[str]:
    """Knip de tekst in segmenten op regelgrenzen, zodat clausules heel blijven."""
    segmenten: list[str] = []
    huidig = ""
    for regel in text.split("\n"):
        if huidig and len(huidig) + len(regel) + 1 > _SEGMENT_GROOTTE:
            segmenten.append(huidig)
            huidig = ""
        huidig += regel + "\n"
    if huidig.strip():
        if segmenten and len(huidig) < _MIN_STAART:
            segmenten[-1] += huidig
        else:
            segmenten.append(huidig)
    return segmenten[:_MAX_SEGMENTEN]


async def analyze_document(contract_text: str, topics_list: list[str]) -> dict:
    """Analyseer het VOLLEDIGE contract in segmenten en voeg resultaten samen.

    Elke segment gaat apart door Ollama, zodat ook clausules achterin lange
    contracten gevonden worden i.p.v. alleen de eerste pagina's.
    """
    bekende_topics = set(topics_list)
    contract_type = "anders"
    topics_by_key: dict[str, dict] = {}

    segmenten = _segmenteer(contract_text)
    for i, segment in enumerate(segmenten, start=1):
        prompt = ANALYSE_PROMPT.format(
            contract_text=segment,
            topics_list=", ".join(topics_list),
        )
        raw = await _ollama_request(prompt)
        try:
            analysis = json.loads(_strip_markdown(raw))
        except json.JSONDecodeError:
            _log.warning(
                "Ollama JSON parse fout (analyse segment %d/%d): %.200s",
                i,
                len(segmenten),
                raw,
            )
            continue

        segment_type = analysis.get("contract_type", "anders")
        if contract_type == "anders" and segment_type:
            contract_type = segment_type

        for item in analysis.get("detected_topics", []):
            key = item.get("topic", "")
            if key not in bekende_topics:
                # Vang typefouten van het model op ("onslaggronden" →
                # "ontslaggronden") zodat echte clausules niet verloren gaan
                dichtstbij = difflib.get_close_matches(
                    key, topics_list, n=1, cutoff=0.8
                )
                if not dichtstbij:
                    continue
                key = dichtstbij[0]
                item = {**item, "topic": key}
            # Zonder letterlijke passage is er geen gegronde vraag mogelijk
            if not str(item.get("passage") or "").strip():
                continue
            # Eerste vindplaats wint
            if key not in topics_by_key:
                topics_by_key[key] = item

    return {
        "contract_type": contract_type,
        "detected_topics": list(topics_by_key.values()),
    }


async def generate_question(
    contract_type: str,
    passage: str,
    topic_label: str,
    asked_questions: list[str],
) -> dict:
    """Genereer een vraag voor de contractspecialist."""
    asked_str = (
        "\n".join(f"- {q}" for q in asked_questions)
        if asked_questions
        else "Nog geen vragen gesteld"
    )
    prompt = QUESTION_PROMPT.format(
        contract_type=contract_type,
        passage=passage[:500],
        topic_label=topic_label,
        asked_questions=asked_str,
    )
    # Iets hogere temperature dan bij extractie: vervolgvragen over hetzelfde
    # onderwerp moeten van elkaar verschillen.
    raw = await _ollama_request(prompt, temperature=0.4)
    try:
        return json.loads(_strip_markdown(raw))
    except json.JSONDecodeError:
        _log.warning("Ollama JSON parse fout (vraag): %.200s", raw)
        return {"question": f"Kun je meer vertellen over: {topic_label}?"}


_GEEN_ANTWOORD = (
    "kan geen antwoord",
    "niet in staat",
    "geen relevante",
    "niet beschikbaar",
    "geen verdere informatie",
    "kennisbank is nog leeg",
)


def _build_chat_prompt(
    message: str,
    history: list[dict[str, str]],
    knowledge_chunks: str,
) -> str:
    # Sla "weet het niet" antwoorden over — die sturen de LLM de verkeerde kant op
    filtered = [
        t
        for t in history[-6:]
        if not (
            t.get("role") == "assistant"
            and any(s in t.get("content", "").lower() for s in _GEEN_ANTWOORD)
        )
    ]
    conv = "".join(f"{t['role'].capitalize()}: {t['content']}\n" for t in filtered[-4:])

    prompt = CHAT_PROMPT.format(
        knowledge_chunks=knowledge_chunks[:6000],
        user_question=message,
    )
    if conv:
        prompt = f"Vorige context:\n{conv}\n\n{prompt}"
    return prompt


async def chat_stream(
    message: str,
    history: list[dict[str, str]],
    knowledge_chunks: str,
) -> AsyncGenerator[str, None]:
    """RAG chatbot stream: yield tokens één voor één via Ollama streaming."""
    prompt = _build_chat_prompt(message, history, knowledge_chunks)
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": True,
        # num_ctx ruim boven de Ollama-default van 4096, anders knipt het
        # model de kennisbank er stilletjes aan de voorkant af.
        "options": {"temperature": 0.1, "top_p": 0.9, "num_ctx": 8192},
    }
    try:
        async with httpx.AsyncClient(timeout=600.0) as client:
            async with client.stream(
                "POST", f"{OLLAMA_BASE_URL}/api/generate", json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            _log.warning(
                                "Ollama stuurde geen geldige JSON: %.100s", line
                            )
                            continue
                        token = data.get("response", "")
                        if token:
                            yield token
                        if data.get("done"):
                            break
    except httpx.ConnectError as exc:
        raise RuntimeError(
            f"Kan geen verbinding maken met Ollama op {OLLAMA_BASE_URL}. "
            "Zorg dat Ollama draait: `ollama serve`"
        ) from exc
    except (
        httpx.TimeoutException,
        httpx.RemoteProtocolError,
        httpx.HTTPStatusError,
    ) as exc:
        raise RuntimeError(f"Ollama verbindingsfout: {exc}") from exc
