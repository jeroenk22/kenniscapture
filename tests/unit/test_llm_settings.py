"""Unit tests voor llm_settings: providerkeuze en de env-fallback bij init."""
import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

import llm_settings  # noqa: E402


@pytest.fixture(autouse=True)
def herstel_module_status(monkeypatch):
    """Herlaad de module na afloop met een schone env, zodat de in-memory
    providerkeuze niet doorlekt naar andere tests."""
    yield
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    importlib.reload(llm_settings)


def test_ongeldige_env_provider_valt_terug_op_ollama(monkeypatch, caplog):
    monkeypatch.setenv("LLM_PROVIDER", "banaan")
    with caplog.at_level("WARNING", logger="app.llm_settings"):
        herladen = importlib.reload(llm_settings)

    assert herladen.get_provider() == "ollama"
    assert "banaan" in caplog.text


def test_geldige_env_provider_wordt_overgenomen(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "claude")
    herladen = importlib.reload(llm_settings)

    assert herladen.get_provider() == "claude"
