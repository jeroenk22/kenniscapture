"""Providerkeuze voor de LLM-laag: ollama (standaard, lokaal) of claude (demo).

De keuze leeft in-memory; na een herstart van de backend geldt weer de
default uit de LLM_PROVIDER omgevingsvariabele. Zo valt het systeem altijd
terug op de veilige, volledig lokale standaard.
"""

import logging
import os

_log = logging.getLogger("app.llm_settings")

PROVIDERS = ("ollama", "claude")

_provider = os.getenv("LLM_PROVIDER", "ollama")
if _provider not in PROVIDERS:
    _log.warning("Onbekende LLM_PROVIDER %r — terugvallen op ollama", _provider)
    _provider = "ollama"


def get_provider() -> str:
    return _provider


def set_provider(provider: str) -> None:
    global _provider
    if provider not in PROVIDERS:
        raise ValueError(f"Onbekende provider: {provider!r}")
    _provider = provider
    _log.info("LLM-provider gewijzigd naar %s", provider)
