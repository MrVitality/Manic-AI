import asyncio
import logging
import os
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.auth import require_api_key
from api.config import SUPABASE_DB_URL

from api.database import init_pool, close_pool
from api.http_client import init_client, close_client
from api.services.embedding import init_redis
from api.services.langfuse import init_langfuse
from api.services.health_logger import health_log_loop

# Import all routers
from api.routers import health, chat, ingest, documents, collections, qdrant, search, analytics, system, models

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_pool(SUPABASE_DB_URL)
    await init_client()
    await init_redis()
    init_langfuse()
    await _run_ddl()
    health_task = asyncio.create_task(health_log_loop())

    yield  # app runs

    # Shutdown
    health_task.cancel()
    try:
        await health_task
    except asyncio.CancelledError:
        pass
    await close_pool()
    await close_client()


async def _run_ddl():
    """Create required tables if they don't exist. Run once at startup."""
    from api.database import get_db_optional
    db = get_db_optional()
    if not db:
        return
    async with db.acquire() as conn:
        # chat_log table for real analytics
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS public.chat_log (
                id BIGSERIAL PRIMARY KEY,
                model TEXT NOT NULL,
                prompt_tokens INT NOT NULL DEFAULT 0,
                completion_tokens INT NOT NULL DEFAULT 0,
                total_tokens INT NOT NULL DEFAULT 0,
                latency_ms FLOAT NOT NULL DEFAULT 0,
                has_rag BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        # service_health_log for services history analytics
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS public.service_health_log (
                id BIGSERIAL PRIMARY KEY,
                service_name TEXT NOT NULL,
                status TEXT NOT NULL,
                latency_ms FLOAT,
                checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)


def _parse_cors_origins() -> list[str]:
    """Read allowed CORS origins from CORS_ORIGINS env var (comma-separated).

    Falls back to localhost defaults for local development.
    """
    raw = os.getenv("CORS_ORIGINS", "").strip()
    if raw:
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    logger.warning(
        "CORS_ORIGINS is not set — defaulting to localhost origins. "
        "Set this environment variable in production."
    )
    return ["http://localhost:3000", "http://localhost:3006"]


def create_app() -> FastAPI:
    app = FastAPI(
        title="Manic AI API",
        version="2.0.0",
        lifespan=lifespan,
    )

    # --- CORS configuration (secure defaults) ---
    cors_origins = _parse_cors_origins()
    allow_credentials = "*" not in cors_origins
    if not allow_credentials:
        logger.warning(
            "CORS allow_origins contains wildcard '*' — "
            "allow_credentials has been forced to False."
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Authentication dependency applied globally ---
    # Health router is public (needed for uptime checks / load balancers).
    app.include_router(health.router)

    # All other routers require API key authentication.
    auth_dep = [Depends(require_api_key)]
    app.include_router(chat.router, dependencies=auth_dep)
    app.include_router(ingest.router, dependencies=auth_dep)
    app.include_router(documents.router, dependencies=auth_dep)
    app.include_router(collections.router, dependencies=auth_dep)
    app.include_router(qdrant.router, dependencies=auth_dep)
    app.include_router(search.router, dependencies=auth_dep)
    app.include_router(analytics.router, dependencies=auth_dep)
    app.include_router(system.router, dependencies=auth_dep)
    app.include_router(models.router, dependencies=auth_dep)

    return app


app = create_app()
