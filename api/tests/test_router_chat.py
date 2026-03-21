"""Tests for chat endpoints."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest


@pytest.mark.asyncio
async def test_chat_200(client):
    with patch("api.services.chat.routed_chat_completion", new_callable=AsyncMock) as mock_cc:
        mock_cc.return_value = {
            "content": "hi there",
            "prompt_tokens": 5,
            "completion_tokens": 3,
            "model": "test-model",
            "raw": {},
        }
        resp = await client.post(
            "/v1/chat",
            json={"messages": [{"role": "user", "content": "hello"}]},
        )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_chat_502_on_http_error(client):
    with patch("api.services.chat.routed_chat_completion", new_callable=AsyncMock) as mock_cc:
        mock_cc.side_effect = httpx.HTTPError("connection refused")
        resp = await client.post(
            "/v1/chat",
            json={"messages": [{"role": "user", "content": "hello"}]},
        )
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_chat_validates_role(client):
    resp = await client.post(
        "/v1/chat",
        json={"messages": [{"role": "invalid_role", "content": "hi"}]},
    )
    assert resp.status_code == 422
