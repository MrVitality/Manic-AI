"""Tests for search endpoints."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_search_returns_200(client):
    with patch("api.routers.search.generate_embedding", new_callable=AsyncMock) as mock_emb, \
         patch("api.routers.search.unified_search", new_callable=AsyncMock) as mock_search:
        mock_emb.return_value = [0.1] * 5
        mock_search.return_value = []
        resp = await client.post("/v1/search", json={"query": "test query"})
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_search_explain_returns_200(client):
    with patch("api.routers.search.generate_embedding", new_callable=AsyncMock) as mock_emb, \
         patch("api.routers.search.search_with_explain", new_callable=AsyncMock) as mock_explain:
        mock_emb.return_value = [0.1] * 5
        mock_explain.return_value = {"results": [], "query_embedding_preview": []}
        resp = await client.post("/v1/search/explain", json={"query": "test"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_search_missing_query(client):
    resp = await client.post("/v1/search", json={})
    assert resp.status_code == 422
