"""Tests for analytics endpoints."""

from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_usage_analytics(client):
    resp = await client.get("/v1/analytics/usage")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_usage_invalid_period(client):
    resp = await client.get("/v1/analytics/usage?period=decade")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_model_analytics(client):
    resp = await client.get("/v1/analytics/models")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_rag_analytics(client, app):
    conn = app.state.db_pool._mock_conn
    # rag_analytics calls fetchrow twice (chunk stats + collection stats)
    conn.fetchrow = AsyncMock(side_effect=[
        {"total": 0, "avg_tokens": 0, "total_tokens": 0},
        {"total": 0, "avg_docs": 0},
    ])
    resp = await client.get("/v1/analytics/rag")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_services_history(client):
    resp = await client.get("/v1/analytics/services/history")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_services_history_hours_out_of_range(client):
    resp = await client.get("/v1/analytics/services/history?hours=200")
    assert resp.status_code == 422
