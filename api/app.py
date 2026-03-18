import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.auth import require_api_key
from api.config import settings
from api.middleware.guardrails import GuardrailsMiddleware
from api.middleware.metrics import MetricsMiddleware
from api.middleware.rate_limit import limiter
from api.middleware.request_id import RequestIdMiddleware
from api.middleware.security_headers import SecurityHeadersMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from api.database import init_pool, close_pool
from api.http_client import init_client, close_client
from api.services.embedding import init_redis
from api.services.langfuse import init_langfuse
from api.services.health_logger import health_log_loop

# Import all routers
from api.routers import health, chat, ingest, documents, collections, qdrant, search, analytics, system, models, agent

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup -- store resources on app.state for DI
    await init_pool(settings.SUPABASE_DB_URL, app=app)
    await init_client(app=app)
    await init_redis(app=app)
    init_langfuse(app=app)
    await _run_ddl()
    health_task = asyncio.create_task(health_log_loop())

    yield  # app runs

    # Shutdown
    health_task.cancel()
    try:
        await health_task
    except asyncio.CancelledError:
        pass
    await close_pool(app=app)
    await close_client(app=app)


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
        # ingest_jobs for async ingestion status tracking
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS public.ingest_jobs (
                id BIGSERIAL PRIMARY KEY,
                document_id TEXT UNIQUE NOT NULL,
                filename TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                chunks_created INT,
                error TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)


def create_app() -> FastAPI:
    _app = FastAPI(
        title="Manic AI API",
        version="2.0.0",
        lifespan=lifespan,
    )

    # --- CORS configuration (secure defaults) ---
    cors_origins = settings.parse_cors_origins()
    allow_credentials = "*" not in cors_origins
    if not allow_credentials:
        logger.warning(
            "CORS allow_origins contains wildcard '*' -- "
            "allow_credentials has been forced to False."
        )

    _app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Rate limiting ---
    _app.state.limiter = limiter
    _app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # --- Observability & security middleware ---
    # Order matters: outermost runs first.
    # RequestId -> SecurityHeaders -> Guardrails -> Metrics
    _app.add_middleware(MetricsMiddleware)
    _app.add_middleware(GuardrailsMiddleware)
    _app.add_middleware(SecurityHeadersMiddleware)
    _app.add_middleware(RequestIdMiddleware)

    # --- API versioning ---
    v1_router = APIRouter(prefix="/v1")

    # Health router is public (needed for uptime checks / load balancers).
    # Mounted at root for load-balancer probes.
    _app.include_router(health.router, tags=["health"])

    # All other routers require API key authentication, under /v1/
    auth_dep = [Depends(require_api_key)]
    v1_router.include_router(chat.router, dependencies=auth_dep, tags=["chat"])
    v1_router.include_router(ingest.router, dependencies=auth_dep, tags=["ingest"])
    v1_router.include_router(documents.router, dependencies=auth_dep, tags=["documents"])
    v1_router.include_router(collections.router, dependencies=auth_dep, tags=["collections"])
    v1_router.include_router(qdrant.router, dependencies=auth_dep, tags=["qdrant"])
    v1_router.include_router(search.router, dependencies=auth_dep, tags=["search"])
    v1_router.include_router(analytics.router, dependencies=auth_dep, tags=["analytics"])
    v1_router.include_router(system.router, dependencies=auth_dep, tags=["system"])
    v1_router.include_router(models.router, dependencies=auth_dep, tags=["models"])
    v1_router.include_router(agent.router, dependencies=auth_dep, tags=["agent"])

    _app.include_router(v1_router)

    return _app


app = create_app()
