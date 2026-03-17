import httpx
from typing import Optional

_client: Optional[httpx.AsyncClient] = None


async def init_client():
    global _client
    _client = httpx.AsyncClient(timeout=60.0)


async def close_client():
    global _client
    if _client:
        await _client.aclose()
        _client = None


def get_client() -> httpx.AsyncClient:
    if _client is None:
        raise RuntimeError("HTTP client not initialized")
    return _client
