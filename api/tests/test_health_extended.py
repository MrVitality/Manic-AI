"""Extended tests for /health and /services/status endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


@pytest.fixture(autouse=True)
def _clear_health_cache():
    """Clear the health endpoint cache between tests."""
    from api.routers import health
    if hasattr(health, '_health_cache'):
        health._health_cache["data"] = None
        health._health_cache["expires"] = 0
    yield


def _ok_http_response() -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    return resp


def _err_http_response() -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 503
    resp.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError("down", request=MagicMock(), response=resp)
    )
    return resp


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_returns_auth_enabled_field(client, mock_http_client):
    """GET /health response includes auth_enabled boolean."""
    mock_http_client.get = AsyncMock(return_value=_ok_http_response())

    resp = await client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert "auth_enabled" in body["data"]
    assert isinstance(body["data"]["auth_enabled"], bool)


@pytest.mark.asyncio
async def test_health_includes_timestamp(client, mock_http_client):
    """GET /health includes a UTC ISO timestamp in the response."""
    mock_http_client.get = AsyncMock(return_value=_ok_http_response())

    resp = await client.get("/health")

    assert resp.status_code == 200
    ts = resp.json()["data"]["timestamp"]
    assert ts is not None
    assert "T" in ts  # ISO 8601 format


@pytest.mark.asyncio
async def test_health_ollama_down_still_returns_200(client, mock_http_client):
    """GET /health still returns 200 even when Ollama is unreachable."""
    mock_http_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

    resp = await client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["services"]["ollama"] in ("offline", "healthy", "error", "unknown")


@pytest.mark.asyncio
async def test_health_with_db_disconnected(app, mock_http_client):
    """GET /health reports database as disconnected when pool is None."""
    from httpx import ASGITransport, AsyncClient

    mock_http_client.get = AsyncMock(return_value=_ok_http_response())

    # Temporarily remove the DB pool
    original_pool = app.state.db_pool
    app.state.db_pool = None

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        resp = await ac.get("/health")

    app.state.db_pool = original_pool

    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["services"]["database"] == "disconnected"


# ---------------------------------------------------------------------------
# GET /services/status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_services_status_returns_all_5_services(client, mock_http_client, app):
    """GET /services/status returns entries for all 5 monitored services."""
    mock_http_client.get = AsyncMock(return_value=_ok_http_response())
    # Provide a DB pool with a working connection for the SELECT 1 check
    conn = app.state.db_pool._mock_conn
    conn.fetchval = AsyncMock(return_value=1)

    resp = await client.get("/services/status")

    assert resp.status_code == 200
    services = resp.json()["data"]["services"]
    assert "ollama" in services
    assert "database" in services
    assert "qdrant" in services
    assert "searxng" in services
    assert "langfuse" in services


@pytest.mark.asyncio
async def test_services_status_each_service_has_name_and_status(client, mock_http_client, app):
    """Each service entry in /services/status has 'name' and 'status' keys."""
    mock_http_client.get = AsyncMock(return_value=_ok_http_response())
    conn = app.state.db_pool._mock_conn
    conn.fetchval = AsyncMock(return_value=1)

    resp = await client.get("/services/status")

    assert resp.status_code == 200
    services = resp.json()["data"]["services"]
    for svc_name, svc_data in services.items():
        assert "name" in svc_data, f"'name' missing for {svc_name}"
        assert "status" in svc_data, f"'status' missing for {svc_name}"


# ---------------------------------------------------------------------------
# GET /metrics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_metrics_returns_prometheus_format(client):
    """GET /metrics returns a non-empty Prometheus metrics payload."""
    resp = await client.get("/metrics")

    assert resp.status_code == 200
    # Prometheus metrics always contain the comment char '#'
    assert b"#" in resp.content


@pytest.mark.asyncio
async def test_metrics_content_type_is_correct(client):
    """GET /metrics content-type matches the Prometheus text exposition format."""
    resp = await client.get("/metrics")

    assert resp.status_code == 200
    content_type = resp.headers.get("content-type", "")
    # Prometheus content type starts with text/plain
    assert "text/plain" in content_type or "text/plain" in content_type
