"""FlashRank cross-encoder reranking -- fast CPU-based relevance scoring.

Replaces the LLM-based reranking approach (2-10s per call) with an 80MB ONNX
cross-encoder model that scores all candidates in ~50ms on CPU.

The model is loaded once at module level and reused across requests.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from api.config import settings

logger = logging.getLogger(__name__)

_ranker = None
_init_error: Optional[str] = None


def _get_ranker():
    """Lazily initialize the FlashRank ranker singleton."""
    global _ranker, _init_error
    if _ranker is not None:
        return _ranker
    if _init_error is not None:
        return None
    try:
        from flashrank import Ranker
        _ranker = Ranker(model_name=settings.FLASHRANK_MODEL)
        logger.info("FlashRank ranker initialized (%s)", settings.FLASHRANK_MODEL)
        return _ranker
    except Exception as exc:
        _init_error = str(exc)
        logger.warning("FlashRank initialization failed: %s", exc)
        return None


def _rerank_sync(
    query: str,
    chunks: List[Dict[str, Any]],
    top_n: int,
) -> List[Dict[str, Any]]:
    """Synchronous reranking using FlashRank (runs in ~50ms on CPU)."""
    from flashrank import RerankRequest

    ranker = _get_ranker()
    if ranker is None:
        raise RuntimeError("FlashRank ranker not available")

    passages = []
    for i, chunk in enumerate(chunks):
        passages.append({
            "id": i,
            "text": chunk.get("content", ""),
            "meta": chunk,
        })

    request = RerankRequest(query=query, passages=passages)
    results = ranker.rerank(request)

    scored: List[Dict[str, Any]] = []
    for result in results:
        original_chunk = result["meta"]
        scored.append({
            **original_chunk,
            "rerank_score": float(result["score"]),
        })

    scored.sort(key=lambda c: c["rerank_score"], reverse=True)
    return scored[:top_n]


async def flashrank_rerank(
    query: str,
    chunks: List[Dict[str, Any]],
    top_n: int = 5,
) -> List[Dict[str, Any]]:
    """Async wrapper for FlashRank reranking.

    Runs the synchronous FlashRank model in a thread to avoid blocking
    the async event loop. Total latency is typically ~50ms.

    Returns chunks with a ``rerank_score`` field (0.0-1.0, higher = more relevant).

    Raises RuntimeError if FlashRank is not available.
    """
    if not chunks:
        return []
    return await asyncio.to_thread(_rerank_sync, query, chunks, top_n)


def is_available() -> bool:
    """Check if FlashRank can be used."""
    return _get_ranker() is not None
