"""Ollama transport (lokale standaard-provider) voor Kenniscapture.

Puur transport: krijgt een kant-en-klare prompt en geeft tekst (of een
tokenstream) terug. Alle prompts, boundaries en filters leven in
llm_client.py.
"""

import json
import logging
import os
from collections.abc import AsyncGenerator

import httpx

_log = logging.getLogger("app.ollama")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")


async def generate(prompt: str, temperature: float = 0.1) -> str:
    """Stuur een prompt naar Ollama en geef de response terug."""
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        # num_ctx ruim boven de Ollama-default van 4096, anders knipt het
        # model lange prompts er stilletjes aan de voorkant af.
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


async def stream(prompt: str, temperature: float = 0.1) -> AsyncGenerator[str, None]:
    """Stream tokens van Ollama, één voor één."""
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": True,
        "options": {"temperature": temperature, "top_p": 0.9, "num_ctx": 8192},
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
