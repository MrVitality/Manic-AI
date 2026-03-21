"""Tests for chat endpoints."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from api.schemas.chat import ChatMessage, ChatResponse


@pytest.mark.asyncio
async def test_chat_200(client):
    mock_response = ChatResponse(
        id="test-id",
        model="test-model",
        message=ChatMessage(role="assistant", content="hi there"),
        sources=[],
        citations=[],
        usage={"prompt_tokens": 5, "completion_tokens": 3},
    )
    with patch("api.routers.chat.complete_chat", new_callable=AsyncMock) as mock_cc:
        mock_cc.return_value = mock_response
        resp = await client.post(
            "/v1/chat",
            json={"messages": [{"role": "user", "content": "hello"}]},
        )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_chat_502_on_http_error(client):
    with patch("api.routers.chat.complete_chat", new_callable=AsyncMock) as mock_cc:
        mock_cc.side_effect = httpx.HTTPError("connection refused")
        resp = await client.post(
            "/v1/chat",
            json={"messages": [{"role": "user", "content": "hello"}]},
        )
    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "bad_gateway"


@pytest.mark.asyncio
async def test_chat_validates_role(client):
    resp = await client.post(
        "/v1/chat",
        json={"messages": [{"role": "invalid_role", "content": "hi"}]},
    )
    assert resp.status_code == 422
