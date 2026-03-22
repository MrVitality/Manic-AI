"""RAG evaluation endpoints."""
import asyncio
import logging
from typing import Any, Dict, List, Optional

import asyncpg
import httpx
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from api.auth import require_api_key
from api.dependencies import get_db, get_db_optional, get_http_client
from api.schemas.envelope import ok
from api.services.rag_eval import compute_eval_metrics, score_distribution
from api.services.search_logger import get_search_history

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_api_key)])


class EvalRequest(BaseModel):
    """Run evaluation against ground truth."""

    query: str = Field(..., min_length=1)
    relevant_chunk_ids: List[str] = Field(..., min_length=1)
    top_k: int = Field(5, ge=1, le=50)
    backend: str = "supabase"
    use_hybrid: bool = True
    rerank: bool = False


class EvalBatchRequest(BaseModel):
    """Run batch evaluation over multiple queries."""

    test_cases: List[EvalRequest] = Field(..., max_length=50)


@router.post("/eval/run", response_model=None, tags=["eval"])
async def run_eval(
    body: EvalRequest,
    client: httpx.AsyncClient = Depends(get_http_client),
    db: Optional[asyncpg.Pool] = Depends(get_db_optional),
) -> Dict[str, Any]:
    """Run a single RAG evaluation: search for query, compare results to ground truth."""
    from api.services.embedding import generate_embedding
    from api.services.search import unified_search

    query_embedding = await generate_embedding(body.query, client=client)
    results = await unified_search(
        query_text=body.query,
        query_embedding=query_embedding,
        backend=body.backend,
        top_k=body.top_k,
        threshold=0.0,  # don't filter by threshold for eval
        use_hybrid=body.use_hybrid,
        collection_id=None,
        user_id=None,
        db=db,
        client=client,
        rerank=body.rerank,
    )

    retrieved_ids = [r.get("id", "") for r in results]
    scores = [r.get("score", 0.0) for r in results]

    metrics: Dict[str, Any] = compute_eval_metrics(retrieved_ids, body.relevant_chunk_ids)
    metrics["score_distribution"] = score_distribution(scores)
    metrics["query"] = body.query
    metrics["retrieved_ids"] = retrieved_ids

    return ok(metrics)


@router.post("/eval/batch", response_model=None, tags=["eval"])
async def run_eval_batch(
    body: EvalBatchRequest,
    client: httpx.AsyncClient = Depends(get_http_client),
    db: Optional[asyncpg.Pool] = Depends(get_db_optional),
) -> Dict[str, Any]:
    """Run batch RAG evaluation over multiple test cases. Returns per-query and aggregate metrics."""
    from api.services.embedding import generate_embedding
    from api.services.search import unified_search

    async def _run_case(case: EvalRequest) -> Dict[str, Any]:
        query_embedding = await generate_embedding(case.query, client=client)
        results = await unified_search(
            query_text=case.query,
            query_embedding=query_embedding,
            backend=case.backend,
            top_k=case.top_k,
            threshold=0.0,
            use_hybrid=case.use_hybrid,
            collection_id=None,
            user_id=None,
            db=db,
            client=client,
            rerank=case.rerank,
        )
        retrieved_ids = [r.get("id", "") for r in results]
        m: Dict[str, Any] = compute_eval_metrics(retrieved_ids, case.relevant_chunk_ids)
        m["query"] = case.query
        return m

    all_metrics: List[Dict[str, Any]] = await asyncio.gather(
        *[_run_case(case) for case in body.test_cases]
    )

    # Aggregate numeric metrics across all test cases
    n = len(all_metrics)
    aggregate: Dict[str, Any] = {}
    if n > 0:
        metric_keys = [k for k in all_metrics[0] if isinstance(all_metrics[0][k], (int, float))]
        for key in metric_keys:
            values = [m[key] for m in all_metrics]
            aggregate[key] = sum(values) / n

    return ok({
        "results": all_metrics,
        "aggregate": aggregate,
        "test_cases": n,
    })


@router.get("/eval/search-history", response_model=None, tags=["eval"])
async def search_history(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: asyncpg.Pool = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve recent search events for analysis."""
    history = await get_search_history(db, limit, offset)
    return ok(history)
