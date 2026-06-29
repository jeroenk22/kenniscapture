"""Ollama LLM client voor Kenniscapture."""
import json
import logging
import os

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

CHAT_PROMPT = """Je bent een assistent die vragen beantwoordt over contracten.
Je antwoordt ALLEEN op basis van de onderstaande kennisbank.
Verzin niets. Als het antwoord er niet in staat, zeg dat dan eerlijk.
Antwoord in het Nederlands.

KENNISBANK:
{knowledge_chunks}

VRAAG: {user_question}

Geef je antwoord en vermeld aan het einde welke bronnen je gebruikte."""


async def _ollama_request(prompt: str) -> str:
    """Stuur een prompt naar Ollama en geef de response terug."""
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
    }
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
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


async def chat(
    message: str,
    history: list[dict[str, str]],
    knowledge_chunks: str,
) -> dict:
    """RAG chatbot: beantwoord een vraag op basis van de kennisbank."""
    conv = ""
    for turn in history[-4:]:
        role = turn.get("role", "user")
        content = turn.get("content", "")
        conv += f"{role.capitalize()}: {content}\n"

    prompt = CHAT_PROMPT.format(
        knowledge_chunks=knowledge_chunks[:3000],
        user_question=message,
    )
    if conv:
        prompt = f"Vorige context:\n{conv}\n\n{prompt}"

    raw = await _ollama_request(prompt)

    # Eenvoudige bronextractie
    sources: list[dict] = []
    for line in raw.split("\n"):
        if "bron:" in line.lower():
            parts = line.split(":", 1)
            if len(parts) > 1:
                sources.append({
                    "file": parts[1].strip(),
                    "passage": "",
                    "topic_label": "",
                })

    return {"answer": raw, "sources": sources}
