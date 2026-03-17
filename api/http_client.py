"""Shared HTTP client management.

The client is stored on ``app.state.http_client`` at startup and read from
there by DI functions.  The legacy module-level reference is kept for the
background health-logger.
"""

import httpx
from typing import Optional

_client: Optional[httpx.AsyncClient] = None


def _set_client(client: Optional[httpx.AsyncClient]):
    import api.http_client as _mod
    _mod._client = client


async def init_client(*, app=None):
    client = httpx.AsyncClient(timeout=60.0)
    _set_client(client)
    if app is not None:
        app.state.http_client = client
    return client


async def close_client(*, app=None):
    client = _client
    if app is not None:
        client = getattr(app.state, "http_client", client)
    if client:
        await client.aclose()
    _set_client(None)
    if app is not None:
        app.state.http_client = None


def get_client() -> httpx.AsyncClient:
    if _client is None:
        raise RuntimeError("HTTP client not initialized")
    return _client
