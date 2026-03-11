import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import SUPABASE_DB_URL
from api.database import init_pool, close_pool
from api.http_client import init_client, close_client
from api.services.embedding import init_redis
from api.services.langfuse import init_langfuse
from api.services.health_logger import health_log_loop

# Import all routers
from api.routers import health, chat, ingest, documents, collections, qdrant, search, analytics, system, models


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


def create_app() -> FastAPI:
    app = FastAPI(
        title="Manic AI API",
        version="2.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount routers
    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(ingest.router)
    app.include_router(documents.router)
    app.include_router(collections.router)
    app.include_router(qdrant.router)
    app.include_router(search.router)
    app.include_router(analytics.router)
    app.include_router(system.router)
    app.include_router(models.router)

    return app


app = create_app()
