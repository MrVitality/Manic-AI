import json
import time
from datetime import datetime, timezone
from typing import Any, Dict

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

from api.config import (
    CHAT_MODEL,
    EMBEDDING_MODEL,
    RAG_THRESHOLD,
    RAG_TOP_K,
    REDIS_URL,
    VECTOR_DIMENSION,
)
from api.database import get_db, get_db_optional

router = APIRouter()

_startup_time = time.time()


# =============================================================================
# GET /system/info
# =============================================================================


@router.get("/system/info")
async def system_info() -> Dict[str, Any]:
    """Deployment info and configuration."""
    uptime = time.time() - _startup_time
    db_pool = get_db_optional()
    pool_size = 0
    pool_free = 0
    if db_pool:
        pool_size = db_pool.get_size()
        pool_free = db_pool.get_idle_size()
    return {
        "version": "2.0.0",
        "uptime_seconds": round(uptime, 1),
        "start_time": datetime.fromtimestamp(_startup_time, tz=timezone.utc).isoformat(),
        "config": {
            "chat_model": CHAT_MODEL,
            "embedding_model": EMBEDDING_MODEL,
            "vector_dimension": VECTOR_DIMENSION,
            "rag_top_k": RAG_TOP_K,
            "rag_threshold": RAG_THRESHOLD,
        },
        "database": {"pool_size": pool_size, "pool_free": pool_free},
    }


# =============================================================================
# POST /system/cache/clear
# =============================================================================


@router.post("/system/cache/clear")
async def clear_cache() -> Dict[str, Any]:
    """Flush all Redis manic:* keys."""
    keys_removed = 0
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(REDIS_URL)
        keys = await r.keys("manic:*")
        if keys:
            keys_removed = await r.delete(*keys)
        await r.aclose()
        return {"cleared": True, "keys_removed": keys_removed}
    except Exception as e:
        return {"cleared": False, "keys_removed": 0, "error": str(e)}


# =============================================================================
# GET /rag/stats
# =============================================================================


@router.get("/rag/stats")
async def rag_stats() -> Dict[str, Any]:
    """Comprehensive RAG system statistics."""
    db_pool = get_db_optional()
    if not db_pool:
        return {
            "total_documents": 0,
            "total_chunks": 0,
            "total_collections": 0,
            "storage_bytes": 0,
            "avg_chunk_tokens": 0,
            "embedding_model": EMBEDDING_MODEL,
            "vector_dimension": VECTOR_DIMENSION,
            "index_type": "pgvector (ivfflat)",
            "documents_by_type": {},
            "recent_ingestions": [],
        }

    async with db_pool.acquire() as conn:
        doc_count = await conn.fetchval("SELECT COUNT(*) FROM rag.documents")
        chunk_row = await conn.fetchrow(
            "SELECT COUNT(*) as total, COALESCE(AVG(content_tokens), 0) as avg_tokens FROM rag.chunks"
        )
        coll_count = await conn.fetchval("SELECT COUNT(*) FROM rag.collections")
        storage = await conn.fetchval("SELECT COALESCE(SUM(file_size), 0) FROM rag.documents")

        by_type = await conn.fetch(
            "SELECT content_type, COUNT(*) as count FROM rag.documents GROUP BY content_type"
        )

        recent = await conn.fetch(
            """SELECT id::text as document_id, filename, chunk_count as chunks_created, status, created_at
               FROM rag.documents ORDER BY created_at DESC LIMIT 10"""
        )

    return {
        "total_documents": doc_count,
        "total_chunks": chunk_row["total"],
        "total_collections": coll_count,
        "storage_bytes": storage,
        "avg_chunk_tokens": round(float(chunk_row["avg_tokens"]), 1),
        "embedding_model": EMBEDDING_MODEL,
        "vector_dimension": VECTOR_DIMENSION,
        "index_type": "pgvector (ivfflat)",
        "documents_by_type": {r["content_type"]: r["count"] for r in by_type},
        "recent_ingestions": [
            {
                "document_id": r["document_id"],
                "filename": r["filename"],
                "chunks_created": r["chunks_created"],
                "status": r["status"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in recent
        ],
    }


# =============================================================================
# GET /documents/{document_id}/chunks
# =============================================================================


@router.get("/documents/{document_id}/chunks")
async def get_document_chunks(
    document_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: asyncpg.Pool = Depends(get_db),
) -> Dict[str, Any]:
    """Paginated chunk viewer for a document."""
    async with db.acquire() as conn:
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM rag.chunks WHERE document_id = $1", document_id
        )
        rows = await conn.fetch(
            """
            SELECT id::text, chunk_index, content, content_tokens, metadata, created_at
            FROM rag.chunks WHERE document_id = $1
            ORDER BY chunk_index LIMIT $2 OFFSET $3
            """,
            document_id,
            limit,
            offset,
        )
    chunks = [
        {
            "id": r["id"],
            "chunk_index": r["chunk_index"],
            "content": r["content"],
            "content_tokens": r["content_tokens"],
            "metadata": json.loads(r["metadata"]) if r["metadata"] else {},
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]
    return {"chunks": chunks, "total": total}
