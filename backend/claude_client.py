"""Claude API transport (demo-provider) voor Kenniscapture.

Puur transport: krijgt een kant-en-klare prompt en geeft tekst (of een
tokenstream) terug. Alle prompts, boundaries en filters leven in
llm_client.py en zijn identiek aan die van de Ollama-provider.

Let op: contractdata verlaat in deze modus het interne netwerk (naar de
Anthropic API). Alleen gebruiken voor demo's met voorbeeldcontracten.
"""

import logging
import os
from collections.abc import AsyncGenerator

import anthropic

_log = logging.getLogger("app.claude")

CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5")
_MAX_TOKENS = 4096


def is_available() -> bool:
    """Is er een API-key geconfigureerd?"""
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def _client() -> anthropic.AsyncAnthropic:
    if not is_available():
        raise RuntimeError(
            "Geen ANTHROPIC_API_KEY geconfigureerd. "
            "Zet de key in config.env of switch terug naar Ollama."
        )
    return anthropic.AsyncAnthropic()


async def generate(prompt: str) -> str:
    """Stuur een prompt naar de Claude API en geef de tekst terug.

    Geen temperature: Sonnet 5 accepteert geen non-default samplingparameters;
    de striktheid zit in de gedeelde prompts uit llm_client.py.
    """
    client = _client()
    try:
        response = await client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIConnectionError as exc:
        raise RuntimeError(f"Kan de Claude API niet bereiken: {exc}") from exc
    except anthropic.APIStatusError as exc:
        raise RuntimeError(
            f"Claude API fout ({exc.status_code}): {exc.message}"
        ) from exc
    except anthropic.APIError as exc:
        raise RuntimeError(f"Claude API fout: {exc}") from exc
    return "".join(block.text for block in response.content if block.type == "text")


async def stream(prompt: str) -> AsyncGenerator[str, None]:
    """Stream tokens van de Claude API, één voor één."""
    client = _client()
    try:
        async with client.messages.stream(
            model=CLAUDE_MODEL,
            max_tokens=_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        ) as response_stream:
            async for text in response_stream.text_stream:
                yield text
    except anthropic.APIConnectionError as exc:
        raise RuntimeError(f"Kan de Claude API niet bereiken: {exc}") from exc
    except anthropic.APIStatusError as exc:
        raise RuntimeError(
            f"Claude API fout ({exc.status_code}): {exc.message}"
        ) from exc
    except anthropic.APIError as exc:
        raise RuntimeError(f"Claude API fout: {exc}") from exc
