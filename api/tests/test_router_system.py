"""Tests for system administration endpoints."""

import pytest


@pytest.mark.asyncio
async def test_system_info(client):
    resp = await client.get("/v1/system/info")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["version"] == "2.0.0"
    assert "uptime_seconds" in body["data"]
    assert "config" in body["data"]


@pytest.mark.asyncio
async def test_system_info_no_db(client, app):
    app.state.db_pool = None
    resp = await client.get("/v1/system/info")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["database"]["pool_size"] == 0


@pytest.mark.asyncio
async def test_cache_clear_no_redis(client, app):
    app.state.redis_cache = None
    resp = await client.post("/v1/system/cache/clear")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["cleared"] is False


@pytest.mark.asyncio
async def test_cache_clear_with_redis(client, app):
    app.state.redis_cache.delete_pattern = lambda p: 5  # sync mock
    from unittest.mock import AsyncMock
    app.state.redis_cache.delete_pattern = AsyncMock(return_value=5)
    resp = await client.post("/v1/system/cache/clear")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["cleared"] is True
    assert body["data"]["keys_removed"] == 5


@pytest.mark.asyncio
async def test_rag_stats_no_db(client, app):
    app.state.db_pool = None
    resp = await client.get("/v1/rag/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["total_documents"] == 0


@pytest.mark.asyncio
async def test_chunks_requires_db(client, app):
    app.state.db_pool = None
    resp = await client.get("/v1/documents/some-id/chunks")
    assert resp.status_code == 503
