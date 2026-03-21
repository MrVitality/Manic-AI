"""Integration tests for global exception handlers via the app."""

from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_http_exception_returns_envelope(client, app):
    """Trigger a real HTTPException (document not found) and check envelope."""
    conn = app.state.db_pool._mock_conn
    conn.execute = AsyncMock(return_value="DELETE 0")
    resp = await client.delete("/v1/documents/missing-id")
    assert resp.status_code == 404
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == "Document not found"


@pytest.mark.asyncio
async def test_validation_error_returns_422(client):
    resp = await client.post(
        "/v1/chat",
        json={"messages": "not-a-list"},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "validation_error"
    assert isinstance(body["error"]["details"], list)
    assert len(body["error"]["details"]) > 0


@pytest.mark.asyncio
async def test_validation_details_have_fields(client):
    resp = await client.post(
        "/v1/chat",
        json={"messages": "not-a-list"},
    )
    body = resp.json()
    detail = body["error"]["details"][0]
    assert "field" in detail
    assert "message" in detail
    assert "code" in detail
