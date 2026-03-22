"""Tests for the /health endpoint."""

import pytest
from unittest.mock import AsyncMock, MagicMock

import httpx


@pytest.mark.asyncio
async def test_health_returns_200(client, mock_http_client):
    """GET /health should return 200 with minimal status info (no config leak)."""
    ollama_response = MagicMock(spec=httpx.Response)
    ollama_response.status_code = 200
    ollama_response.raise_for_status = MagicMock()
    mock_http_client.get = AsyncMock(return_value=ollama_response)

    response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "healthy"
    assert "timestamp" in body["data"]
    # Security: /health must NOT expose internal config or service details
    assert "services" not in body["data"]
    assert "config" not in body["data"]
    assert "auth_enabled" not in body["data"]


@pytest.mark.asyncio
async def test_health_no_config_leak(client, mock_http_client):
    """GET /health must not expose model names or auth status."""
    ollama_response = MagicMock(spec=httpx.Response)
    ollama_response.status_code = 200
    ollama_response.raise_for_status = MagicMock()
    mock_http_client.get = AsyncMock(return_value=ollama_response)

    response = await client.get("/health")

    body = response.json()
    data = body["data"]
    # None of these internal details should be in the public health check
    assert "chat_model" not in data
    assert "embedding_model" not in data
    assert "vector_dimension" not in data


@pytest.mark.asyncio
async def test_health_always_returns_200(client, mock_db_pool, mock_http_client):
    """GET /health should always return 200 regardless of service state."""
    ollama_response = MagicMock(spec=httpx.Response)
    ollama_response.status_code = 200
    ollama_response.raise_for_status = MagicMock()
    mock_http_client.get = AsyncMock(return_value=ollama_response)

    response = await client.get("/health")

    body = response.json()
    assert body["data"]["status"] == "healthy"
