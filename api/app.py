import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.auth import require_api_key
from api.config import settings
from api.exception_handlers import register_exception_handlers
from api.middleware.guardrails import GuardrailsMiddleware
from api.middleware.metrics import MetricsMiddleware
from api.middleware.prometheus import PrometheusMiddleware
from api.middleware.rate_limit import limiter
from api.middleware.request_id import RequestIdMiddleware
from api.middleware.security_headers import SecurityHeadersMiddleware

from api.database import init_pool, close_pool
from api.http_client import init_client, close_client
from api.services.embedding import init_redis
from api.services.langfuse import init_langfuse
from api.services.health_logger import health_log_loop

# Import all routers
from api.routers import health, chat, ingest, documents, collections, qdrant, search, analytics, system, models, agent, eval as eval_router, feedback as feedback_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup -- store resources on app.state for DI
    await init_pool(settings.SUPABASE_DB_URL, app=app)
    await init_client(app=app)
    await init_redis(app=app)
    init_langfuse(app=app)
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



_TAGS_METADATA = [
    {"name": "health", "description": "Health checks and service status (unauthenticated)"},
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
]


def create_app() -> FastAPI:
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
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Rate limiting ---
    _app.state.limiter = limiter

    # --- Global exception handlers (envelope-consistent errors) ---
    register_exception_handlers(_app)

    # --- Observability & security middleware ---
    # Order matters: outermost runs first.
    # RequestId -> SecurityHeaders -> Guardrails -> Prometheus -> Metrics
    _app.add_middleware(MetricsMiddleware)
    _app.add_middleware(PrometheusMiddleware)
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
    v1_router.include_router(eval_router.router, dependencies=auth_dep, tags=["eval"])
    v1_router.include_router(feedback_router.router, dependencies=auth_dep, tags=["feedback"])

    _app.include_router(v1_router)

    return _app


app = create_app()
