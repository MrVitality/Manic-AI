"""Tests for the /health endpoint."""

import pytest
from unittest.mock import AsyncMock, MagicMock

import httpx


@pytest.mark.asyncio
async def test_health_returns_200(client, mock_http_client):
    """GET /health should return 200 with an envelope containing service info."""
    # Mock the Ollama check_service call to return a healthy status
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
    assert "services" in body["data"]
    assert "config" in body["data"]


@pytest.mark.asyncio
async def test_health_includes_config(client, mock_http_client):
    """GET /health should return model configuration details."""
    ollama_response = MagicMock(spec=httpx.Response)
    ollama_response.status_code = 200
    ollama_response.raise_for_status = MagicMock()
    mock_http_client.get = AsyncMock(return_value=ollama_response)

    response = await client.get("/health")

    body = response.json()
    config = body["data"]["config"]
    assert "chat_model" in config
    assert "embedding_model" in config
    assert "vector_dimension" in config


@pytest.mark.asyncio
async def test_health_reports_db_status(client, mock_db_pool, mock_http_client):
    """GET /health should report database connection status."""
    ollama_response = MagicMock(spec=httpx.Response)
    ollama_response.status_code = 200
    ollama_response.raise_for_status = MagicMock()
    mock_http_client.get = AsyncMock(return_value=ollama_response)

    response = await client.get("/health")

    body = response.json()
    # mock_db_pool is truthy, so DB should be "connected"
    assert body["data"]["services"]["database"] == "connected"
