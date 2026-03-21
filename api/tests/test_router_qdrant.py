"""Tests for Qdrant management endpoints."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest


@pytest.mark.asyncio
async def test_list_qdrant_collections(client, app):
    resp_mock = MagicMock()
    resp_mock.status_code = 200
    resp_mock.json.return_value = {"result": {"collections": []}}
    resp_mock.raise_for_status = MagicMock()
    app.state.http_client.get = AsyncMock(return_value=resp_mock)
    resp = await client.get("/v1/qdrant/collections")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_qdrant_502(client, app):
    app.state.http_client.get = AsyncMock(side_effect=httpx.HTTPError("timeout"))
    resp = await client.get("/v1/qdrant/collections")
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_create_qdrant_collection(client, app):
    resp_mock = MagicMock()
    resp_mock.status_code = 200
    resp_mock.json.return_value = {"result": True}
    resp_mock.raise_for_status = MagicMock()
    app.state.http_client.put = AsyncMock(return_value=resp_mock)
    resp = await client.post("/v1/qdrant/collections/test-col")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_qdrant_collection(client, app):
    resp_mock = MagicMock()
    resp_mock.status_code = 200
    resp_mock.json.return_value = {}
    resp_mock.raise_for_status = MagicMock()
    app.state.http_client.delete = AsyncMock(return_value=resp_mock)
    resp = await client.delete("/v1/qdrant/collections/test-col")
    assert resp.status_code == 200
