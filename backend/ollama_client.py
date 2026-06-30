"""Ollama LLM client voor Kenniscapture."""
import json
import logging
import os
from collections.abc import AsyncGenerator

import httpx

_log = logging.getLogger("app.ollama")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

ANALYSE_PROMPT = """Je analyseert een contract van een contractspecialist.
Geef ALLEEN een JSON response terug, geen uitleg of markdown.

Contract tekst:
{contract_text}

Bekende onderwerpen om op te letten: {topics_list}

Geef terug:
{{
  "contract_type": "NDA|arbeidscontract|leverancier|anders",
  "detected_topics": [
    {{
      "topic": "topic_sleutel_uit_de_lijst",
      "passage": "het exacte stukje tekst uit het contract (max 200 chars)",
      "page_hint": "zoekterm om de passage terug te vinden"
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
- Direct gerelateerd zijn aan de passage
- Vragen naar beslislogica, niet naar feiten
- Kort zijn (max 2 zinnen)
- In het Nederlands zijn

Geef terug:
{{
  "question": "de vraag"
}}"""

CHAT_PROMPT = """Je bent een assistent die uitsluitend antwoordt op basis van de KENNISBANK hieronder.
De kennisbank bevat vraag-en-antwoord paren van een contractspecialist.

STRIKTE REGELS — NOOIT overtreden:
1. Gebruik ALLEEN informatie die letterlijk in de kennisbank staat.
2. Voeg GEEN eigen redenering, aanvullingen of algemene kennis toe — ook niet als iemand vraagt om "uitgebreider" of "meer uitleg".
3. Als de kennisbank onvoldoende info bevat, zeg dan letterlijk: "De kennisbank bevat hierover geen verdere informatie."
4. Citeer altijd de bron (topic + documentnaam) aan het einde van je antwoord.
5. Antwoord in het Nederlands. Wees beknopt en direct.

KENNISBANK:
{knowledge_chunks}

VRAAG: {user_question}

ANTWOORD (alleen op basis van bovenstaande kennisbank):"""


async def _ollama_request(prompt: str) -> str:
    """Stuur een prompt naar Ollama en geef de response terug."""
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
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


async def analyze_document(contract_text: str, topics_list: list[str]) -> dict:
    """Analyseer een contract en detecteer topics."""
    prompt = ANALYSE_PROMPT.format(
        contract_text=contract_text[:4000],
        topics_list=", ".join(topics_list),
    )
    raw = await _ollama_request(prompt)
    try:
        return json.loads(_strip_markdown(raw))
    except json.JSONDecodeError:
        _log.warning("Ollama JSON parse fout (analyse): %.200s", raw)
        return {"contract_type": "anders", "detected_topics": []}


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
    raw = await _ollama_request(prompt)
    try:
        return json.loads(_strip_markdown(raw))
    except json.JSONDecodeError:
        _log.warning("Ollama JSON parse fout (vraag): %.200s", raw)
        return {"question": f"Kun je meer vertellen over: {topic_label}?"}


_GEEN_ANTWOORD = ("kan geen antwoord", "niet in staat", "geen relevante", "niet beschikbaar")


def _build_chat_prompt(
    message: str,
    history: list[dict[str, str]],
    knowledge_chunks: str,
) -> str:
    # Sla "weet het niet" antwoorden over — die sturen de LLM de verkeerde kant op
    filtered = [
        t for t in history[-6:]
        if not (
            t.get("role") == "assistant"
            and any(s in t.get("content", "").lower() for s in _GEEN_ANTWOORD)
        )
    ]
    conv = "".join(
        f"{t['role'].capitalize()}: {t['content']}\n"
        for t in filtered[-4:]
    )

    prompt = CHAT_PROMPT.format(
        knowledge_chunks=knowledge_chunks[:4000],
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
        "options": {"temperature": 0.1, "top_p": 0.9},
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
                            _log.warning("Ollama stuurde geen geldige JSON: %.100s", line)
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
    except (httpx.TimeoutException, httpx.RemoteProtocolError, httpx.HTTPStatusError) as exc:
        raise RuntimeError(f"Ollama verbindingsfout: {exc}") from exc
