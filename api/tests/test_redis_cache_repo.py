"""Tests for Redis cache repository."""

from unittest.mock import AsyncMock

import pytest

from api.repositories.redis_cache import RedisCacheRepository


@pytest.mark.asyncio
async def test_get_returns_value():
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=b"hello")
    repo = RedisCacheRepository(mock_redis)
    result = await repo.get("key")
    assert result == b"hello"


@pytest.mark.asyncio
async def test_get_returns_none_on_exception():
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(side_effect=Exception("timeout"))
    repo = RedisCacheRepository(mock_redis)
    result = await repo.get("key")
    assert result is None


@pytest.mark.asyncio
async def test_setex_calls_redis():
    mock_redis = AsyncMock()
    mock_redis.setex = AsyncMock()
    repo = RedisCacheRepository(mock_redis)
    await repo.setex("key", 3600, "val")
    mock_redis.setex.assert_called_once_with("key", 3600, "val")


@pytest.mark.asyncio
async def test_setex_suppresses_exception():
    mock_redis = AsyncMock()
    mock_redis.setex = AsyncMock(side_effect=Exception("down"))
    repo = RedisCacheRepository(mock_redis)
    await repo.setex("key", 60, "val")  # no raise


@pytest.mark.asyncio
async def test_delete_pattern_returns_count():
    mock_redis = AsyncMock()
    mock_redis.keys = AsyncMock(return_value=["k1", "k2"])
    mock_redis.delete = AsyncMock(return_value=2)
    repo = RedisCacheRepository(mock_redis)
    result = await repo.delete_pattern("manic:*")
    assert result == 2


@pytest.mark.asyncio
async def test_delete_pattern_no_keys():
    mock_redis = AsyncMock()
    mock_redis.keys = AsyncMock(return_value=[])
    repo = RedisCacheRepository(mock_redis)
    result = await repo.delete_pattern("manic:*")
    assert result == 0


@pytest.mark.asyncio
async def test_delete_pattern_suppresses_exception():
    mock_redis = AsyncMock()
    mock_redis.keys = AsyncMock(side_effect=Exception("down"))
    repo = RedisCacheRepository(mock_redis)
    result = await repo.delete_pattern("*")
    assert result == 0
