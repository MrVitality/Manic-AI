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
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=0)
    conn.fetchrow = AsyncMock(return_value=None)
    conn.execute = AsyncMock(return_value="OK")

    # Build pool as MagicMock so sync methods (get_size, get_idle_size) work
    pool = MagicMock()
    pool.get_size = MagicMock(return_value=5)
    pool.get_idle_size = MagicMock(return_value=3)

    # pool.acquire() must return a fresh async context manager each call
    # to avoid reentrancy issues with asyncio.gather
    class _AcquireCM:
        async def __aenter__(self):
            return conn
        async def __aexit__(self, *args):
            return False

    pool.acquire = MagicMock(side_effect=lambda: _AcquireCM())
    # Attach conn for test access
    pool._mock_conn = conn
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


@pytest.fixture()
def make_http_response():
    """Factory for building mock httpx.Response objects with custom status/json."""

    def _make(status_code=200, json_body=None):
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = status_code
        resp.json.return_value = json_body or {}
        resp.raise_for_status = MagicMock()
        if status_code >= 400:
            resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                "error", request=MagicMock(), response=resp
            )
        return resp

    return _make


@pytest.fixture()
def app_with_auth(mock_db_pool, mock_http_client, mock_redis) -> FastAPI:
    """App with API_SECRET_KEY='test-secret' for auth enforcement tests."""
    from api.app import create_app
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _noop(app: FastAPI):
        yield

    with patch("api.app.lifespan", _noop):
        test_app = create_app()

    test_app.state.db_pool = mock_db_pool
    test_app.state.http_client = mock_http_client
    test_app.state.redis_cache = mock_redis
    test_app.state.langfuse = None
    return test_app


@pytest_asyncio.fixture()
async def auth_client(app_with_auth: FastAPI) -> AsyncClient:
    """Async HTTP test client with auth enforcement enabled."""
    transport = ASGITransport(app=app_with_auth)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        # Patch _secret_key for the duration of the test
        with patch("api.auth._secret_key", "test-secret"):
            yield ac
