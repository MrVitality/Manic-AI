"""Tests for RAG service utility functions."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from api.services.rag import check_service


@pytest.mark.asyncio
async def test_check_service_healthy():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    resp = MagicMock()
    resp.status_code = 200
    mock_client.get = AsyncMock(return_value=resp)
    result = await check_service("http://test:8080/health", mock_client)
    assert result["status"] == "healthy"
    assert result["latency_ms"] is not None


@pytest.mark.asyncio
async def test_check_service_degraded():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    resp = MagicMock()
    resp.status_code = 503
    mock_client.get = AsyncMock(return_value=resp)
    result = await check_service("http://test:8080/health", mock_client)
    assert result["status"] == "degraded"


@pytest.mark.asyncio
async def test_check_service_offline():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("unreachable"))
    result = await check_service("http://test:8080/health", mock_client)
    assert result["status"] == "offline"
    assert result["latency_ms"] is None
