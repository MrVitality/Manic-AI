import logging
import time
from typing import Any, Dict, List, Optional

import asyncpg
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.config import RAG_KEYWORD_WEIGHT
from api.database import get_db_optional
from api.http_client import get_client
from api.services.embedding import generate_embedding
from api.services.rag import hybrid_search, qdrant_search, vector_search

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class SearchRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5
    threshold: Optional[float] = 0.7
    use_hybrid: Optional[bool] = True
    collection_id: Optional[str] = None
    user_id: Optional[str] = None
    backend: Optional[str] = "supabase"


class SearchResult(BaseModel):
    id: str
    document_id: str
    content: str
    metadata: Dict[str, Any]
    score: float


class SearchExplainRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5
    threshold: Optional[float] = 0.5
    use_hybrid: Optional[bool] = True
    collection_id: Optional[str] = None
    include_vectors: Optional[bool] = False
    backend: Optional[str] = "supabase"


# ---------------------------------------------------------------------------
# Internal helper: unified search across backends
# ---------------------------------------------------------------------------


async def _unified_search(
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
    results: List[Dict[str, Any]] = []

    if backend in ["supabase", "both"] and db:
        if use_hybrid:
            rows = await hybrid_search(
                query_text,
                query_embedding,
                db,
                top_k,
                RAG_KEYWORD_WEIGHT,
                collection_id,
                user_id,
            )
        else:
            rows = await vector_search(
                query_embedding,
                db,
                top_k,
                threshold,
                collection_id,
                user_id,
            )
        for r in rows:
            r["backend"] = "supabase"
        results.extend(rows)

    if backend in ["qdrant", "both"]:
        filters: Dict[str, str] = {}
        if collection_id:
            filters["collection_id"] = collection_id
        if user_id:
            filters["user_id"] = user_id
        qdrant_results = await qdrant_search(
            query_embedding,
            client,
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


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/search", response_model=List[SearchResult])
async def search_documents(
    request: SearchRequest,
    client: httpx.AsyncClient = Depends(get_client),
    db=Depends(get_db_optional),
):
    try:
        query_embedding = await generate_embedding(request.query, client=client)
        results = await _unified_search(
            query_text=request.query,
            query_embedding=query_embedding,
            backend=request.backend or "supabase",
            top_k=request.top_k or 5,
            threshold=request.threshold or 0.7,
            use_hybrid=request.use_hybrid if request.use_hybrid is not None else True,
            collection_id=request.collection_id,
            user_id=request.user_id,
            db=db,
            client=client,
        )
        return [SearchResult(**r) for r in results]
    except Exception:
        logger.exception("Search failed for query: %s", request.query[:100])
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/search/explain")
async def search_explain(
    request: SearchExplainRequest,
    client: httpx.AsyncClient = Depends(get_client),
    db=Depends(get_db_optional),
):
    start = time.time()
    query_embedding = await generate_embedding(request.query, client=client)
    backend = request.backend or "supabase"
    top_k = request.top_k or 5
    threshold = request.threshold or 0.5
    results: List[Dict[str, Any]] = []

    if backend in ["supabase", "both"] and db:
        if request.use_hybrid:
            raw = await hybrid_search(
                request.query,
                query_embedding,
                db,
                top_k,
                RAG_KEYWORD_WEIGHT,
                request.collection_id,
                None,
            )
        else:
            raw = await vector_search(
                query_embedding,
                db,
                top_k,
                threshold,
                request.collection_id,
                None,
            )

        # Batch fetch all filenames in one query — fixes the N+1 bug.
        doc_ids = list({r["document_id"] for r in raw})
        filename_map: Dict[str, str] = {}
        if doc_ids and db:
            try:
                async with db.acquire() as conn:
                    rows = await conn.fetch(
                        "SELECT id::text, filename FROM rag.documents WHERE id = ANY($1::uuid[])",
                        doc_ids,
                    )
                    filename_map = {r["id"]: r["filename"] for r in rows}
            except Exception:
                logger.warning("Failed to fetch filenames for search explain", exc_info=True)

        for r in raw:
            doc_filename = filename_map.get(r["document_id"], "unknown")
            result_entry: Dict[str, Any] = {
                "id": r["id"],
                "document_id": r["document_id"],
                "content": r["content"],
                "metadata": r.get("metadata", {}),
                "score": r["score"],
                "backend": "supabase",
                "doc_filename": doc_filename,
            }
            if "vector_score" in r:
                result_entry["vector_score"] = r["vector_score"]
            if "keyword_score" in r:
                result_entry["keyword_score"] = r["keyword_score"]
            results.append(result_entry)

    if backend in ["qdrant", "both"]:
        filters: Dict[str, str] = {}
        if request.collection_id:
            filters["collection_id"] = request.collection_id
        qdrant_results = await qdrant_search(
            query_embedding,
            client,
            collection_name="documents",
            top_k=top_k,
            threshold=threshold,
            filters=filters or None,
        )
        results.extend(qdrant_results)

    latency_ms = round((time.time() - start) * 1000, 1)
    embedding_preview = query_embedding[:10] if request.include_vectors else []

    return {
        "results": results,
        "query_embedding_preview": embedding_preview,
        "search_latency_ms": latency_ms,
    }
