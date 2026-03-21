"""Tests for API key authentication in auth.py."""

import pytest


@pytest.mark.asyncio
async def test_auth_disabled_allows_requests(client):
    """Default test app has no API_SECRET_KEY — auth is bypassed."""
    response = await client.get("/v1/system/info")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_auth_enabled_valid_key(auth_client):
    response = await auth_client.get(
        "/v1/system/info",
        headers={"X-API-Key": "test-secret"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_auth_enabled_wrong_key(auth_client):
    response = await auth_client.get(
        "/v1/system/info",
        headers={"X-API-Key": "wrong-key"},
    )
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_auth_enabled_missing_key(auth_client):
    response = await auth_client.get("/v1/system/info")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_auth_enabled_empty_key(auth_client):
    response = await auth_client.get(
        "/v1/system/info",
        headers={"X-API-Key": ""},
    )
    assert response.status_code == 401
