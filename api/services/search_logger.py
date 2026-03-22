"""Log search events for RAG evaluation and analytics."""
import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

import asyncpg

logger = logging.getLogger(__name__)


async def log_search(
    db: Optional[asyncpg.Pool],
    *,
    query: str,
    backend: str,
    use_hybrid: bool,
    top_k: int,
    threshold: float,
    keyword_weight: float,
    reranked: bool,
    results: List[Dict[str, Any]],
    latency_ms: float,
    collection_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Optional[str]:
    """Log a search event and its results. Returns the search_log ID."""
    if not db:
        return None

    search_id = str(uuid4())
    scores = [r.get("score", 0.0) for r in results]

    try:
        async with db.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO public.search_log
                (id, query, backend, use_hybrid, top_k, threshold, keyword_weight,
                 reranked, result_count, avg_score, max_score, latency_ms,
                 collection_id, user_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                """,
                search_id,
                query,
                backend,
                use_hybrid,
                top_k,
                threshold,
                keyword_weight,
                reranked,
                len(results),
                sum(scores) / len(scores) if scores else 0.0,
                max(scores) if scores else 0.0,
                latency_ms,
                collection_id,
                user_id,
            )

            # Log individual results
            for rank, result in enumerate(results):
                await conn.execute(
                    """
                    INSERT INTO public.search_result_log
                    (search_log_id, chunk_id, retrieval_rank, vector_score,
                     keyword_score, combined_score, rerank_score)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    search_id,
                    result.get("id", ""),
                    rank + 1,
                    result.get("vector_score"),
                    result.get("keyword_score"),
                    result.get("score", 0.0),
                    result.get("rerank_score"),
                )
    except Exception:
        logger.warning("Failed to log search event %s", search_id)
        return None

    return search_id


async def get_search_history(
    db: asyncpg.Pool,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Retrieve recent search events for analysis."""
    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, query, backend, use_hybrid, top_k, threshold, keyword_weight,
                   reranked, result_count, avg_score, max_score, latency_ms,
                   collection_id, created_at
            FROM public.search_log
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
        )
    return [
        {
            "id": r["id"],
            "query": r["query"],
            "backend": r["backend"],
            "use_hybrid": r["use_hybrid"],
            "top_k": r["top_k"],
            "reranked": r["reranked"],
            "result_count": r["result_count"],
            "avg_score": float(r["avg_score"]) if r["avg_score"] is not None else 0.0,
            "max_score": float(r["max_score"]) if r["max_score"] is not None else 0.0,
            "latency_ms": float(r["latency_ms"]) if r["latency_ms"] is not None else 0.0,
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]
