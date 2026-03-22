"""Health and service-status routes.

These are mounted at the root (not under /v1/) so that load balancers
and uptime monitors can reach them without authentication.
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import Response, StreamingResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import asyncpg
import httpx

from api.config import settings
from api.dependencies import get_db_optional, get_http_client
from api.schemas.envelope import ok
from api.services.rag import check_service

router = APIRouter()


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
async def health_check(
    client: httpx.AsyncClient = Depends(get_http_client),
    db: Optional[asyncpg.Pool] = Depends(get_db_optional),
) -> Dict[str, Any]:
    ollama = await check_service(f"{settings.OLLAMA_URL}/api/tags", client)
    return ok({
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "auth_enabled": bool(settings.API_SECRET_KEY),
        "services": {
            "database": "connected" if db else "disconnected",
            "ollama": ollama["status"],
        },
        "config": {
            "chat_model": settings.CHAT_MODEL,
            "embedding_model": settings.EMBEDDING_MODEL,
            "vector_dimension": settings.VECTOR_DIMENSION,
        },
    })


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


@router.get("/services/status", tags=["health"])
async def services_status(
    client: httpx.AsyncClient = Depends(get_http_client),
    db: Optional[asyncpg.Pool] = Depends(get_db_optional),
) -> Dict[str, Any]:
    data = await _get_all_services(client, db)
    return ok(data)


@router.get("/services/status/stream", tags=["health"])
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
                except Exception as e:
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
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
    client: httpx.AsyncClient = Depends(get_http_client),
    db: Optional[asyncpg.Pool] = Depends(get_db_optional),
):
    """WebSocket endpoint for real-time service status updates.

    Sends a full status snapshot every 10 seconds. Responds to ``ping``
    messages from the client with a ``{"type": "pong"}`` reply.
    """
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


@router.get("/metrics", tags=["health"], include_in_schema=False)
async def prometheus_metrics():
    """Prometheus metrics endpoint for monitoring stack."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
