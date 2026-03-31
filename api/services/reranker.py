"""Cross-encoder reranking with FlashRank (fast) or Ollama LLM (fallback).

After hybrid search retrieves candidate chunks, this module reranks them
by relevance to the user query.

Supports three modes:
- "flashrank" (default): Uses an 80MB ONNX cross-encoder model (~50ms on CPU).
  Fastest and most accurate. Falls back to "batch" if FlashRank is unavailable.
- "batch": Scores all candidates in a single LLM call via
  cross_encoder.cross_encode_rerank().
- "individual" (legacy): Scores each candidate with a separate LLM call.

Configure via the ``reranker_mode`` parameter, settings.RERANKER_MODE, or env var.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Literal, Optional

import httpx

from api.config import settings
from api.services.cross_encoder import cross_encode_rerank
from api.services.flashrank_reranker import flashrank_rerank, is_available as flashrank_available

logger = logging.getLogger(__name__)

# Default reranking parameters
DEFAULT_RERANK_TOP_N = 5
DEFAULT_RERANKER_MODE: Literal["flashrank", "batch", "individual"] = getattr(
    settings, "RERANKER_MODE", "flashrank"
)
RERANK_MODEL = None  # uses settings.CHAT_MODEL if not overridden

_SCORING_PROMPT_TEMPLATE = (
    "You are a relevance scoring assistant. Rate how relevant the following "
    "document chunk is to the given query on a scale from 0 to 10, where "
    "0 means completely irrelevant and 10 means perfectly relevant.\n\n"
    "Query: {query}\n\n"
    "Document chunk:\n{chunk}\n\n"
    "Respond with ONLY a JSON object: {{\"score\": <number>}}\n"
    "Do not include any other text."
)


async def _score_chunk(
    query: str,
    chunk: Dict[str, Any],
    client: httpx.AsyncClient,
    model: str,
) -> float:
    """Score a single chunk's relevance to the query using Ollama (individual mode)."""
    prompt = _SCORING_PROMPT_TEMPLATE.format(
        query=query,
        chunk=chunk.get("content", "")[:1000],  # limit chunk size sent to LLM
    )
    try:
        response = await client.post(
            f"{settings.OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0.0},
            },
            timeout=30.0,
        )
        response.raise_for_status()
        content = response.json().get("message", {}).get("content", "")
        # Parse the score from the JSON response
        parsed = json.loads(content.strip())
        score = float(parsed.get("score", 0))
        return max(0.0, min(10.0, score))
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        logger.warning("Failed to parse reranker score: %s", exc)
        return 0.0
    except httpx.HTTPError as exc:
        logger.warning("Reranker LLM request failed: %s", exc)
        return 0.0


async def _rerank_individual(
    query: str,
    chunks: List[Dict[str, Any]],
    client: httpx.AsyncClient,
    top_n: int,
    model: str,
) -> List[Dict[str, Any]]:
    """Legacy individual scoring: one LLM call per candidate chunk."""
    scores = await asyncio.gather(
        *[_score_chunk(query, chunk, client, model) for chunk in chunks],
        return_exceptions=True,
    )

    scored_chunks: List[Dict[str, Any]] = []
    for chunk, score in zip(chunks, scores):
        rerank_score = score if isinstance(score, float) else 0.0
        scored_chunks.append({**chunk, "rerank_score": rerank_score})

    scored_chunks.sort(
        key=lambda c: (c.get("rerank_score", 0), c.get("score", 0)),
        reverse=True,
    )
    return scored_chunks[:top_n]


def _normalize_rerank_scores(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize rerank_score to 0.0-1.0 range regardless of reranker backend.

    FlashRank already produces 0-1 scores. LLM rerankers produce 0-10 scores.
    This ensures downstream consumers (CRAG gate, etc.) see a consistent range.
    """
    return [
        {**chunk, "rerank_score": chunk["rerank_score"] / 10.0}
        if chunk.get("rerank_score", 0.0) > 1.0
        else chunk
        for chunk in chunks
    ]


async def rerank_chunks(
    query: str,
    chunks: List[Dict[str, Any]],
    client: httpx.AsyncClient,
    top_n: int = DEFAULT_RERANK_TOP_N,
    model: Optional[str] = None,
    reranker_mode: Literal["flashrank", "batch", "individual"] = DEFAULT_RERANKER_MODE,
) -> List[Dict[str, Any]]:
    """Rerank search result chunks by cross-encoder relevance scoring.

    Takes candidate chunks (typically top-20 from hybrid search) and
    returns the top_n most relevant ones based on cross-encoder scoring.

    Each returned chunk gets an additional ``rerank_score`` field (0.0-1.0).
    The original ``score`` from the retrieval stage is preserved.

    Parameters
    ----------
    query : str
        The user query.
    chunks : list of dict
        Candidate chunks from retrieval.
    client : httpx.AsyncClient
        Shared HTTP client.
    top_n : int
        Number of top results to return.
    model : str, optional
        Override the scoring model (only used for LLM-based modes).
    reranker_mode : "flashrank" | "batch" | "individual"
        "flashrank" (default): fast CPU cross-encoder (~50ms).
        "batch": single LLM call for all candidates.
        "individual" (legacy): one LLM call per candidate.
    """
    if not chunks:
        return []

    # --- FlashRank (only when explicitly requested) ---
    if reranker_mode == "flashrank":
        if flashrank_available():
            try:
                result = await flashrank_rerank(query=query, chunks=chunks, top_n=top_n)
                return _normalize_rerank_scores(result)
            except RuntimeError:
                logger.warning("FlashRank reranking failed, falling back to LLM batch")
        # fall through to batch LLM

    # --- LLM batch reranking ---
    rerank_model = model or RERANK_MODEL or settings.CHAT_MODEL

    if reranker_mode in ("flashrank", "batch"):
        try:
            result = await cross_encode_rerank(
                query=query,
                chunks=chunks,
                top_n=top_n,
                http_client=client,
                model=rerank_model,
            )
            return _normalize_rerank_scores(result)
        except RuntimeError:
            logger.warning(
                "Batch reranking failed, falling back to individual scoring"
            )

    # --- Individual LLM scoring (last resort) ---
    result = await _rerank_individual(query, chunks, client, top_n, rerank_model)
    return _normalize_rerank_scores(result)
