"""Shared test fixtures for the Manic AI API test suite."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture()
def mock_db_pool():
    """Mock asyncpg connection pool.

    Provides a pool whose ``acquire()`` context manager yields a mock
    connection with ``fetch``, ``fetchval``, ``fetchrow``, and ``execute``
    methods that return empty defaults.
    """
    pool = AsyncMock()
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=None)
    conn.fetchrow = AsyncMock(return_value=None)
    conn.execute = AsyncMock(return_value="OK")

    # pool.acquire() is an async context manager
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool


@pytest.fixture()
def mock_http_client():
    """Mock httpx.AsyncClient for outbound HTTP calls."""
    client = AsyncMock(spec=httpx.AsyncClient)
    # Default: successful JSON response
    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json.return_value = {}
    response.raise_for_status = MagicMock()
    client.get = AsyncMock(return_value=response)
    client.post = AsyncMock(return_value=response)
    return client


@pytest.fixture()
def mock_redis():
    """Mock Redis cache repository."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=True)
    return redis


@pytest.fixture()
def app(mock_db_pool, mock_http_client, mock_redis) -> FastAPI:
    """Create a FastAPI app with mocked dependencies injected via app.state.

    Skips the real lifespan (no DB connections, no Ollama, no Redis).
    """
    from api.app import create_app

    # Patch the lifespan so startup/shutdown don't run real connections
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _noop_lifespan(app: FastAPI):
        yield

    with patch("api.app.lifespan", _noop_lifespan):
        test_app = create_app()

    # Inject mocked resources onto app.state
    test_app.state.db_pool = mock_db_pool
    test_app.state.http_client = mock_http_client
    test_app.state.redis_cache = mock_redis
    test_app.state.langfuse = None

    return test_app


@pytest_asyncio.fixture()
async def client(app: FastAPI) -> AsyncClient:
    """Async HTTP test client wired to the test FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
