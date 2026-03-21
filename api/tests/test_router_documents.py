"""Tests for document endpoints."""

from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_list_documents_empty(client):
    resp = await client.get("/v1/documents")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"] == []
    assert body["meta"]["total"] is not None


@pytest.mark.asyncio
async def test_list_documents_with_results(client, app):
    conn = app.state.db_pool._mock_conn
    conn.fetch = AsyncMock(return_value=[{
        "id": "abc-123",
        "filename": "test.txt",
        "content_type": "text/plain",
        "file_size": 100,
        "status": "completed",
        "chunk_count": 3,
        "metadata": "{}",
        "created_at": None,
        "updated_at": None,
    }])
    conn.fetchval = AsyncMock(return_value=1)
    resp = await client.get("/v1/documents")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 1
    assert body["data"][0]["id"] == "abc-123"
    assert body["meta"]["total"] == 1


@pytest.mark.asyncio
async def test_delete_document_success(client, app):
    conn = app.state.db_pool._mock_conn
    conn.execute = AsyncMock(return_value="DELETE 1")
    resp = await client.delete("/v1/documents/some-uuid")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["status"] == "deleted"


@pytest.mark.asyncio
async def test_delete_document_not_found(client, app):
    conn = app.state.db_pool._mock_conn
    conn.execute = AsyncMock(return_value="DELETE 0")
    resp = await client.delete("/v1/documents/missing-id")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "not_found"
