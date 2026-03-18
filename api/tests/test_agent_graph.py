"""Tests for agent_graph — Redis state persistence and TTL."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.services.agent_graph import _save_state, _load_state


@pytest.mark.asyncio
async def test_save_state_uses_configured_ttl():
    """_save_state must use AGENT_STATE_TTL_SECONDS from settings."""
    mock_redis = AsyncMock()
    mock_redis.setex = AsyncMock()

    with patch("api.services.agent_graph._get_redis", return_value=mock_redis):
        with patch("api.config.settings.AGENT_STATE_TTL_SECONDS", 7200):
            await _save_state("run-123", {"status": "running"})

    mock_redis.setex.assert_called_once()
    call_args = mock_redis.setex.call_args
    key, ttl, _ = call_args.args
    assert key == "agent:run:run-123"
    assert ttl == 7200, f"Expected TTL 7200, got {ttl}"


@pytest.mark.asyncio
async def test_save_state_default_ttl_is_24h():
    """Default AGENT_STATE_TTL_SECONDS should be 86400 (24 hours)."""
    from api.config import settings

    assert settings.AGENT_STATE_TTL_SECONDS == 86400


@pytest.mark.asyncio
async def test_load_state_returns_none_when_redis_unavailable():
    """_load_state returns None gracefully when Redis is not configured."""
    with patch("api.services.agent_graph._get_redis", return_value=None):
        result = await _load_state("run-abc")
    assert result is None


@pytest.mark.asyncio
async def test_load_state_returns_parsed_state():
    """_load_state deserializes JSON from Redis."""
    state = {"status": "completed", "answer": "42"}
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=json.dumps(state))

    with patch("api.services.agent_graph._get_redis", return_value=mock_redis):
        result = await _load_state("run-xyz")

    assert result == state
