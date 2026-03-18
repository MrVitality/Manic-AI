"""Batch cross-encoder reranking using Ollama LLM scoring.

Instead of making one LLM call per candidate chunk (the "individual" approach),
this module scores ALL candidates in a single prompt, dramatically reducing
latency and Ollama load for reranking.
"""

import json
import logging
import re
from typing import Any, Dict, List

import httpx

from api.config import settings

logger = logging.getLogger(__name__)

_BATCH_SCORING_PROMPT = (
    "You are a relevance scoring assistant. Score the relevance of each "
    "passage below to the given query on a scale of 0 to 10, where 0 means "
    "completely irrelevant and 10 means perfectly relevant.\n\n"
    "Respond with ONLY a JSON array of numbers (scores) in the same order "
    "as the passages. Example: [8, 3, 10, 1]\n"
    "Do not include any other text.\n\n"
    "Query: {query}\n\n"
    "Passages:\n{passages}"
)

# Max characters per passage sent to the LLM to keep total prompt reasonable
_MAX_PASSAGE_CHARS = 500


def _build_passages_text(chunks: List[Dict[str, Any]]) -> str:
    """Format numbered passages for the batch scoring prompt."""
    lines = []
    for i, chunk in enumerate(chunks, 1):
        content = chunk.get("content", "")[:_MAX_PASSAGE_CHARS]
        lines.append(f"{i}. {content}")
    return "\n".join(lines)


def _parse_scores(raw: str, expected_count: int) -> List[float]:
    """Parse a JSON array of scores from the LLM response.

    Applies several heuristics to handle common LLM formatting issues:
    - Strips markdown code fences
    - Extracts the first JSON array found in the text
    - Clamps values to 0-10 range
    """
    # Strip markdown code fences if present
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`")

    # Try to find a JSON array in the response
    match = re.search(r"\[[\d\s,.\-]+\]", cleaned)
    if match:
        cleaned = match.group(0)

    try:
        scores = json.loads(cleaned)
        if isinstance(scores, list):
            result = []
            for s in scores:
                try:
                    val = float(s)
                    result.append(max(0.0, min(10.0, val)))
                except (TypeError, ValueError):
                    result.append(0.0)
            # Pad or truncate to expected count
            while len(result) < expected_count:
                result.append(0.0)
            return result[:expected_count]
    except (json.JSONDecodeError, TypeError):
        pass

    # Fallback: try to extract individual numbers
    numbers = re.findall(r"(\d+(?:\.\d+)?)", cleaned)
    if len(numbers) >= expected_count:
        return [max(0.0, min(10.0, float(n))) for n in numbers[:expected_count]]

    logger.warning(
        "Could not parse %d scores from LLM response (got %d numbers)",
        expected_count,
        len(numbers),
    )
    return [0.0] * expected_count


async def cross_encode_rerank(
    query: str,
    chunks: List[Dict[str, Any]],
    top_n: int,
    http_client: httpx.AsyncClient,
    model: str | None = None,
) -> List[Dict[str, Any]]:
    """Rerank chunks using batch cross-encoder scoring in a single LLM call.

    Sends all candidate passages to the LLM at once and asks for a JSON
    array of relevance scores. Falls back to returning chunks with zero
    scores if the batch call fails (the caller can then retry with
    individual scoring).

    Parameters
    ----------
    query : str
        The user query.
    chunks : list of dict
        Candidate chunks from hybrid search. Each must have a ``content`` key.
    top_n : int
        Number of top-scoring chunks to return.
    http_client : httpx.AsyncClient
        Shared HTTP client for Ollama requests.
    model : str, optional
        Override model for scoring. Defaults to settings.CHAT_MODEL.

    Returns
    -------
    list of dict
        Top-N chunks sorted by relevance, each with a ``rerank_score`` field.

    Raises
    ------
    RuntimeError
        If the batch scoring call fails entirely (caller should fall back).
    """
    if not chunks:
        return []

    scoring_model = model or settings.CHAT_MODEL
    passages_text = _build_passages_text(chunks)
    prompt = _BATCH_SCORING_PROMPT.format(query=query, passages=passages_text)

    try:
        response = await http_client.post(
            f"{settings.OLLAMA_URL}/api/chat",
            json={
                "model": scoring_model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0.0},
            },
            timeout=60.0,  # longer timeout for batch scoring
        )
        response.raise_for_status()
        content = response.json().get("message", {}).get("content", "")
        scores = _parse_scores(content, len(chunks))
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise RuntimeError(f"Batch cross-encoder scoring failed: {exc}") from exc

    scored_chunks = [
        {**chunk, "rerank_score": score}
        for chunk, score in zip(chunks, scores)
    ]
    scored_chunks.sort(
        key=lambda c: (c.get("rerank_score", 0), c.get("score", 0)),
        reverse=True,
    )
    return scored_chunks[:top_n]
