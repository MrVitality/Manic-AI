"""Analytics business logic."""

import logging
from typing import Any, Dict, Optional

import asyncpg
import httpx

from api.config import settings
from api.repositories.supabase_documents import SupabaseDocumentRepository

logger = logging.getLogger(__name__)


async def usage_analytics(
    db: Optional[asyncpg.Pool],
    interval: str,
    model: Optional[str],
) -> Dict[str, Any]:
    """Token usage aggregated by period."""
    if not db:
        return {
            "data": [],
            "totals": {"total_tokens": 0, "total_requests": 0, "avg_latency_ms": 0},
        }

    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                date_trunc('hour', created_at) AS bucket,
                model,
                SUM(total_tokens)       AS total_tokens,
                SUM(prompt_tokens)      AS prompt_tokens,
                SUM(completion_tokens)  AS completion_tokens,
                COUNT(*)                AS request_count,
                ROUND(AVG(latency_ms)::numeric, 1) AS avg_latency_ms
            FROM public.chat_log
            WHERE created_at > NOW() - $1::INTERVAL
              AND ($2::text IS NULL OR model = $2)
            GROUP BY bucket, model
            ORDER BY bucket
            """,
            interval, model,
        )

    data_points = [
        {
            "timestamp": r["bucket"].isoformat(),
            "model": r["model"],
            "total_tokens": r["total_tokens"],
            "prompt_tokens": r["prompt_tokens"],
            "completion_tokens": r["completion_tokens"],
            "request_count": r["request_count"],
            "avg_latency_ms": float(r["avg_latency_ms"]),
        }
        for r in rows
    ]

    total_tokens = sum(r["total_tokens"] for r in data_points)
    total_requests = sum(r["request_count"] for r in data_points)
    total_latency = sum(r["avg_latency_ms"] * r["request_count"] for r in data_points)

    return {
        "data": data_points,
        "totals": {
            "total_tokens": total_tokens,
            "total_requests": total_requests,
            "avg_latency_ms": round(total_latency / max(total_requests, 1), 1),
        },
    }


async def model_analytics(
    db: Optional[asyncpg.Pool],
    client: httpx.AsyncClient,
) -> Dict[str, Any]:
    """Per-model usage stats merged with installed Ollama models."""
    model_stats: Dict[str, Dict] = {}
    if db:
        async with db.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    model,
                    COUNT(*)                               AS request_count,
                    SUM(total_tokens)                      AS total_tokens,
                    ROUND(AVG(latency_ms)::numeric, 1)     AS avg_latency_ms,
                    ROUND(AVG(total_tokens)::numeric, 1)   AS avg_tokens_per_request,
                    MAX(created_at)                        AS last_used
                FROM public.chat_log
                GROUP BY model
                """,
            )
            for r in rows:
                model_stats[r["model"]] = {
                    "request_count": r["request_count"],
                    "total_tokens": r["total_tokens"],
                    "avg_latency_ms": float(r["avg_latency_ms"]),
                    "avg_tokens_per_request": float(r["avg_tokens_per_request"]),
                    "last_used": r["last_used"].isoformat() if r["last_used"] else None,
                }

    models = []
    try:
        resp = await client.get(f"{settings.OLLAMA_URL}/api/tags")
        resp.raise_for_status()
        for m in resp.json().get("models", []):
            name = m.get("name", "unknown")
            stats = model_stats.get(name, {})
            models.append({
                "name": name,
                "size_bytes": m.get("size", 0),
                "request_count": stats.get("request_count", 0),
                "total_tokens": stats.get("total_tokens", 0),
                "avg_latency_ms": stats.get("avg_latency_ms", 0),
                "avg_tokens_per_request": stats.get("avg_tokens_per_request", 0),
                "last_used": stats.get("last_used"),
            })
    except Exception:
        logger.warning("Failed to fetch Ollama model list for analytics", exc_info=True)

    return {"models": models}


async def rag_analytics(db: Optional[asyncpg.Pool]) -> Dict[str, Any]:
    """RAG pipeline analytics."""
    empty = {
        "documents": {"total": 0, "by_status": {}},
        "chunks": {"total": 0, "avg_per_document": 0, "total_tokens": 0},
        "searches": {"total": 0, "avg_results": 0.0, "avg_score": 0.0, "avg_latency_ms": 0.0},
        "collections": {"total": 0, "avg_documents_per_collection": 0},
    }
    if not db:
        return empty
    doc_repo = SupabaseDocumentRepository(db)
    return await doc_repo.rag_analytics()


async def services_history(
    db: Optional[asyncpg.Pool],
    service: Optional[str],
    hours: int,
) -> Dict[str, Any]:
    """Historical service latency data."""
    if not db:
        return {"history": []}

    try:
        async with db.acquire() as conn:
            exists = await conn.fetchval(
                """
                SELECT EXISTS(
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_name = 'service_health_log'
                      AND table_schema = 'public'
                )
                """,
            )
            if not exists:
                return {"history": []}

            if service:
                rows = await conn.fetch(
                    """
                    SELECT service_name, status, latency_ms, checked_at
                    FROM public.service_health_log
                    WHERE service_name = $1
                      AND checked_at > NOW() - $2 * INTERVAL '1 hour'
                    ORDER BY checked_at DESC
                    LIMIT 500
                    """,
                    service, hours,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT service_name, status, latency_ms, checked_at
                    FROM public.service_health_log
                    WHERE checked_at > NOW() - $1 * INTERVAL '1 hour'
                    ORDER BY checked_at DESC
                    LIMIT 1000
                    """,
                    hours,
                )

        snapshots: Dict[str, Dict] = {}
        for r in rows:
            ts_key = r["checked_at"].strftime("%Y-%m-%dT%H:%M:00")
            if ts_key not in snapshots:
                snapshots[ts_key] = {"timestamp": ts_key, "services": {}}
            snapshots[ts_key]["services"][r["service_name"]] = {
                "status": r["status"],
                "latency_ms": float(r["latency_ms"]) if r["latency_ms"] else None,
            }

        history = sorted(snapshots.values(), key=lambda x: x["timestamp"])
        return {"history": history}
    except Exception:
        logger.exception("Failed to fetch service health history")
        return {"history": []}
