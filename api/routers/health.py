"""Health and service-status routes.

These are mounted at the root (not under /v1/) so that load balancers
and uptime monitors can reach them without authentication.
"""

import asyncio
import hmac
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import logging

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import Response, StreamingResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import asyncpg
import httpx

from api.auth import _secret_key, require_api_key
from api.config import settings
from api.dependencies import get_db_optional, get_http_client
from api.schemas.envelope import ok
from api.services.rag import check_service

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Simple time-based cache for the /health endpoint (5-second TTL).
# Prevents hammering downstream services on every load-balancer probe.
# ---------------------------------------------------------------------------
_HEALTH_CACHE_TTL: float = 5.0
_health_cache: Dict[str, Any] = {"data": None, "expires": 0.0}


class ConnectionManager:
    """Manages active WebSocket connections for broadcasting status updates."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, data: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(data)
            except Exception:
                pass


manager = ConnectionManager()


@router.get("/health", tags=["health"])
async def health_check() -> Dict[str, Any]:
    now = time.monotonic()
    if _health_cache["data"] is not None and now < _health_cache["expires"]:
        return _health_cache["data"]

    result = ok({
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    _health_cache["data"] = result
    _health_cache["expires"] = now + _HEALTH_CACHE_TTL
    return result


async def _get_all_services(
    client: httpx.AsyncClient,
    db: Optional[asyncpg.Pool],
) -> dict:
    ollama, qdrant, searxng, langfuse = await asyncio.gather(
        check_service(f"{settings.OLLAMA_URL}/api/tags", client),
        check_service(f"{settings.QDRANT_URL}/collections", client),
        check_service(f"{settings.SEARXNG_URL}/healthz", client),
        check_service(settings.LANGFUSE_HOST, client),
    )
    db_status: Dict[str, Any] = {"status": "offline", "latency_ms": None}
    if db:
        try:
            start = datetime.now(timezone.utc)
            async with db.acquire() as conn:
                await conn.fetchval("SELECT 1")
            latency = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            db_status = {"status": "healthy", "latency_ms": round(latency, 1)}
        except Exception:
            db_status = {"status": "offline", "latency_ms": None}

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            "ollama": {"name": "Ollama", "url": settings.OLLAMA_URL, **ollama},
            "database": {"name": "PostgreSQL", "url": "supabase-db:5432", **db_status},
            "qdrant": {"name": "Qdrant", "url": settings.QDRANT_URL, **qdrant},
            "searxng": {"name": "SearXNG", "url": settings.SEARXNG_URL, **searxng},
            "langfuse": {"name": "Langfuse", "url": settings.LANGFUSE_HOST, **langfuse},
        },
    }


@router.get("/services/status", tags=["health"], dependencies=[Depends(require_api_key)])
async def services_status(
    client: httpx.AsyncClient = Depends(get_http_client),
    db: Optional[asyncpg.Pool] = Depends(get_db_optional),
) -> Dict[str, Any]:
    data = await _get_all_services(client, db)
    return ok(data)


@router.get("/services/status/stream", tags=["health"], dependencies=[Depends(require_api_key)])
async def services_status_stream(
    client: httpx.AsyncClient = Depends(get_http_client),
    db: Optional[asyncpg.Pool] = Depends(get_db_optional),
) -> StreamingResponse:
    async def event_generator():
        try:
            while True:
                try:
                    data = await _get_all_services(client, db)
                    yield f"data: {json.dumps(data)}\n\n"
                except Exception:
                    logger.exception("Service status poll failed")
                    yield f"data: {json.dumps({'error': 'Status check failed'})}\n\n"
                await asyncio.sleep(10)
        except asyncio.CancelledError:
            return

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.websocket("/ws/status")
async def websocket_status(
    websocket: WebSocket,
    token: Optional[str] = Query(default=None),
    client: httpx.AsyncClient = Depends(get_http_client),
    db: Optional[asyncpg.Pool] = Depends(get_db_optional),
):
    """WebSocket endpoint for real-time service status updates.

    Sends a full status snapshot every 10 seconds. Responds to ``ping``
    messages from the client with a ``{"type": "pong"}`` reply.

    When API_SECRET_KEY is configured, callers must supply a matching
    ``token`` query parameter or the connection is rejected with code 1008.
    """
    if _secret_key:
        if not token or not hmac.compare_digest(token, _secret_key):
            await websocket.close(code=1008)
            return

    await manager.connect(websocket)
    try:
        while True:
            data = await _get_all_services(client, db)
            await websocket.send_json(data)
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
                if msg == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                pass  # Normal — just proceed to next status update
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


@router.get("/health/ready", tags=["health"])
async def readiness_check(
    db: Optional[asyncpg.Pool] = Depends(get_db_optional),
) -> Response:
    """Readiness probe — returns 200 when DB and Redis are reachable, 503 otherwise.

    Intended for use by load balancers and orchestrators to gate traffic.
    No authentication required.
    """
    failures: list[str] = []

    # Check DB pool
    if db:
        try:
            async with db.acquire() as conn:
                await conn.fetchval("SELECT 1")
        except Exception as exc:
            logger.warning("Readiness: DB check failed: %s", exc)
            failures.append("database")
    else:
        failures.append("database")

    # Check Redis — read the raw client from the embedding module (shared ref)
    try:
        import api.services.embedding as _emb_mod
        redis_client = _emb_mod._redis
        if redis_client:
            await redis_client.ping()
        # Redis is optional — absence is not a failure, only an unreachable client is
    except Exception as exc:
        logger.warning("Readiness: Redis check failed: %s", exc)
        failures.append("redis")

    if failures:
        return Response(
            content=json.dumps({"status": "not ready", "failed": failures}),
            status_code=503,
            media_type="application/json",
        )

    return Response(
        content=json.dumps({"status": "ready"}),
        status_code=200,
        media_type="application/json",
    )


@router.get("/metrics", tags=["health"], include_in_schema=False)
async def prometheus_metrics():
    """Prometheus metrics endpoint for monitoring stack."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
