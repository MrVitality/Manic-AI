# ruff: noqa: E402
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from starlette.middleware.gzip import GZipMiddleware

from api.logging_config import setup_logging
from api.auth import require_api_key
from api.config import settings

# Initialise JSON structured logging before any other code touches the log system
setup_logging(os.getenv("LOG_LEVEL", "INFO"))
from api.exception_handlers import register_exception_handlers
from api.middleware.audit import AuditMiddleware
from api.middleware.guardrails import GuardrailsMiddleware
from api.middleware.metrics import MetricsMiddleware
from api.middleware.prometheus import PrometheusMiddleware
from api.middleware.rate_limit import limiter
from api.middleware.request_id import RequestIdMiddleware
from api.middleware.request_size import RequestSizeLimitMiddleware
from api.middleware.security_headers import SecurityHeadersMiddleware

from api.database import init_pool, close_pool
from api.http_client import init_client, close_client
from api.services.embedding import init_redis
from api.services.langfuse import init_langfuse
from api.services.health_logger import health_log_loop
from api.services.scheduler import start_scheduler, stop_scheduler
from api.services.folder_watcher import start_folder_watcher, stop_folder_watcher
from api.plugins import load_plugins

# Import all routers
from api.routers import health, chat, ingest, documents, collections, qdrant, search, analytics, system, models, agent, eval as eval_router, feedback as feedback_router, plugins as plugins_router, admin as admin_router, conversations as conversations_router
from api.routers import auth_routes, openai_compat
from api.routers import scheduler as scheduler_router
from api.routers import consensus as consensus_router
from api.routers import re_leads as re_leads_router
from api.routers import re_listings as re_listings_router
from api.routers import re_content as re_content_router

logger = logging.getLogger(__name__)


_SHUTDOWN_TIMEOUT = 30  # seconds to wait for tracked background tasks


def track_task(app: FastAPI, coro) -> asyncio.Task:
    """Schedule *coro* as an asyncio Task and register it for graceful shutdown.

    The task is added to ``app.state.background_tasks`` and automatically
    removed when it completes so the set does not grow unboundedly.
    """
    task = asyncio.create_task(coro)
    app.state.background_tasks.add(task)
    task.add_done_callback(app.state.background_tasks.discard)
    return task


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup -- store resources on app.state for DI
    app.state.background_tasks: set = set()
    await init_pool(settings.SUPABASE_DB_URL, app=app)
    await init_client(app=app)
    await init_redis(app=app)
    init_langfuse(app=app)
    load_plugins()
    health_task = asyncio.create_task(health_log_loop())

    # Retrieve shared resources for background services.
    _http_client = getattr(app.state, "http_client", None)
    _db_pool = getattr(app.state, "db_pool", None)

    start_scheduler(_http_client, _db_pool)
    start_folder_watcher(_http_client, _db_pool)

    yield  # app runs

    # Shutdown — wait for in-flight ingestion jobs, then cancel infra tasks.
    pending = set(app.state.background_tasks)
    if pending:
        logger.info(
            "Waiting up to %ds for %d in-flight background task(s)...",
            _SHUTDOWN_TIMEOUT,
            len(pending),
        )
        try:
            await asyncio.wait_for(
                asyncio.shield(asyncio.gather(*pending, return_exceptions=True)),
                timeout=_SHUTDOWN_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "%d background task(s) did not finish within %ds; proceeding with shutdown.",
                len(pending),
                _SHUTDOWN_TIMEOUT,
            )

    await stop_folder_watcher()
    await stop_scheduler()

    health_task.cancel()
    try:
        await health_task
    except asyncio.CancelledError:
        pass
    await close_pool(app=app)
    await close_client(app=app)



_TAGS_METADATA = [
    {"name": "health", "description": "Health checks and service status (unauthenticated)"},
    {"name": "auth", "description": "Authentication — obtain an API key via email + password (unauthenticated)"},
    {"name": "openai-compat", "description": "OpenAI-compatible API (POST /v1/chat/completions, GET /v1/models)"},
    {"name": "chat", "description": "Chat completion and streaming inference"},
    {"name": "search", "description": "Hybrid vector + BM25 search (POST bodies used for complex query parameters)"},
    {"name": "ingest", "description": "Document ingestion and embedding generation"},
    {"name": "documents", "description": "Document CRUD and chunk inspection"},
    {"name": "collections", "description": "Collection management for organizing documents"},
    {"name": "qdrant", "description": "Direct Qdrant vector database operations"},
    {"name": "analytics", "description": "Usage, model, RAG, and service analytics"},
    {"name": "system", "description": "System info, cache management, and RAG stats"},
    {"name": "models", "description": "Ollama model management (list, pull, delete)"},
    {"name": "agent", "description": "Generator-Critic reasoning agent with streaming support"},
    {"name": "eval", "description": "RAG evaluation metrics, batch testing, and search history analytics"},
    {"name": "feedback", "description": "User feedback on chat responses for RAG quality tracking"},
    {"name": "plugins", "description": "Plugin management — list installed plugins and execute plugin tools"},
    {"name": "admin", "description": "Admin-only: user management, account control, and system statistics"},
    {"name": "conversations", "description": "Server-side conversation and message persistence"},
]


def create_app() -> FastAPI:
    if settings.SENTRY_DSN:
        import sentry_sdk
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            environment=settings.SENTRY_ENVIRONMENT,
            send_default_pii=False,
        )

    _app = FastAPI(
        title="Manic AI API",
        description=(
            "Full-stack AI platform API with RAG capabilities, hybrid search, "
            "document ingestion, and multi-model inference."
        ),
        version="2.0.0",
        lifespan=lifespan,
        openapi_tags=_TAGS_METADATA,
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
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-API-Key", "X-Request-ID", "Accept"],
    )

    # --- Rate limiting ---
    _app.state.limiter = limiter

    # --- Global exception handlers (envelope-consistent errors) ---
    register_exception_handlers(_app)

    # --- Observability & security middleware ---
    # Order matters: outermost runs first on request, last on response.
    # GZip -> RequestSizeLimit -> RequestId -> SecurityHeaders -> Guardrails -> Prometheus -> Metrics -> Audit
    _app.add_middleware(AuditMiddleware)
    _app.add_middleware(MetricsMiddleware)
    _app.add_middleware(PrometheusMiddleware)
    _app.add_middleware(GuardrailsMiddleware)
    _app.add_middleware(SecurityHeadersMiddleware)
    _app.add_middleware(RequestIdMiddleware)
    _app.add_middleware(RequestSizeLimitMiddleware)
    _app.add_middleware(GZipMiddleware, minimum_size=500)

    # --- API versioning ---
    v1_router = APIRouter(prefix="/v1")

    # Health router is public (needed for uptime checks / load balancers).
    # Mounted at root for load-balancer probes.
    _app.include_router(health.router, tags=["health"])

    # Auth router is public — clients need it to obtain their API key.
    _app.include_router(auth_routes.router, tags=["auth"])

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
    v1_router.include_router(eval_router.router, dependencies=auth_dep, tags=["eval"])
    v1_router.include_router(feedback_router.router, dependencies=auth_dep, tags=["feedback"])
    v1_router.include_router(plugins_router.router, dependencies=auth_dep, tags=["plugins"])
    # Admin router: base auth_dep runs first, then require_admin enforces admin-level access per endpoint
    v1_router.include_router(admin_router.router, dependencies=auth_dep, tags=["admin"])
    v1_router.include_router(conversations_router.router, dependencies=auth_dep, tags=["conversations"])
    v1_router.include_router(openai_compat.router, dependencies=auth_dep, tags=["openai-compat"])
    v1_router.include_router(scheduler_router.router, dependencies=auth_dep, tags=["agent"])
    v1_router.include_router(consensus_router.router, dependencies=auth_dep, tags=["chat"])
    v1_router.include_router(re_leads_router.router, dependencies=auth_dep, tags=["re-leads"])
    v1_router.include_router(re_listings_router.router, dependencies=auth_dep, tags=["re-listings"])
    v1_router.include_router(re_content_router.router, dependencies=auth_dep, tags=["re-content"])

    _app.include_router(v1_router)

    # --- Distributed tracing (opt-in via OTEL_ENABLED=true) ---
    from api.tracing import setup_tracing
    setup_tracing(_app)

    return _app


app = create_app()
