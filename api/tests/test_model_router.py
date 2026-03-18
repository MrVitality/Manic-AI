"""Tests for model_router -- cloud (OpenAI) backend routing."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_openai_response(content: str, model: str = "gpt-4o-mini") -> dict:
    return {
        "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        "model": model,
    }


def _make_mock_http_client(response_data: dict, status_code: int = 200) -> AsyncMock:
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.json.return_value = response_data
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=mock_response)
    return mock_client


# ---------------------------------------------------------------------------
# Config fields
# ---------------------------------------------------------------------------


def test_openai_config_fields_exist():
    """Config must expose OPENAI_API_KEY, ANTHROPIC_API_KEY, OPENAI_BASE_URL."""
    from api.config import settings

    assert hasattr(settings, "OPENAI_API_KEY")
    assert hasattr(settings, "ANTHROPIC_API_KEY")
    assert hasattr(settings, "OPENAI_BASE_URL")
    assert settings.OPENAI_BASE_URL == "https://api.openai.com/v1"


# ---------------------------------------------------------------------------
# Non-streaming OpenAI routing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_routes_to_openai_backend_non_streaming():
    """chat_completion routes to OpenAI when backend='openai' and key is set."""
    from api.services.model_router import chat_completion

    mock_data = _make_openai_response("mocked reply", "gpt-4o-mini")
    mock_client = _make_mock_http_client(mock_data)

    with patch("api.config.settings.INFERENCE_BACKEND", "openai"), \
         patch("api.config.settings.OPENAI_API_KEY", "sk-test-key"), \
         patch("api.config.settings.OPENAI_BASE_URL", "https://api.openai.com/v1"):
        result = await chat_completion(
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-4o-mini",
            stream=False,
            http_client=mock_client,
        )

    assert result["content"] == "mocked reply"
    assert result["model"] == "gpt-4o-mini"
    assert result["prompt_tokens"] == 10
    assert result["completion_tokens"] == 5
    assert "raw" in result


@pytest.mark.asyncio
async def test_openai_backend_requires_api_key():
    """chat_completion falls back to Ollama if OPENAI_API_KEY is empty."""
    from api.services.model_router import chat_completion

    ollama_data = {
        "message": {"content": "ollama reply"},
        "prompt_eval_count": 8,
        "eval_count": 3,
    }
    mock_client = _make_mock_http_client(ollama_data)

    with patch("api.config.settings.INFERENCE_BACKEND", "openai"), \
         patch("api.config.settings.OPENAI_API_KEY", ""):
        result = await chat_completion(
            messages=[{"role": "user", "content": "hi"}],
            model="llama3.2:3b",
            stream=False,
            http_client=mock_client,
        )

    # Should have fallen back to Ollama (Ollama uses OLLAMA_URL endpoint)
    assert result["content"] == "ollama reply"


@pytest.mark.asyncio
async def test_openai_chat_sends_authorization_header():
    """_openai_chat must include Authorization: Bearer in the request."""
    from api.services.model_router import _openai_chat

    mock_data = _make_openai_response("test response")
    mock_client = _make_mock_http_client(mock_data)

    with patch("api.config.settings.OPENAI_API_KEY", "sk-test-key"), \
         patch("api.config.settings.OPENAI_BASE_URL", "https://api.openai.com/v1"):
        await _openai_chat(
            [{"role": "user", "content": "hello"}],
            "gpt-4o-mini",
            mock_client,
        )

    call_kwargs = mock_client.post.call_args
    headers = call_kwargs.kwargs.get("headers", {})
    assert "Authorization" in headers
    assert headers["Authorization"] == "Bearer sk-test-key"


# ---------------------------------------------------------------------------
# Streaming OpenAI routing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_openai_stream_yields_content_and_done():
    """_openai_chat_stream yields content chunks and a final done chunk."""
    from api.services.model_router import _openai_chat_stream

    sse_lines = [
        'data: {"choices": [{"delta": {"content": "Hello"}}], "usage": null}',
        'data: {"choices": [{"delta": {"content": " world"}}], "usage": null}',
        'data: {"choices": [{"delta": {}}], "usage": {"prompt_tokens": 5, "completion_tokens": 2}}',
        "data: [DONE]",
    ]

    async def _aiter_lines():
        for line in sse_lines:
            yield line

    mock_response = MagicMock()
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)
    mock_response.aiter_lines = _aiter_lines

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.stream = MagicMock(return_value=mock_response)

    with patch("api.config.settings.OPENAI_API_KEY", "sk-test"), \
         patch("api.config.settings.OPENAI_BASE_URL", "https://api.openai.com/v1"):
        chunks = []
        async for chunk in _openai_chat_stream(
            [{"role": "user", "content": "hi"}],
            "gpt-4o-mini",
            mock_client,
        ):
            chunks.append(chunk)

    content_chunks = [c for c in chunks if c.get("type") == "content"]
    done_chunks = [c for c in chunks if c.get("type") == "done"]

    assert len(content_chunks) == 2
    assert content_chunks[0]["content"] == "Hello"
    assert content_chunks[1]["content"] == " world"
    assert len(done_chunks) == 1
    assert done_chunks[0]["prompt_tokens"] == 5
    assert done_chunks[0]["completion_tokens"] == 2
