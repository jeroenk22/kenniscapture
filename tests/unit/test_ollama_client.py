"""Unit tests voor ollama_client (puur transport): generate en stream."""
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

import ollama_client  # noqa: E402


# ── generate ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_succes():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"response": "Antwoord van Ollama"}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await ollama_client.generate("test prompt")

    assert result == "Antwoord van Ollama"


@pytest.mark.asyncio
async def test_generate_stuurt_temperature_mee():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"response": "ok"}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient", return_value=mock_client):
        await ollama_client.generate("test", temperature=0.4)

    payload = mock_client.post.await_args.kwargs["json"]
    assert payload["options"]["temperature"] == 0.4
    assert payload["options"]["num_ctx"] == 8192


@pytest.mark.asyncio
async def test_generate_connect_error():
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("geen verbinding"))

    with patch("httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(RuntimeError, match="Ollama"):
            await ollama_client.generate("test")


# ── stream ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stream_yield_tokens():
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
        async for token in ollama_client.stream("vraag"):
            tokens.append(token)

    assert tokens == ["Hallo", " wereld"]


@pytest.mark.asyncio
async def test_stream_sla_slechte_json_over():
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
        async for token in ollama_client.stream("vraag"):
            tokens.append(token)

    assert tokens == ["Token"]


@pytest.mark.asyncio
async def test_stream_connect_error():
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.stream = MagicMock(side_effect=httpx.ConnectError("geen verbinding"))

    with patch("httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(RuntimeError, match="Ollama"):
            async for _ in ollama_client.stream("vraag"):
                pass


@pytest.mark.asyncio
async def test_stream_timeout_error():
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.stream = MagicMock(side_effect=httpx.TimeoutException("timeout"))

    with patch("httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(RuntimeError, match="verbindingsfout"):
            async for _ in ollama_client.stream("vraag"):
                pass
