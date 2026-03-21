"""Tests for HTTP middleware (security headers, request ID, metrics)."""

import pytest


@pytest.mark.asyncio
async def test_security_headers_present(client):
    resp = await client.get("/health")
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"
    assert "referrer-policy" in resp.headers


@pytest.mark.asyncio
async def test_request_id_generated(client):
    resp = await client.get("/health")
    rid = resp.headers.get("x-request-id")
    assert rid and len(rid) > 0


@pytest.mark.asyncio
async def test_request_id_preserved(client):
    resp = await client.get("/health", headers={"X-Request-ID": "my-test-id"})
    assert resp.headers["x-request-id"] == "my-test-id"


@pytest.mark.asyncio
async def test_response_time_header(client):
    resp = await client.get("/health")
    assert float(resp.headers["x-response-time-ms"]) >= 0
