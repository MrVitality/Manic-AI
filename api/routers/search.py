"""Search routes."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
import asyncpg
import httpx

from api.auth import get_current_user_id
from api.config import settings
from api.dependencies import get_db_optional, get_http_client
from api.middleware.rate_limit import limiter
from api.schemas.envelope import ok
from api.schemas.search import SearchExplainRequest, SearchRequest, SearchResult
from api.services.embedding import generate_embedding
from api.services.search import search_with_explain, unified_search

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/search",
    response_model=None,
    tags=["search"],
    summary="Hybrid document search",
    description="Unified hybrid search combining vector similarity and BM25 keyword matching. "
    "Uses POST instead of GET to support complex query bodies with filtering, "
    "backend selection, and reranking options.",
)
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def search_documents(
    request: Request,
    body: SearchRequest,
    client: httpx.AsyncClient = Depends(get_http_client),
    db: Optional[asyncpg.Pool] = Depends(get_db_optional),
):
    try:
        # In multi_user mode, enforce tenant isolation by using the authenticated
        # user's id rather than trusting the client-supplied body value.
        effective_user_id = get_current_user_id(request) or body.user_id
        query_embedding = await generate_embedding(body.query, client=client)
        results = await unified_search(
            query_text=body.query,
            query_embedding=query_embedding,
            backend=body.backend or "supabase",
            top_k=body.top_k or 5,
            threshold=body.threshold or 0.7,
            use_hybrid=body.use_hybrid if body.use_hybrid is not None else True,
            collection_id=body.collection_id,
            user_id=effective_user_id,
            db=db,
            client=client,
            rerank=body.rerank or False,
            use_mmr=body.use_mmr,
            mmr_lambda=body.mmr_lambda,
        )
        return ok([SearchResult(**r).model_dump() for r in results])
    except Exception:
        logger.exception("Search failed for query: %s", body.query[:100])
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/search/explain",
    response_model=None,
    tags=["search"],
    summary="Search with scoring explanation",
    description="Search with detailed scoring breakdown for debugging relevance. "
    "Uses POST to support the same complex query body as /search.",
)
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def search_explain(
    request: Request,
    body: SearchExplainRequest,
    client: httpx.AsyncClient = Depends(get_http_client),
    db: Optional[asyncpg.Pool] = Depends(get_db_optional),
):
    try:
        effective_user_id = get_current_user_id(request)
        query_embedding = await generate_embedding(body.query, client=client)
        result = await search_with_explain(
            query_text=body.query,
            query_embedding=query_embedding,
            backend=body.backend or "supabase",
            top_k=body.top_k or 5,
            threshold=body.threshold or 0.5,
            use_hybrid=body.use_hybrid if body.use_hybrid is not None else True,
            collection_id=body.collection_id,
            include_vectors=body.include_vectors or False,
            user_id=effective_user_id,
            db=db,
            client=client,
        )
        return ok(result)
    except Exception:
        logger.exception("Search explain failed for query: %s", body.query[:100])
        raise HTTPException(status_code=500, detail="Internal server error")
