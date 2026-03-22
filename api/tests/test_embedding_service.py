"""Tests for the embedding service -- cache integration and Ollama calls."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ollama_response(embedding: list) -> MagicMock:
    """Build a mock httpx.Response that returns an Ollama-style embedding body."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"embedding": embedding}
    resp.raise_for_status = MagicMock()
    return resp


def _make_mock_client(embedding: list) -> AsyncMock:
    """Build a mock httpx.AsyncClient whose post() returns the given embedding."""
    import httpx

    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=_make_ollama_response(embedding))
    return client


# ---------------------------------------------------------------------------
# Cache-disabled path: always hits Ollama
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_embedding_calls_ollama():
    """When cache is unavailable (_redis=None), calls Ollama and returns embedding."""
    mock_client = _make_mock_client([0.1, 0.2, 0.3])

    with patch("api.services.embedding._redis", None):
        from api.services.embedding import generate_embedding

        result = await generate_embedding("hello", client=mock_client)

    assert result == [0.1, 0.2, 0.3]
    mock_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_generate_embedding_posts_to_ollama_url():
    """The Ollama POST target must include /api/embeddings."""
    mock_client = _make_mock_client([0.9, 0.8])

    with patch("api.services.embedding._redis", None):
        from api.services.embedding import generate_embedding

        await generate_embedding("url check", client=mock_client)

    call_args = mock_client.post.call_args
    url = call_args.args[0] if call_args.args else call_args.kwargs.get("url", "")
    assert "/api/embeddings" in url


@pytest.mark.asyncio
async def test_generate_embedding_sends_model_and_prompt():
    """The POST body must include 'model' and 'prompt' keys."""
    mock_client = _make_mock_client([1.0])

    with patch("api.services.embedding._redis", None):
        from api.services.embedding import generate_embedding

        await generate_embedding("test prompt", client=mock_client)

    call_kwargs = mock_client.post.call_args.kwargs
    json_body = call_kwargs.get("json", {})
    assert "model" in json_body
    assert json_body["prompt"] == "test prompt"


# ---------------------------------------------------------------------------
# Cache hit: Ollama is skipped
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_hit_skips_ollama():
    """When embedding is cached in Redis, Ollama must not be called."""
    import httpx

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=json.dumps([0.5, 0.6]).encode())
    mock_client = AsyncMock(spec=httpx.AsyncClient)

    with patch("api.services.embedding._redis", mock_redis):
        from api.services.embedding import generate_embedding

        result = await generate_embedding("cached text", client=mock_client)

    assert result == [0.5, 0.6]
    mock_client.post.assert_not_called()


@pytest.mark.asyncio
async def test_cache_hit_returns_correct_values():
    """Cached values are JSON-decoded and returned exactly as stored."""
    import httpx

    stored = [0.11, 0.22, 0.33, 0.44]
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=json.dumps(stored).encode())
    mock_client = AsyncMock(spec=httpx.AsyncClient)

    with patch("api.services.embedding._redis", mock_redis):
        from api.services.embedding import generate_embedding

        result = await generate_embedding("some text", client=mock_client)

    assert result == stored


# ---------------------------------------------------------------------------
# Cache miss: result stored in Redis after Ollama call
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_miss_stores_result():
    """On cache miss, result is stored via Redis.setex after Ollama call."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()

    mock_client = _make_mock_client([0.3, 0.4])

    with patch("api.services.embedding._redis", mock_redis):
        from api.services.embedding import generate_embedding

        result = await generate_embedding("new text", client=mock_client)

    assert result == [0.3, 0.4]
    mock_redis.setex.assert_called_once()


@pytest.mark.asyncio
async def test_cache_miss_stores_json_encoded_embedding():
    """The value stored in Redis is a JSON-encoded list, not raw floats."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()

    mock_client = _make_mock_client([0.7, 0.8, 0.9])

    with patch("api.services.embedding._redis", mock_redis):
        from api.services.embedding import generate_embedding

        await generate_embedding("store test", client=mock_client)

    # Third positional arg to setex is the value
    call_args = mock_redis.setex.call_args
    stored_value = call_args.args[2] if len(call_args.args) >= 3 else call_args.kwargs.get("value")
    decoded = json.loads(stored_value)
    assert decoded == [0.7, 0.8, 0.9]


@pytest.mark.asyncio
async def test_cache_miss_uses_configured_ttl():
    """The TTL passed to setex must match settings.EMBEDDING_CACHE_TTL."""
    from api.config import settings

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()

    mock_client = _make_mock_client([0.1])

    with patch("api.services.embedding._redis", mock_redis):
        from api.services.embedding import generate_embedding

        await generate_embedding("ttl test", client=mock_client)

    call_args = mock_redis.setex.call_args
    # setex(key, ttl, value) -- second positional arg is TTL
    ttl = call_args.args[1] if len(call_args.args) >= 2 else call_args.kwargs.get("time")
    assert ttl == settings.EMBEDDING_CACHE_TTL


# ---------------------------------------------------------------------------
# Redis error resilience: errors must not surface to callers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_redis_get_error_falls_through_to_ollama():
    """If Redis.get raises, embedding generation continues via Ollama."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(side_effect=ConnectionError("redis down"))

    mock_client = _make_mock_client([0.5])

    with patch("api.services.embedding._redis", mock_redis):
        from api.services.embedding import generate_embedding

        result = await generate_embedding("resilience", client=mock_client)

    assert result == [0.5]
    mock_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_redis_setex_error_does_not_raise():
    """If Redis.setex raises after a successful Ollama call, no exception surfaces."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock(side_effect=ConnectionError("redis down"))

    mock_client = _make_mock_client([0.6])

    with patch("api.services.embedding._redis", mock_redis):
        from api.services.embedding import generate_embedding

        result = await generate_embedding("write error test", client=mock_client)

    # Must return the embedding even though caching failed
    assert result == [0.6]


# ---------------------------------------------------------------------------
# Cache key isolation: different texts produce different keys
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_keys_differ_for_different_texts():
    """Distinct texts must query different Redis keys."""
    import httpx

    captured_keys: list = []

    async def _get(key):
        captured_keys.append(key)
        return json.dumps([0.0]).encode()

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(side_effect=_get)
    mock_client = AsyncMock(spec=httpx.AsyncClient)

    with patch("api.services.embedding._redis", mock_redis):
        from api.services.embedding import generate_embedding

        await generate_embedding("text one", client=mock_client)
        await generate_embedding("text two", client=mock_client)

    assert len(captured_keys) == 2
    assert captured_keys[0] != captured_keys[1]
