"""Unit tests voor claude_client (puur transport, gemockte anthropic SDK)."""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

import claude_client  # noqa: E402


# ── is_available ────────────────────────────────────────────────────────────


def test_is_available_zonder_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert claude_client.is_available() is False


def test_is_available_met_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    assert claude_client.is_available() is True


# ── generate ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_zonder_key_geeft_duidelijke_fout(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        await claude_client.generate("prompt")


def _mock_anthropic_client(response=None, side_effect=None):
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(
        return_value=response, side_effect=side_effect
    )
    return mock_client


@pytest.mark.asyncio
async def test_generate_succes_zonder_temperature(monkeypatch):
    """De prompt gaat 1-op-1 door; temperature wordt bewust NIET meegestuurd
    (Sonnet 5 weigert non-default samplingparameters)."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    block = MagicMock()
    block.type = "text"
    block.text = "Antwoord van Claude"
    response = MagicMock()
    response.content = [block]
    mock_client = _mock_anthropic_client(response=response)

    with patch("claude_client.anthropic.AsyncAnthropic", return_value=mock_client):
        result = await claude_client.generate("DE PROMPT")

    assert result == "Antwoord van Claude"
    kwargs = mock_client.messages.create.await_args.kwargs
    assert kwargs["messages"] == [{"role": "user", "content": "DE PROMPT"}]
    assert "temperature" not in kwargs


@pytest.mark.asyncio
async def test_generate_verbindingsfout(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    fout = anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))
    mock_client = _mock_anthropic_client(side_effect=fout)

    with patch("claude_client.anthropic.AsyncAnthropic", return_value=mock_client):
        with pytest.raises(RuntimeError, match="Claude API"):
            await claude_client.generate("prompt")


@pytest.mark.asyncio
async def test_generate_api_statusfout(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    request = httpx.Request("POST", "https://api.anthropic.com")
    response = httpx.Response(429, request=request)
    fout = anthropic.APIStatusError("rate limited", response=response, body=None)
    mock_client = _mock_anthropic_client(side_effect=fout)

    with patch("claude_client.anthropic.AsyncAnthropic", return_value=mock_client):
        with pytest.raises(RuntimeError, match="429"):
            await claude_client.generate("prompt")


@pytest.mark.asyncio
async def test_generate_overige_sdk_fout(monkeypatch):
    """Andere anthropic-SDK-fouten dan connectie/status krijgen ook een nette
    RuntimeError (bijv. een response die niet aan het schema voldoet)."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    request = httpx.Request("POST", "https://api.anthropic.com")
    response = httpx.Response(200, request=request)
    fout = anthropic.APIResponseValidationError(response=response, body=None)
    mock_client = _mock_anthropic_client(side_effect=fout)

    with patch("claude_client.anthropic.AsyncAnthropic", return_value=mock_client):
        with pytest.raises(RuntimeError, match="Claude API fout"):
            await claude_client.generate("prompt")


# ── stream ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stream_yield_tokens(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    async def fake_text_stream():
        yield "Hal"
        yield "lo"

    inner = MagicMock()
    inner.text_stream = fake_text_stream()
    stream_cm = MagicMock()
    stream_cm.__aenter__ = AsyncMock(return_value=inner)
    stream_cm.__aexit__ = AsyncMock(return_value=False)

    mock_client = MagicMock()
    mock_client.messages.stream = MagicMock(return_value=stream_cm)

    with patch("claude_client.anthropic.AsyncAnthropic", return_value=mock_client):
        tokens = [t async for t in claude_client.stream("prompt")]

    assert tokens == ["Hal", "lo"]
    kwargs = mock_client.messages.stream.call_args.kwargs
    assert kwargs["messages"] == [{"role": "user", "content": "prompt"}]
    assert "temperature" not in kwargs


@pytest.mark.asyncio
async def test_stream_zonder_key_geeft_duidelijke_fout(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        async for _ in claude_client.stream("prompt"):
            pass


@pytest.mark.asyncio
async def test_stream_verbindingsfout(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    fout = anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))
    mock_client = MagicMock()
    mock_client.messages.stream = MagicMock(side_effect=fout)

    with patch("claude_client.anthropic.AsyncAnthropic", return_value=mock_client):
        with pytest.raises(RuntimeError, match="Claude API"):
            async for _ in claude_client.stream("prompt"):
                pass


@pytest.mark.asyncio
async def test_stream_overige_sdk_fout(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    request = httpx.Request("POST", "https://api.anthropic.com")
    response = httpx.Response(200, request=request)
    fout = anthropic.APIResponseValidationError(response=response, body=None)
    mock_client = MagicMock()
    mock_client.messages.stream = MagicMock(side_effect=fout)

    with patch("claude_client.anthropic.AsyncAnthropic", return_value=mock_client):
        with pytest.raises(RuntimeError, match="Claude API fout"):
            async for _ in claude_client.stream("prompt"):
                pass
