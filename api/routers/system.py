"""System administration routes."""

import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import asyncpg
from fastapi import APIRouter, Depends, Query, Request

from api.config import settings
from api.dependencies import get_db, get_db_optional, get_redis
from api.middleware.rate_limit import limiter
from api.repositories.redis_cache import RedisCacheRepository
from api.repositories.supabase_documents import SupabaseDocumentRepository
from api.schemas.envelope import ok

router = APIRouter()

_startup_time = time.time()


@router.get("/system/info", response_model=None, tags=["system"])
async def system_info(
    db: Optional[asyncpg.Pool] = Depends(get_db_optional),
) -> Dict[str, Any]:
    uptime = time.time() - _startup_time
    pool_size = db.get_size() if db else 0
    pool_free = db.get_idle_size() if db else 0
    return ok({
        "version": "2.0.0",
        "uptime_seconds": round(uptime, 1),
        "start_time": datetime.fromtimestamp(_startup_time, tz=timezone.utc).isoformat(),
        "config": {
            "chat_model": settings.CHAT_MODEL,
            "embedding_model": settings.EMBEDDING_MODEL,
            "vector_dimension": settings.VECTOR_DIMENSION,
            "rag_top_k": settings.RAG_TOP_K,
            "rag_threshold": settings.RAG_THRESHOLD,
        },
        "database": {"pool_size": pool_size, "pool_free": pool_free},
    })


@router.post("/system/cache/clear", response_model=None, tags=["system"])
@limiter.limit(f"{settings.RATE_LIMIT_MUTATIONS_PER_MINUTE}/minute")
async def clear_cache(
    request: Request,
    redis: Optional[RedisCacheRepository] = Depends(get_redis),
) -> Dict[str, Any]:
    if not redis:
        return ok({"cleared": False, "keys_removed": 0, "error": "Redis not available"})
    keys_removed = await redis.delete_pattern("manic:*")
    return ok({"cleared": True, "keys_removed": keys_removed})


@router.get("/rag/stats", response_model=None, tags=["system"])
async def rag_stats(
    db: Optional[asyncpg.Pool] = Depends(get_db_optional),
) -> Dict[str, Any]:
    if not db:
        return ok({
            "total_documents": 0,
            "total_chunks": 0,
            "total_collections": 0,
            "storage_bytes": 0,
            "avg_chunk_tokens": 0,
            "embedding_model": settings.EMBEDDING_MODEL,
            "vector_dimension": settings.VECTOR_DIMENSION,
            "index_type": "pgvector (ivfflat)",
            "documents_by_type": {},
            "recent_ingestions": [],
        })
    doc_repo = SupabaseDocumentRepository(db)
    data = await doc_repo.rag_stats(settings.EMBEDDING_MODEL, settings.VECTOR_DIMENSION)
    return ok(data)


@router.get("/documents/{document_id}/chunks", response_model=None, tags=["documents"])
async def get_document_chunks(
    document_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: asyncpg.Pool = Depends(get_db),
) -> Dict[str, Any]:
    doc_repo = SupabaseDocumentRepository(db)
    data = await doc_repo.get_document_chunks(document_id, limit, offset)
    total = data.get("total", 0)
    return ok(data, meta={"total": total, "limit": limit, "offset": offset})
