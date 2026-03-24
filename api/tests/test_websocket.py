"""Tests for the /ws/status WebSocket endpoint."""

from unittest.mock import AsyncMock, MagicMock

import httpx
from starlette.testclient import TestClient

from api.dependencies import get_http_client, get_db_optional


def _make_mock_response():
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    return resp


def test_websocket_status_connects(app):
    """WebSocket endpoint accepts connections and sends a status snapshot."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=_make_mock_response())

    app.dependency_overrides[get_http_client] = lambda: mock_client
    app.dependency_overrides[get_db_optional] = lambda: None

    try:
        client = TestClient(app)
        with client.websocket_connect("/ws/status") as ws:
            data = ws.receive_json()
            assert "timestamp" in data
            assert "services" in data
    finally:
        app.dependency_overrides.clear()


def test_websocket_status_service_keys(app):
    """Status snapshot contains the expected service keys."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=_make_mock_response())

    app.dependency_overrides[get_http_client] = lambda: mock_client
    app.dependency_overrides[get_db_optional] = lambda: None

    try:
        client = TestClient(app)
        with client.websocket_connect("/ws/status") as ws:
            data = ws.receive_json()
            services = data["services"]
            assert "ollama" in services
            assert "database" in services
            assert "qdrant" in services
            assert "searxng" in services
            assert "langfuse" in services
    finally:
        app.dependency_overrides.clear()


def test_websocket_ping_pong(app):
    """Client can send a ping and receive a pong response."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=_make_mock_response())

    app.dependency_overrides[get_http_client] = lambda: mock_client
    app.dependency_overrides[get_db_optional] = lambda: None

    try:
        client = TestClient(app)
        with client.websocket_connect("/ws/status") as ws:
            ws.receive_json()  # consume initial snapshot
            ws.send_text("ping")
            reply = ws.receive_json()
            assert reply == {"type": "pong"}
    finally:
        app.dependency_overrides.clear()
