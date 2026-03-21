"""Tests for agent endpoints."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest


@pytest.mark.asyncio
async def test_agent_run_200(client):
    with patch("api.routers.agent.run_agent", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {"run_id": "r1", "status": "completed", "result": "answer"}
        resp = await client.post("/v1/agent/run", json={"query": "test question"})
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_agent_run_502(client):
    with patch("api.routers.agent.run_agent", new_callable=AsyncMock) as mock_run:
        mock_run.side_effect = httpx.HTTPError("down")
        resp = await client.post("/v1/agent/run", json={"query": "test"})
    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "bad_gateway"


@pytest.mark.asyncio
async def test_agent_status_404(client):
    with patch("api.routers.agent.get_run_status", new_callable=AsyncMock) as mock_status:
        mock_status.return_value = None
        resp = await client.get("/v1/agent/unknown/status")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_agent_status_found(client):
    with patch("api.routers.agent.get_run_status", new_callable=AsyncMock) as mock_status:
        mock_status.return_value = {"run_id": "x", "status": "completed"}
        resp = await client.get("/v1/agent/x/status")
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "completed"


@pytest.mark.asyncio
async def test_agent_query_min_length(client):
    resp = await client.post("/v1/agent/run", json={"query": ""})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_agent_query_max_length(client):
    resp = await client.post("/v1/agent/run", json={"query": "x" * 10001})
    assert resp.status_code == 422
