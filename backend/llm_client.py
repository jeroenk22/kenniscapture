"""LLM-orkestratie voor Kenniscapture: prompts, segmentatie en provider-dispatch.

Alle prompts, boundaries en filters leven hier en gelden voor élke provider.
De providers zelf (ollama_client, claude_client) zijn puur transport: prompt
erin, tekst of tokenstream eruit. Welke provider actief is bepaalt
llm_settings (standaard: ollama, volledig lokaal).
"""

import difflib
import json
import logging
import re
from collections.abc import AsyncGenerator

import claude_client
import llm_settings
import ollama_client

_log = logging.getLogger("app.llm")

ANALYSE_PROMPT = """Je analyseert een (deel van een) contract voor een contractspecialist.
Geef ALLEEN een JSON response terug, geen uitleg of markdown.

Contract tekst:
{contract_text}

Bekende contracttypes uit eerdere contracten (hergebruik er een als die
inhoudelijk past): {known_types}

Bekende onderwerpen uit eerdere contracten (hergebruik een sleutel als een
clausule hier EXACT inhoudelijk bij past): {topics_list}

Instructies:
- Bepaal zelf het contracttype op basis van de daadwerkelijke inhoud van de
  tekst (bijvoorbeeld "arbeidscontract", "NDA", "leverancier",
  "aannemingsovereenkomst", "huurovereenkomst", ...). Hergebruik een bekend
  contracttype als dat inhoudelijk past; is de tekst duidelijk een ander
  soort contract, verzin dan een nieuwe, korte en consistente naam
  (snake_case bij meerdere woorden).
- Loop de bekende onderwerpen langs en controleer of er in de tekst een
  clausule of passage over staat. Neem ALLEEN onderwerpen op die
  daadwerkelijk in de tekst voorkomen — geen lege passages.
- Kom je een clausule tegen die inhoudelijk NIET bij een bekend onderwerp
  past, verzin dan een nieuwe, korte snake_case sleutel plus een leesbare
  Nederlandse label voor dat onderwerp. Zo blijft de onderwerpencatalogus
  meegroeien met nieuwe contracttypes.
- "passage" moet een LETTERLIJK citaat uit de tekst zijn (max 200 tekens).
  Kies het citaat met de concrete keuze: bedragen, termijnen, percentages of
  voorwaarden. Verzin GEEN passages en parafraseer NIET.

Geef terug:
{{
  "contract_type": "korte_consistente_categorienaam",
  "detected_topics": [
    {{
      "topic": "snake_case_sleutel (bestaand of nieuw)",
      "topic_label": "Leesbare Nederlandse naam van het onderwerp",
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


async def _generate(prompt: str, temperature: float = 0.1) -> str:
    """Stuur een prompt naar de actieve provider (zelfde prompt, ander transport)."""
    if llm_settings.get_provider() == "claude":
        return await claude_client.generate(prompt)
    return await ollama_client.generate(prompt, temperature)


def _stream(prompt: str, temperature: float = 0.1) -> AsyncGenerator[str, None]:
    """Tokenstream van de actieve provider (zelfde prompt, ander transport)."""
    if llm_settings.get_provider() == "claude":
        return claude_client.stream(prompt)
    return ollama_client.stream(prompt, temperature)


def _strip_markdown(raw: str) -> str:
    """Verwijder markdown code fences uit de LLM-response."""
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
# LLM-aanroep, groot genoeg om hele clausules bij elkaar te houden.
_SEGMENT_GROOTTE = 3500
_MAX_SEGMENTEN = 6
# Een restje korter dan dit plakken we aan het vorige segment — een aparte
# LLM-aanroep voor een paar regels is zonde van de tijd.
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


def _slugify(text: str) -> str:
    """Normaliseer een door de LLM verzonnen topic-sleutel naar snake_case."""
    text = re.sub(r"[^a-z0-9]+", "_", (text or "").strip().lower())
    return text.strip("_")


def _normalize_contract_type(text: str) -> str:
    """Ruim spaties op maar behoud hoofdlettergebruik (bv. bestaande 'NDA')."""
    return re.sub(r"\s+", "_", (text or "").strip())


async def analyze_document(
    contract_text: str,
    topics_list: list[str],
    known_contract_types: list[str] | None = None,
) -> dict:
    """Analyseer het VOLLEDIGE contract in segmenten en voeg resultaten samen.

    Elke segment gaat apart door de LLM, zodat ook clausules achterin lange
    contracten gevonden worden i.p.v. alleen de eerste pagina's. Het
    contracttype en onderwerpen die niet bij de bekende catalogus passen
    worden niet weggegooid maar overgenomen — de catalogus is een generieke
    dekking-tracker die meegroeit met elk nieuw contracttype.
    """
    bekende_topics = set(topics_list)
    contract_type = "anders"
    topics_by_key: dict[str, dict] = {}

    segmenten = _segmenteer(contract_text)
    for i, segment in enumerate(segmenten, start=1):
        prompt = ANALYSE_PROMPT.format(
            contract_text=segment,
            topics_list=", ".join(topics_list) if topics_list else "(nog geen)",
            known_types=", ".join(known_contract_types)
            if known_contract_types
            else "(nog geen)",
        )
        raw = await _generate(prompt)
        try:
            analysis = json.loads(_strip_markdown(raw))
        except json.JSONDecodeError:
            _log.warning(
                "LLM JSON parse fout (analyse segment %d/%d): %.200s",
                i,
                len(segmenten),
                raw,
            )
            continue

        segment_type = (
            _normalize_contract_type(analysis.get("contract_type", "")) or "anders"
        )
        if contract_type == "anders" and segment_type != "anders":
            contract_type = segment_type

        for item in analysis.get("detected_topics", []):
            key = _slugify(item.get("topic", ""))
            if not key:
                continue
            if key not in bekende_topics:
                # Vang typefouten van het model op ("onslaggronden" →
                # "ontslaggronden") zodat het geen onnodig nieuw topic wordt
                dichtstbij = difflib.get_close_matches(
                    key, topics_list, n=1, cutoff=0.8
                )
                if dichtstbij:
                    key = dichtstbij[0]
                # geen close match: dit is een echt nieuw onderwerp — blijft
                # staan i.p.v. te worden weggegooid
            # Zonder letterlijke passage is er geen gegronde vraag mogelijk
            if not str(item.get("passage") or "").strip():
                continue
            label = (
                str(item.get("topic_label") or "").strip()
                or key.replace("_", " ").capitalize()
            )
            item = {**item, "topic": key, "topic_label": label}
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
    raw = await _generate(prompt, temperature=0.4)
    try:
        return json.loads(_strip_markdown(raw))
    except json.JSONDecodeError:
        _log.warning("LLM JSON parse fout (vraag): %.200s", raw)
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
    """RAG chatbot stream: yield tokens één voor één via de actieve provider."""
    prompt = _build_chat_prompt(message, history, knowledge_chunks)
    async for token in _stream(prompt, temperature=0.1):
        yield token
