"""Search business logic -- unified search across Supabase + Qdrant."""

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

logger = logging.getLogger(__name__)


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
) -> List[Dict[str, Any]]:
    """Run search across the requested backend(s) and deduplicate."""
    results: List[Dict[str, Any]] = []

    if backend in ["supabase", "both"] and db:
        sb_vector = SupabaseVectorRepository(db)
        if use_hybrid:
            rows = await sb_vector.hybrid_search(
                query_text, query_embedding,
                top_k=top_k,
                keyword_weight=settings.RAG_KEYWORD_WEIGHT,
                collection_id=collection_id,
                user_id=user_id,
            )
        else:
            rows = await sb_vector.vector_search(
                query_embedding,
                top_k=top_k,
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
        qdrant_results = await qdrant.search(
            query_embedding,
            collection_name="documents",
            top_k=top_k,
            threshold=threshold,
            filters=filters or None,
        )
        results.extend(qdrant_results)

    if backend == "both":
        seen: set = set()
        unique: List[Dict[str, Any]] = []
        for r in sorted(results, key=lambda x: x["score"], reverse=True):
            h = hash(r["content"][:100])
            if h not in seen:
                seen.add(h)
                unique.append(r)
        results = unique[:top_k]

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

    return {
        "results": results,
        "query_embedding_preview": embedding_preview,
        "search_latency_ms": latency_ms,
    }
