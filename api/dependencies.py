"""FastAPI dependency injection functions.

All dependencies read from ``request.app.state`` rather than relying on
mutable module-level globals.  The old ``database.py`` / ``http_client.py`` /
``services/embedding.py`` init/close helpers are still called by the lifespan
handler, but they now store the objects on ``app.state``.
"""

from typing import Optional

import asyncpg
import httpx
from fastapi import HTTPException, Request

from api.repositories.redis_cache import RedisCacheRepository
from api.repositories.supabase_documents import SupabaseDocumentRepository
from api.repositories.supabase_vector import SupabaseVectorRepository
from api.repositories.qdrant_vector import QdrantVectorRepository
from api.config import settings


# ---------------------------------------------------------------------------
# Core resource dependencies
# ---------------------------------------------------------------------------


async def get_db(request: Request) -> asyncpg.Pool:
    """Require a live database pool (503 if unavailable)."""
    pool: Optional[asyncpg.Pool] = getattr(request.app.state, "db_pool", None)
    if not pool:
        raise HTTPException(status_code=503, detail="Database not connected")
    return pool


async def get_db_optional(request: Request) -> Optional[asyncpg.Pool]:
    """Return the database pool or None (no error)."""
    return getattr(request.app.state, "db_pool", None)


async def get_http_client(request: Request) -> httpx.AsyncClient:
    """Return the shared HTTP client."""
    client: Optional[httpx.AsyncClient] = getattr(request.app.state, "http_client", None)
    if client is None:
        raise HTTPException(status_code=503, detail="HTTP client not initialised")
    return client


async def get_redis(request: Request) -> Optional[RedisCacheRepository]:
    """Return the Redis cache repository or None."""
    return getattr(request.app.state, "redis_cache", None)


async def get_langfuse(request: Request):
    """Return the Langfuse client or None."""
    return getattr(request.app.state, "langfuse", None)


# ---------------------------------------------------------------------------
# Repository dependencies
# ---------------------------------------------------------------------------


async def get_document_repo(request: Request) -> SupabaseDocumentRepository:
    pool = await get_db(request)
    return SupabaseDocumentRepository(pool)


async def get_document_repo_optional(request: Request) -> Optional[SupabaseDocumentRepository]:
    pool = await get_db_optional(request)
    if pool is None:
        return None
    return SupabaseDocumentRepository(pool)


async def get_vector_repo(request: Request) -> SupabaseVectorRepository:
    pool = await get_db(request)
    return SupabaseVectorRepository(pool)


async def get_qdrant_repo(request: Request) -> QdrantVectorRepository:
    client = await get_http_client(request)
    return QdrantVectorRepository(settings.QDRANT_URL, client)
