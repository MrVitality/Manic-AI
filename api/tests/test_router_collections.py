"""Tests for collection endpoints."""

from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_list_collections_empty(client):
    resp = await client.get("/v1/collections")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"] == []


@pytest.mark.asyncio
async def test_create_collection(client):
    resp = await client.post("/v1/collections", json={"name": "test-col"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["name"] == "test-col"
    assert "id" in body["data"]


@pytest.mark.asyncio
async def test_create_collection_empty_name(client):
    resp = await client.post("/v1/collections", json={"name": ""})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_collection_success(client, app):
    conn = app.state.db_pool._mock_conn
    conn.execute = AsyncMock(return_value="DELETE 1")
    resp = await client.delete("/v1/collections/some-id")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["status"] == "deleted"


@pytest.mark.asyncio
async def test_delete_collection_not_found(client, app):
    conn = app.state.db_pool._mock_conn
    conn.execute = AsyncMock(return_value="DELETE 0")
    resp = await client.delete("/v1/collections/missing")
    assert resp.status_code == 404
