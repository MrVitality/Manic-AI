"""Tests for model_router -- Ollama and vLLM backend routing.

Complements test_model_router.py which covers the OpenAI backend.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ollama_response(content: str, prompt_tokens: int = 5, completion_tokens: int = 3) -> dict:
    """Build a dict matching Ollama's /api/chat non-streaming response shape."""
    return {
        "message": {"content": content},
        "prompt_eval_count": prompt_tokens,
        "eval_count": completion_tokens,
        "done": True,
    }


def _make_vllm_response(content: str, model: str = "mistral-7b") -> dict:
    """Build a dict matching vLLM's OpenAI-compatible /v1/chat/completions shape."""
    return {
        "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 8, "completion_tokens": 4},
        "model": model,
    }


def _make_mock_client(response_data: dict, status_code: int = 200) -> AsyncMock:
    """Return a mock httpx.AsyncClient whose post() returns response_data."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.json.return_value = response_data
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=mock_response)
    return mock_client


# ---------------------------------------------------------------------------
# Ollama backend -- non-streaming
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ollama_chat_returns_normalized_response():
    """Ollama backend normalises response to the standard five-key dict."""
    from api.services.model_router import _ollama_chat

    data = _make_ollama_response("hi there", prompt_tokens=5, completion_tokens=3)
    mock_client = _make_mock_client(data)

    with patch("api.config.settings.OLLAMA_URL", "http://ollama:11434"):
        result = await _ollama_chat(
            messages=[{"role": "user", "content": "hello"}],
            model="llama3.2:3b",
            client=mock_client,
        )

    assert result["content"] == "hi there"
    assert result["prompt_tokens"] == 5
    assert result["completion_tokens"] == 3
    assert result["model"] == "llama3.2:3b"
    assert "raw" in result


@pytest.mark.asyncio
async def test_ollama_chat_posts_to_correct_url():
    """Ollama backend must POST to <OLLAMA_URL>/api/chat."""
    from api.services.model_router import _ollama_chat

    data = _make_ollama_response("ok")
    mock_client = _make_mock_client(data)

    with patch("api.config.settings.OLLAMA_URL", "http://ollama:11434"):
        await _ollama_chat(
            messages=[{"role": "user", "content": "test"}],
            model="llama3.2:3b",
            client=mock_client,
        )

    call_args = mock_client.post.call_args
    url = call_args.args[0] if call_args.args else call_args.kwargs.get("url", "")
    assert url == "http://ollama:11434/api/chat"


@pytest.mark.asyncio
async def test_ollama_chat_sends_stream_false():
    """Ollama non-streaming call must include stream=False in the payload."""
    from api.services.model_router import _ollama_chat

    data = _make_ollama_response("ok")
    mock_client = _make_mock_client(data)

    with patch("api.config.settings.OLLAMA_URL", "http://ollama:11434"):
        await _ollama_chat(
            messages=[{"role": "user", "content": "test"}],
            model="llama3.2:3b",
            client=mock_client,
        )

    payload = mock_client.post.call_args.kwargs.get("json", {})
    assert payload.get("stream") is False


@pytest.mark.asyncio
async def test_ollama_chat_empty_message_content_defaults_to_empty_string():
    """If Ollama omits 'message.content', content normalises to empty string."""
    from api.services.model_router import _ollama_chat

    data = {"done": True, "prompt_eval_count": 0, "eval_count": 0}  # no 'message' key
    mock_client = _make_mock_client(data)

    with patch("api.config.settings.OLLAMA_URL", "http://ollama:11434"):
        result = await _ollama_chat(
            messages=[{"role": "user", "content": "test"}],
            model="llama3.2:3b",
            client=mock_client,
        )

    assert result["content"] == ""
    assert result["prompt_tokens"] == 0
    assert result["completion_tokens"] == 0


@pytest.mark.asyncio
async def test_ollama_chat_raises_on_http_error():
    """_ollama_chat propagates httpx.HTTPStatusError from raise_for_status."""
    from api.services.model_router import _ollama_chat

    mock_response = MagicMock()
    mock_response.status_code = 503
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "Service Unavailable",
            request=MagicMock(),
            response=mock_response,
        )
    )
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("api.config.settings.OLLAMA_URL", "http://ollama:11434"):
        with pytest.raises(httpx.HTTPStatusError):
            await _ollama_chat(
                messages=[{"role": "user", "content": "hi"}],
                model="llama3.2:3b",
                client=mock_client,
            )


# ---------------------------------------------------------------------------
# chat_completion routes to Ollama by default / when configured
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_completion_routes_to_ollama_when_backend_is_ollama():
    """chat_completion calls the Ollama endpoint when INFERENCE_BACKEND='ollama'."""
    from api.services.model_router import chat_completion

    data = _make_ollama_response("ollama says hi")
    mock_client = _make_mock_client(data)

    with patch("api.config.settings.INFERENCE_BACKEND", "ollama"), \
         patch("api.config.settings.OLLAMA_URL", "http://ollama:11434"):
        result = await chat_completion(
            messages=[{"role": "user", "content": "hi"}],
            model="llama3.2:3b",
            stream=False,
            http_client=mock_client,
        )

    assert result["content"] == "ollama says hi"
    assert result["model"] == "llama3.2:3b"


@pytest.mark.asyncio
async def test_chat_completion_defaults_to_ollama_for_unknown_backend():
    """Unknown INFERENCE_BACKEND values fall through to Ollama."""
    from api.services.model_router import chat_completion

    data = _make_ollama_response("fallback")
    mock_client = _make_mock_client(data)

    with patch("api.config.settings.INFERENCE_BACKEND", "unknown_backend"), \
         patch("api.config.settings.OLLAMA_URL", "http://ollama:11434"):
        result = await chat_completion(
            messages=[{"role": "user", "content": "test"}],
            model="llama3.2:3b",
            stream=False,
            http_client=mock_client,
        )

    assert result["content"] == "fallback"


# ---------------------------------------------------------------------------
# vLLM backend -- non-streaming
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_vllm_chat_returns_normalized_response():
    """vLLM backend normalises OpenAI-compatible response to standard format."""
    from api.services.model_router import _vllm_chat

    data = _make_vllm_response("vllm says hello", model="mistral-7b")
    mock_client = _make_mock_client(data)

    with patch("api.config.settings.VLLM_URL", "http://vllm:8000"):
        result = await _vllm_chat(
            messages=[{"role": "user", "content": "hi"}],
            model="mistral-7b",
            client=mock_client,
        )

    assert result["content"] == "vllm says hello"
    assert result["prompt_tokens"] == 8
    assert result["completion_tokens"] == 4
    assert result["model"] == "mistral-7b"
    assert "raw" in result


@pytest.mark.asyncio
async def test_vllm_chat_posts_to_correct_url():
    """vLLM backend must POST to <VLLM_URL>/v1/chat/completions."""
    from api.services.model_router import _vllm_chat

    data = _make_vllm_response("ok")
    mock_client = _make_mock_client(data)

    with patch("api.config.settings.VLLM_URL", "http://vllm:8000"):
        await _vllm_chat(
            messages=[{"role": "user", "content": "test"}],
            model="mistral-7b",
            client=mock_client,
        )

    call_args = mock_client.post.call_args
    url = call_args.args[0] if call_args.args else call_args.kwargs.get("url", "")
    assert url == "http://vllm:8000/v1/chat/completions"


@pytest.mark.asyncio
async def test_vllm_chat_includes_max_tokens_when_provided():
    """max_tokens must appear in the POST body when explicitly supplied."""
    from api.services.model_router import _vllm_chat

    data = _make_vllm_response("response")
    mock_client = _make_mock_client(data)

    with patch("api.config.settings.VLLM_URL", "http://vllm:8000"):
        await _vllm_chat(
            messages=[{"role": "user", "content": "test"}],
            model="mistral-7b",
            client=mock_client,
            max_tokens=256,
        )

    payload = mock_client.post.call_args.kwargs.get("json", {})
    assert payload.get("max_tokens") == 256


@pytest.mark.asyncio
async def test_vllm_chat_omits_max_tokens_when_none():
    """max_tokens must NOT appear in the POST body when not supplied."""
    from api.services.model_router import _vllm_chat

    data = _make_vllm_response("response")
    mock_client = _make_mock_client(data)

    with patch("api.config.settings.VLLM_URL", "http://vllm:8000"):
        await _vllm_chat(
            messages=[{"role": "user", "content": "test"}],
            model="mistral-7b",
            client=mock_client,
        )

    payload = mock_client.post.call_args.kwargs.get("json", {})
    assert "max_tokens" not in payload


@pytest.mark.asyncio
async def test_vllm_chat_raises_on_http_error():
    """_vllm_chat propagates httpx.HTTPStatusError when the server returns an error."""
    from api.services.model_router import _vllm_chat

    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "Internal Server Error",
            request=MagicMock(),
            response=mock_response,
        )
    )
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("api.config.settings.VLLM_URL", "http://vllm:8000"):
        with pytest.raises(httpx.HTTPStatusError):
            await _vllm_chat(
                messages=[{"role": "user", "content": "hi"}],
                model="mistral-7b",
                client=mock_client,
            )


@pytest.mark.asyncio
async def test_vllm_chat_empty_choices_raises():
    """If vLLM returns an empty choices list, IndexError is raised."""
    from api.services.model_router import _vllm_chat

    data = {"choices": [], "usage": {"prompt_tokens": 0, "completion_tokens": 0}, "model": "m"}
    mock_client = _make_mock_client(data)

    with patch("api.config.settings.VLLM_URL", "http://vllm:8000"):
        with pytest.raises(IndexError):
            await _vllm_chat(
                messages=[{"role": "user", "content": "test"}],
                model="m",
                client=mock_client,
            )


# ---------------------------------------------------------------------------
# Backend routing via chat_completion -- configuration gates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backend_routing_selects_vllm_when_configured():
    """chat_completion calls _vllm_chat when backend='vllm' and VLLM_URL is set."""
    from api.services.model_router import chat_completion

    data = _make_vllm_response("from vllm")
    mock_client = _make_mock_client(data)

    with patch("api.config.settings.INFERENCE_BACKEND", "vllm"), \
         patch("api.config.settings.VLLM_URL", "http://vllm:8000"):
        result = await chat_completion(
            messages=[{"role": "user", "content": "hello"}],
            model="mistral-7b",
            stream=False,
            http_client=mock_client,
        )

    # vLLM response contains "choices" key internally, but content is normalised
    assert result["content"] == "from vllm"


@pytest.mark.asyncio
async def test_backend_routing_falls_back_to_ollama_when_vllm_url_empty():
    """chat_completion falls back to Ollama when INFERENCE_BACKEND='vllm' but VLLM_URL=''."""
    from api.services.model_router import chat_completion

    data = _make_ollama_response("ollama fallback")
    mock_client = _make_mock_client(data)

    with patch("api.config.settings.INFERENCE_BACKEND", "vllm"), \
         patch("api.config.settings.VLLM_URL", ""), \
         patch("api.config.settings.OLLAMA_URL", "http://ollama:11434"):
        result = await chat_completion(
            messages=[{"role": "user", "content": "hi"}],
            model="llama3.2:3b",
            stream=False,
            http_client=mock_client,
        )

    assert result["content"] == "ollama fallback"


@pytest.mark.asyncio
async def test_backend_routing_selects_openai_when_configured():
    """chat_completion routes to OpenAI when backend='openai' and API key is set."""
    from api.services.model_router import chat_completion

    openai_data = {
        "choices": [{"message": {"content": "from openai"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 2},
        "model": "gpt-4o-mini",
    }
    mock_client = _make_mock_client(openai_data)

    with patch("api.config.settings.INFERENCE_BACKEND", "openai"), \
         patch("api.config.settings.OPENAI_API_KEY", "sk-test-key"), \
         patch("api.config.settings.OPENAI_BASE_URL", "https://api.openai.com/v1"):
        result = await chat_completion(
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-4o-mini",
            stream=False,
            http_client=mock_client,
        )

    assert result["content"] == "from openai"
    assert result["model"] == "gpt-4o-mini"


# ---------------------------------------------------------------------------
# vLLM streaming -- _vllm_chat_stream
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_vllm_stream_yields_content_and_done():
    """_vllm_chat_stream yields content chunks then a final done chunk."""
    from api.services.model_router import _vllm_chat_stream

    sse_lines = [
        'data: {"choices": [{"delta": {"content": "vllm"}}], "usage": null}',
        'data: {"choices": [{"delta": {"content": " chunk"}}], "usage": null}',
        'data: {"choices": [{"delta": {}}], "usage": {"prompt_tokens": 4, "completion_tokens": 2}}',
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

    with patch("api.config.settings.VLLM_URL", "http://vllm:8000"):
        chunks = []
        async for chunk in _vllm_chat_stream(
            [{"role": "user", "content": "hi"}],
            "mistral-7b",
            mock_client,
        ):
            chunks.append(chunk)

    content_chunks = [c for c in chunks if c.get("type") == "content"]
    done_chunks = [c for c in chunks if c.get("type") == "done"]

    assert len(content_chunks) == 2
    assert content_chunks[0]["content"] == "vllm"
    assert content_chunks[1]["content"] == " chunk"
    assert len(done_chunks) == 1
    assert done_chunks[0]["prompt_tokens"] == 4
    assert done_chunks[0]["completion_tokens"] == 2


@pytest.mark.asyncio
async def test_vllm_stream_skips_non_data_lines():
    """_vllm_chat_stream ignores lines that do not start with 'data: '."""
    from api.services.model_router import _vllm_chat_stream

    sse_lines = [
        "",  # blank line
        ": keep-alive",  # comment line
        'data: {"choices": [{"delta": {"content": "hello"}}], "usage": null}',
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

    with patch("api.config.settings.VLLM_URL", "http://vllm:8000"):
        chunks = []
        async for chunk in _vllm_chat_stream(
            [{"role": "user", "content": "test"}],
            "mistral-7b",
            mock_client,
        ):
            chunks.append(chunk)

    content_chunks = [c for c in chunks if c.get("type") == "content"]
    assert len(content_chunks) == 1
    assert content_chunks[0]["content"] == "hello"


# ---------------------------------------------------------------------------
# Ollama streaming -- _ollama_chat_stream
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ollama_stream_yields_content_and_done():
    """_ollama_chat_stream yields content chunks and a terminal done chunk."""
    from api.services.model_router import _ollama_chat_stream

    stream_lines = [
        '{"message": {"content": "Hello"}, "done": false}',
        '{"message": {"content": " world"}, "done": false}',
        '{"message": {"content": ""}, "done": true, "prompt_eval_count": 6, "eval_count": 2}',
    ]

    async def _aiter_lines():
        for line in stream_lines:
            yield line

    mock_response = MagicMock()
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)
    mock_response.aiter_lines = _aiter_lines

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.stream = MagicMock(return_value=mock_response)

    with patch("api.config.settings.OLLAMA_URL", "http://ollama:11434"):
        chunks = []
        async for chunk in _ollama_chat_stream(
            [{"role": "user", "content": "hi"}],
            "llama3.2:3b",
            mock_client,
        ):
            chunks.append(chunk)

    content_chunks = [c for c in chunks if c.get("type") == "content"]
    done_chunks = [c for c in chunks if c.get("type") == "done"]

    assert len(content_chunks) == 2
    assert content_chunks[0]["content"] == "Hello"
    assert content_chunks[1]["content"] == " world"
    assert len(done_chunks) == 1
    assert done_chunks[0]["prompt_tokens"] == 6
    assert done_chunks[0]["completion_tokens"] == 2
