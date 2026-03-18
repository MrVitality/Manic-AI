"""Search routes."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
import asyncpg
import httpx

from api.config import settings
from api.dependencies import get_db_optional, get_http_client
from api.middleware.rate_limit import limiter
from api.schemas.envelope import ok
from api.schemas.search import SearchExplainRequest, SearchRequest, SearchResult
from api.services.embedding import generate_embedding
from api.services.search import search_with_explain, unified_search

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/search", response_model=None, tags=["search"])
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def search_documents(
    http_request: Request,
    request: SearchRequest,
    client: httpx.AsyncClient = Depends(get_http_client),
    db: Optional[asyncpg.Pool] = Depends(get_db_optional),
):
    try:
        query_embedding = await generate_embedding(request.query, client=client)
        results = await unified_search(
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
            rerank=request.rerank or False,
        )
        return ok([SearchResult(**r).model_dump() for r in results])
    except Exception:
        logger.exception("Search failed for query: %s", request.query[:100])
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/search/explain", response_model=None, tags=["search"])
async def search_explain(
    request: SearchExplainRequest,
    client: httpx.AsyncClient = Depends(get_http_client),
    db: Optional[asyncpg.Pool] = Depends(get_db_optional),
):
    query_embedding = await generate_embedding(request.query, client=client)
    result = await search_with_explain(
        query_text=request.query,
        query_embedding=query_embedding,
        backend=request.backend or "supabase",
        top_k=request.top_k or 5,
        threshold=request.threshold or 0.5,
        use_hybrid=request.use_hybrid if request.use_hybrid is not None else True,
        collection_id=request.collection_id,
        include_vectors=request.include_vectors or False,
        db=db,
        client=client,
    )
    return ok(result)
