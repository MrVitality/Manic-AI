"""CRAG (Corrective RAG) relevance gate.

After retrieval and reranking, evaluates whether the retrieved context is
actually relevant to the query. Three possible outcomes:

- CORRECT: Top score >= high threshold → use context as-is
- AMBIGUOUS: Top score between thresholds → supplement with web search
- INCORRECT: Top score < low threshold → discard context, use web search

This prevents the LLM from hallucinating confidently based on irrelevant context.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional

import httpx

from api.config import settings
from api.services.web_search import web_search

logger = logging.getLogger(__name__)

Verdict = Literal["correct", "ambiguous", "incorrect"]


@dataclass(frozen=True)
class GateResult:
    """Result of the CRAG relevance gate evaluation."""
    verdict: Verdict
    chunks: tuple
    web_results_added: int = 0
    reformulated_query: Optional[str] = None


async def _reformulate_query(
    query: str,
    client: httpx.AsyncClient,
) -> Optional[str]:
    """Ask the LLM to reformulate a query for better retrieval."""
    try:
        prompt = (
            "The following search query returned poor results. "
            "Reformulate it to be more specific and searchable. "
            "Return ONLY the reformulated query, nothing else.\n\n"
            f"Original query: {query}\n\nReformulated query:"
        )
        response = await client.post(
            f"{settings.OLLAMA_URL}/api/chat",
            json={
                "model": settings.CHAT_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0.0},
            },
            timeout=10.0,
        )
        response.raise_for_status()
        reformulated = response.json().get("message", {}).get("content", "").strip()
        if reformulated and reformulated != query:
            logger.debug("Query reformulated: '%s' -> '%s'", query[:60], reformulated[:60])
            return reformulated
    except Exception as exc:
        logger.warning("Query reformulation failed: %s", exc)
    return None


async def relevance_gate(
    query: str,
    chunks: List[Dict[str, Any]],
    client: httpx.AsyncClient,
    high_threshold: Optional[float] = None,
    low_threshold: Optional[float] = None,
) -> GateResult:
    """Evaluate retrieval quality and apply corrective action if needed.

    Expects chunks to have a ``rerank_score`` field in 0.0-1.0 range
    (normalized by the reranker). Falls back to ``score`` if ``rerank_score``
    is not present.

    Parameters
    ----------
    query : str
        The user query.
    chunks : list of dict
        Retrieved (and optionally reranked) chunks.
    client : httpx.AsyncClient
        Shared HTTP client for web search and LLM calls.
    high_threshold : float, optional
        Above this score, context is considered correct. Default from settings.
    low_threshold : float, optional
        Below this score, context is considered incorrect. Default from settings.
    """
    if not settings.CRAG_ENABLED:
        return GateResult(verdict="correct", chunks=tuple(chunks))

    high = high_threshold if high_threshold is not None else settings.CRAG_HIGH_THRESHOLD
    low = low_threshold if low_threshold is not None else settings.CRAG_LOW_THRESHOLD

    # No results at all → INCORRECT
    if not chunks:
        logger.info("CRAG gate: no retrieval results, falling back to web search")
        web_results = await web_search(query, client)
        return GateResult(
            verdict="incorrect",
            chunks=tuple(web_results),
            web_results_added=len(web_results),
        )

    # Get the top score (prefer rerank_score, fall back to score)
    top_score = chunks[0].get("rerank_score", chunks[0].get("score", 0.0))

    if top_score >= high:
        logger.debug("CRAG gate: CORRECT (top_score=%.3f >= %.3f)", top_score, high)
        return GateResult(verdict="correct", chunks=tuple(chunks))

    if top_score >= low:
        # AMBIGUOUS: supplement with web results
        logger.info("CRAG gate: AMBIGUOUS (%.3f <= top_score=%.3f < %.3f), supplementing with web search",
                     low, top_score, high)
        web_results = await web_search(query, client, top_k=3)
        combined = list(chunks) + web_results
        return GateResult(
            verdict="ambiguous",
            chunks=tuple(combined),
            web_results_added=len(web_results),
        )

    # INCORRECT: discard retrieval context, try web search
    logger.info("CRAG gate: INCORRECT (top_score=%.3f < %.3f), discarding context", top_score, low)
    reformulated = await _reformulate_query(query, client)
    search_query = reformulated or query
    web_results = await web_search(search_query, client, top_k=5)
    return GateResult(
        verdict="incorrect",
        chunks=tuple(web_results),
        web_results_added=len(web_results),
        reformulated_query=reformulated,
    )
