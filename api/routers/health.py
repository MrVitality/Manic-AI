import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
import httpx

from api.config import OLLAMA_URL, QDRANT_URL, SEARXNG_URL, LANGFUSE_HOST, CHAT_MODEL, EMBEDDING_MODEL, VECTOR_DIMENSION
from api.database import get_db_optional
from api.http_client import get_client
from api.services.rag import check_service

router = APIRouter()


@router.get("/health")
async def health_check(client: httpx.AsyncClient = Depends(get_client)) -> Dict[str, Any]:
    db_pool = get_db_optional()
    ollama = await check_service(f"{OLLAMA_URL}/api/tags", client)
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            "database": "connected" if db_pool else "disconnected",
            "ollama": ollama["status"],
        },
        "config": {
            "chat_model": CHAT_MODEL,
            "embedding_model": EMBEDDING_MODEL,
            "vector_dimension": VECTOR_DIMENSION,
        },
    }


async def _get_all_services(client: httpx.AsyncClient) -> dict:
    db_pool = get_db_optional()
    ollama, qdrant, searxng, langfuse = await asyncio.gather(
        check_service(f"{OLLAMA_URL}/api/tags", client),
        check_service(f"{QDRANT_URL}/collections", client),
        check_service(f"{SEARXNG_URL}/healthz", client),
        check_service(LANGFUSE_HOST, client),
    )
    db_status = {"status": "offline", "latency_ms": None}
    if db_pool:
        try:
            start = datetime.now(timezone.utc)
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            latency = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            db_status = {"status": "healthy", "latency_ms": round(latency, 1)}
        except Exception:
            db_status = {"status": "offline", "latency_ms": None}

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            "ollama": {"name": "Ollama", "url": OLLAMA_URL, **ollama},
            "database": {"name": "PostgreSQL", "url": "supabase-db:5432", **db_status},
            "qdrant": {"name": "Qdrant", "url": QDRANT_URL, **qdrant},
            "searxng": {"name": "SearXNG", "url": SEARXNG_URL, **searxng},
            "langfuse": {"name": "Langfuse", "url": LANGFUSE_HOST, **langfuse},
        },
    }


@router.get("/services/status")
async def services_status(client: httpx.AsyncClient = Depends(get_client)) -> Dict[str, Any]:
    return await _get_all_services(client)


@router.get("/services/status/stream")
async def services_status_stream(client: httpx.AsyncClient = Depends(get_client)) -> StreamingResponse:
    async def event_generator():
        try:
            while True:
                try:
                    data = await _get_all_services(client)
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
