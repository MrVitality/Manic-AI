"""Search business logic -- unified search across Supabase + Qdrant."""

import asyncio
import hashlib
import json
import logging
import time
from typing import Any, Dict, List, Optional

import asyncpg
import httpx

from api.config import settings
from api.repositories.qdrant_vector import QdrantVectorRepository
from api.repositories.supabase_documents import SupabaseDocumentRepository
from api.repositories.supabase_vector import SupabaseVectorRepository
from api.services.embedding import generate_embedding
from api.services.mmr import mmr_rerank
from api.services.reranker import rerank_chunks
from api.services.search_logger import log_search

logger = logging.getLogger(__name__)

# Module-level Redis client — injected by init_redis() at app startup.
_redis = None


def _set_redis(client) -> None:
    """Replace the module-level Redis reference (mirrors embedding.py pattern)."""
    import api.services.search as _mod
    _mod._redis = client


def _search_cache_key(
    query: str,
    backend: str,
    top_k: int,
    threshold: float,
    use_hybrid: bool,
    collection_id: Optional[str],
    keyword_weight: float,
) -> str:
    """Return a deterministic Redis key for the given search parameters."""
    params = {
        "query": query,
        "backend": backend,
        "top_k": top_k,
        "threshold": threshold,
        "use_hybrid": use_hybrid,
        "collection_id": collection_id,
        "keyword_weight": keyword_weight,
    }
    digest = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()
    return f"manic:search:{digest}"


async def unified_search(
    query_text: str,
    query_embedding: List[float],
    backend: str,
    top_k: int,
    threshold: float,
    use_hybrid: bool,
    collection_id: Optional[str],
    user_id: Optional[str],
    db: Optional[asyncpg.Pool],
    client: httpx.AsyncClient,
    rerank: bool = False,
    skip_cache: bool = False,
    use_mmr: bool = False,
    mmr_lambda: float = 0.7,
) -> List[Dict[str, Any]]:
    """Run search across the requested backend(s), deduplicate, and optionally rerank.

    Results are cached in Redis for SEARCH_CACHE_TTL seconds (default 300 s).
    Pass skip_cache=True to bypass the cache and always run a live search.
    Caching is skipped silently when user_id is set (per-user results are not shared)
    or when Redis is unavailable.

    Args:
        use_mmr: When True, apply Maximal Marginal Relevance re-ranking after
            retrieval to promote diversity among the returned results.
            MMR is supported for the Qdrant backend (vectors are fetched from
            Qdrant directly).  For the Supabase backend MMR falls back to plain
            score-ordered results (TODO: return embeddings from Supabase search).
        mmr_lambda: MMR trade-off weight passed to :func:`~api.services.mmr.mmr_rerank`.
            0 = maximum diversity, 1 = maximum relevance.  Defaults to 0.7.
    """
    start = time.time()

    # --- Cache lookup (skip for user-scoped queries to avoid result leakage) ---
    cache_key: Optional[str] = None
    if not skip_cache and not user_id and _redis:
        cache_key = _search_cache_key(
            query=query_text,
            backend=backend,
            top_k=top_k,
            threshold=threshold,
            use_hybrid=use_hybrid,
            collection_id=collection_id,
            keyword_weight=settings.RAG_KEYWORD_WEIGHT,
        )
        try:
            cached = await _redis.get(cache_key)
            if cached:
                logger.debug("Search cache hit for key %s", cache_key)
                return json.loads(cached)
        except Exception as exc:
            logger.warning("Redis search cache get failed: %s", exc)
            cache_key = None  # do not attempt to write on a broken connection

    # When reranking or MMR is active, fetch more candidates for better selection.
    needs_extra_candidates = rerank or use_mmr
    retrieval_top_k = top_k * 3 if use_mmr else (20 if rerank else top_k)

    results: List[Dict[str, Any]] = []

    if backend in ["supabase", "both"] and db:
        sb_vector = SupabaseVectorRepository(db)
        if use_hybrid:
            rows = await sb_vector.hybrid_search(
                query_text, query_embedding,
                top_k=retrieval_top_k,
                keyword_weight=settings.RAG_KEYWORD_WEIGHT,
                collection_id=collection_id,
                user_id=user_id,
            )
        else:
            rows = await sb_vector.vector_search(
                query_embedding,
                top_k=retrieval_top_k,
                threshold=threshold,
                collection_id=collection_id,
                user_id=user_id,
            )
        for r in rows:
            r["backend"] = "supabase"
        results.extend(rows)

    if backend in ["qdrant", "both"]:
        qdrant = QdrantVectorRepository(settings.QDRANT_URL, client)
        filters: Dict[str, str] = {}
        if collection_id:
            filters["collection_id"] = collection_id
        if user_id:
            filters["user_id"] = user_id

        if use_mmr:
            # Fetch vectors alongside results so MMR can compute inter-document
            # cosine similarity without a second round-trip.
            qdrant_results = await qdrant.search_with_vectors(
                query_embedding,
                collection_name="documents",
                top_k=retrieval_top_k,
                threshold=threshold,
                filters=filters or None,
            )
        else:
            qdrant_results = await qdrant.search(
                query_embedding,
                collection_name="documents",
                top_k=retrieval_top_k,
                threshold=threshold,
                filters=filters or None,
            )
        results.extend(qdrant_results)

    if backend == "both":
        seen: set = set()
        unique: List[Dict[str, Any]] = []
        for r in sorted(results, key=lambda x: x["score"], reverse=True):
            h = hashlib.sha256(r["content"][:500].encode()).hexdigest()
            if h not in seen:
                seen.add(h)
                unique.append(r)
        results = unique

    # MMR re-ranking (diversity-aware, applied before cross-encoder reranking).
    # Only Qdrant results carry embeddings; Supabase results are passed through
    # as-is (TODO: surface embeddings from the Supabase vector search function).
    if use_mmr and results:
        qdrant_mask = [i for i, r in enumerate(results) if r.get("embedding")]
        if qdrant_mask:
            qdrant_subset = [results[i] for i in qdrant_mask]
            embeddings = [r["embedding"] for r in qdrant_subset]
            scores = [r["score"] for r in qdrant_subset]
            ranked_local_indices = mmr_rerank(
                query_embedding=query_embedding,
                candidate_embeddings=embeddings,
                candidate_scores=scores,
                k=top_k,
                lambda_mult=mmr_lambda,
            )
            mmr_results = [qdrant_subset[i] for i in ranked_local_indices]
            # Append any non-Qdrant results that were not part of the MMR pool
            # (Supabase etc.) up to top_k, preserving score order.
            other_results = [results[i] for i in range(len(results)) if i not in qdrant_mask]
            remaining_slots = top_k - len(mmr_results)
            if remaining_slots > 0 and other_results:
                other_sorted = sorted(other_results, key=lambda x: x["score"], reverse=True)
                mmr_results.extend(other_sorted[:remaining_slots])
            results = mmr_results
        else:
            # No embeddings available — fall back to score-ordered truncation.
            logger.debug("MMR requested but no embeddings available; falling back to score order")
            results = results[:top_k]
    elif rerank and results:
        # Cross-encoder reranking (optional)
        results = await rerank_chunks(
            query=query_text,
            chunks=results,
            client=client,
            top_n=top_k,
        )
    else:
        results = results[:top_k]

    # Strip internal "embedding" key from results before returning / caching
    # to avoid leaking large vectors to API consumers.
    for r in results:
        r.pop("embedding", None)

    # --- Cache store (best-effort, does not block response) ---
    if cache_key and _redis:
        try:
            await _redis.setex(cache_key, settings.SEARCH_CACHE_TTL, json.dumps(results))
            logger.debug("Search results cached under key %s (TTL %ds)", cache_key, settings.SEARCH_CACHE_TTL)
        except Exception as exc:
            logger.warning("Redis search cache set failed: %s", exc)

    # Log search event (best-effort, does not block response)
    latency_ms = round((time.time() - start) * 1000, 1)
    task = asyncio.create_task(log_search(
        db=db,
        query=query_text,
        backend=backend,
        use_hybrid=use_hybrid,
        top_k=top_k,
        threshold=threshold,
        keyword_weight=settings.RAG_KEYWORD_WEIGHT,
        reranked=rerank,
        results=results,
        latency_ms=latency_ms,
        collection_id=collection_id,
        user_id=user_id,
    ))
    task.add_done_callback(
        lambda t: logger.warning("Search log failed: %s", t.exception())
        if not t.cancelled() and t.exception() else None
    )

    return results


async def search_with_explain(
    query_text: str,
    query_embedding: List[float],
    backend: str,
    top_k: int,
    threshold: float,
    use_hybrid: bool,
    collection_id: Optional[str],
    include_vectors: bool,
    db: Optional[asyncpg.Pool],
    client: httpx.AsyncClient,
) -> Dict[str, Any]:
    """Search with debug/explain metadata."""
    start = time.time()
    results: List[Dict[str, Any]] = []

    if backend in ["supabase", "both"] and db:
        sb_vector = SupabaseVectorRepository(db)
        if use_hybrid:
            raw = await sb_vector.hybrid_search(
                query_text, query_embedding,
                top_k=top_k,
                keyword_weight=settings.RAG_KEYWORD_WEIGHT,
                collection_id=collection_id,
            )
        else:
            raw = await sb_vector.vector_search(
                query_embedding,
                top_k=top_k,
                threshold=threshold,
                collection_id=collection_id,
            )

        doc_ids = list({r["document_id"] for r in raw})
        doc_repo = SupabaseDocumentRepository(db)
        filename_map = await doc_repo.get_document_filenames(doc_ids)

        for r in raw:
            entry: Dict[str, Any] = {
                "id": r["id"],
                "document_id": r["document_id"],
                "content": r["content"],
                "metadata": r.get("metadata", {}),
                "score": r["score"],
                "backend": "supabase",
                "doc_filename": filename_map.get(r["document_id"], "unknown"),
            }
            if "vector_score" in r:
                entry["vector_score"] = r["vector_score"]
            if "keyword_score" in r:
                entry["keyword_score"] = r["keyword_score"]
            results.append(entry)

    if backend in ["qdrant", "both"]:
        qdrant = QdrantVectorRepository(settings.QDRANT_URL, client)
        filters: Dict[str, str] = {}
        if collection_id:
            filters["collection_id"] = collection_id
        qdrant_results = await qdrant.search(
            query_embedding,
            collection_name="documents",
            top_k=top_k,
            threshold=threshold,
            filters=filters or None,
        )
        results.extend(qdrant_results)

    latency_ms = round((time.time() - start) * 1000, 1)
    embedding_preview = query_embedding[:10] if include_vectors else []

    # Log search event (best-effort, does not block response)
    task = asyncio.create_task(log_search(
        db=db,
        query=query_text,
        backend=backend,
        use_hybrid=use_hybrid,
        top_k=top_k,
        threshold=threshold,
        keyword_weight=settings.RAG_KEYWORD_WEIGHT,
        reranked=False,
        results=results,
        latency_ms=latency_ms,
        collection_id=collection_id,
        user_id=None,
    ))
    task.add_done_callback(
        lambda t: logger.warning("Search log failed: %s", t.exception())
        if not t.cancelled() and t.exception() else None
    )

    return {
        "results": results,
        "query_embedding_preview": embedding_preview,
        "search_latency_ms": latency_ms,
    }
