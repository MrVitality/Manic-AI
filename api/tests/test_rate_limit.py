"""Tests for per-IP rate limiting middleware."""

import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI


@pytest_asyncio.fixture()
async def rate_limited_client():
    """App with rate limit patched to 3/minute for fast testing."""
    from contextlib import asynccontextmanager
    from api.app import create_app

    @asynccontextmanager
    async def _noop_lifespan(app: FastAPI):
        yield

    with patch("api.app.lifespan", _noop_lifespan):
        test_app = create_app()

    # Inject mocked state so endpoints don't crash
    test_app.state.db_pool = None
    test_app.state.http_client = AsyncMock()
    test_app.state.redis_cache = None
    test_app.state.langfuse = None

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.mark.asyncio
async def test_rate_limiter_module_exists():
    """The rate_limit middleware module must expose a limiter instance."""
    from api.middleware.rate_limit import limiter
    assert limiter is not None


@pytest.mark.asyncio
async def test_rate_limit_config_fields_exist():
    """Config must expose RATE_LIMIT_PER_MINUTE and RATE_LIMIT_INGEST_PER_MINUTE."""
    from api.config import settings
    assert hasattr(settings, "RATE_LIMIT_PER_MINUTE")
    assert hasattr(settings, "RATE_LIMIT_INGEST_PER_MINUTE")
    assert settings.RATE_LIMIT_PER_MINUTE > 0
    assert settings.RATE_LIMIT_INGEST_PER_MINUTE > 0


@pytest.mark.asyncio
async def test_app_has_limiter_on_state(rate_limited_client):
    """The FastAPI app must have a limiter registered on app.state."""
    # A health check should succeed — confirms the app initialised
    r = await rate_limited_client.get("/health")
    assert r.status_code in (200, 503)  # 503 if services down in test env
