"""Tests for ingest endpoints."""

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_ingest_returns_accepted(client):
    resp = await client.post(
        "/v1/ingest",
        json={"content": "hello world", "filename": "test.txt"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["status"] == "processing"
    assert "document_id" in body["data"]


@pytest.mark.asyncio
async def test_ingest_status_not_found(client, app):
    conn = app.state.db_pool._mock_conn
    conn.fetchrow = AsyncMock(return_value=None)
    # Clear in-memory tracker
    from api.services import ingestion
    ingestion._job_status.clear()
    resp = await client.get("/v1/ingest/unknown-id/status")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_ingest_status_found(client, app):
    conn = app.state.db_pool._mock_conn
    conn.fetchrow = AsyncMock(return_value={
        "document_id": "doc-1",
        "status": "completed",
        "filename": "f.txt",
        "chunks_created": 5,
        "error": None,
        "created_at": None,
        "updated_at": None,
    })
    resp = await client.get("/v1/ingest/doc-1/status")
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "completed"


@pytest.mark.asyncio
async def test_ingest_validates_overlap(client):
    resp = await client.post(
        "/v1/ingest",
        json={"content": "x", "filename": "f.txt", "chunk_size": 100, "chunk_overlap": 100},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_embed_returns_200(client, app):
    http = app.state.http_client
    resp_mock = MagicMock()
    resp_mock.status_code = 200
    resp_mock.json.return_value = {"embedding": [0.1, 0.2, 0.3]}
    resp_mock.raise_for_status = MagicMock()
    http.post = AsyncMock(return_value=resp_mock)
    resp = await client.post("/v1/embed", json={"text": "hello"})
    assert resp.status_code == 200
    assert resp.json()["data"]["dimensions"] == 3
