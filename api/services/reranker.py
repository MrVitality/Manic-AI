"""Cross-encoder reranking using Ollama LLM scoring.

After hybrid search retrieves candidate chunks, this module reranks them
by asking the LLM to score each chunk's relevance to the query.
"""

import json
import logging
from typing import Any, Dict, List

import httpx

from api.config import settings

logger = logging.getLogger(__name__)

# Default reranking parameters
DEFAULT_RERANK_TOP_N = 5
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
    """Score a single chunk's relevance to the query using Ollama."""
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


async def rerank_chunks(
    query: str,
    chunks: List[Dict[str, Any]],
    client: httpx.AsyncClient,
    top_n: int = DEFAULT_RERANK_TOP_N,
    model: str = None,
) -> List[Dict[str, Any]]:
    """Rerank search result chunks by LLM-scored relevance.

    Takes candidate chunks (typically top-20 from hybrid search) and
    returns the top_n most relevant ones based on cross-encoder scoring.

    Each returned chunk gets an additional ``rerank_score`` field (0-10).
    The original ``score`` from the retrieval stage is preserved.
    """
    if not chunks:
        return []

    rerank_model = model or RERANK_MODEL or settings.CHAT_MODEL

    # Score all chunks concurrently
    import asyncio
    scores = await asyncio.gather(
        *[_score_chunk(query, chunk, client, rerank_model) for chunk in chunks],
        return_exceptions=True,
    )

    scored_chunks: List[Dict[str, Any]] = []
    for chunk, score in zip(chunks, scores):
        rerank_score = score if isinstance(score, float) else 0.0
        scored_chunk = {**chunk, "rerank_score": rerank_score}
        scored_chunks.append(scored_chunk)

    # Sort by rerank score descending, break ties with original retrieval score
    scored_chunks.sort(
        key=lambda c: (c.get("rerank_score", 0), c.get("score", 0)),
        reverse=True,
    )

    return scored_chunks[:top_n]
