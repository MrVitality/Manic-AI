"""Tests for api/services/cache.py."""

import json
from unittest.mock import AsyncMock

import pytest

from api.services.cache import get_cached, set_cached


# ---------------------------------------------------------------------------
# get_cached
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_cached_returns_parsed_json_on_hit():
    """get_cached deserialises cached JSON and returns the Python object."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=json.dumps({"answer": 42}))

    result = await get_cached(redis, "my-key")

    assert result == {"answer": 42}
    redis.get.assert_called_once_with("my-key")


@pytest.mark.asyncio
async def test_get_cached_returns_none_on_miss():
    """get_cached returns None when the key is absent from Redis."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)

    result = await get_cached(redis, "missing-key")

    assert result is None


@pytest.mark.asyncio
async def test_get_cached_returns_none_when_redis_is_none():
    """get_cached returns None immediately when no Redis client is provided."""
    result = await get_cached(None, "any-key")

    assert result is None


@pytest.mark.asyncio
async def test_get_cached_returns_none_on_invalid_json():
    """get_cached returns None (and logs) when stored value is not valid JSON."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value="not-valid-json{{{{")

    result = await get_cached(redis, "bad-json-key")

    assert result is None


@pytest.mark.asyncio
async def test_get_cached_returns_list_value():
    """get_cached correctly deserialises a JSON array."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=json.dumps([1, 2, 3]))

    result = await get_cached(redis, "list-key")

    assert result == [1, 2, 3]


# ---------------------------------------------------------------------------
# set_cached
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_cached_stores_json_with_ttl():
    """set_cached serialises data to JSON and calls setex with TTL."""
    redis = AsyncMock()
    redis.setex = AsyncMock()

    data = {"result": "value", "count": 5}
    await set_cached(redis, "store-key", data, ttl=120)

    redis.setex.assert_called_once()
    call_args = redis.setex.call_args[0]
    assert call_args[0] == "store-key"
    assert call_args[1] == 120
    # Third arg should be a valid JSON string matching data
    stored = json.loads(call_args[2])
    assert stored == data


@pytest.mark.asyncio
async def test_set_cached_does_nothing_when_redis_is_none():
    """set_cached is a no-op when redis=None."""
    # Should not raise
    await set_cached(None, "key", {"x": 1}, ttl=60)


@pytest.mark.asyncio
async def test_set_cached_uses_default_ttl():
    """set_cached defaults to 60 seconds TTL."""
    redis = AsyncMock()
    redis.setex = AsyncMock()

    await set_cached(redis, "ttl-key", "data")

    call_args = redis.setex.call_args[0]
    assert call_args[1] == 60
