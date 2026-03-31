"""SearXNG web search integration for RAG fallback.

Provides web search results formatted as RAG chunks, used by:
- Query classifier (web_search route)
- CRAG relevance gate (fallback when retrieval quality is poor)
"""

import logging
from typing import Any, Dict, List
from uuid import uuid4

import httpx

from api.config import settings

logger = logging.getLogger(__name__)


async def web_search(
    query: str,
    client: httpx.AsyncClient,
    top_k: int = 5,
    timeout: float = 3.0,
) -> List[Dict[str, Any]]:
    """Search the web via SearXNG and return results as RAG-compatible chunks.

    Returns results in the same format as vector search chunks:
    ``{id, document_id, content, metadata, score, backend}``.

    Falls back to an empty list on any error (web search is best-effort).
    """
    try:
        response = await client.get(
            f"{settings.SEARXNG_URL}/search",
            params={
                "q": query,
                "format": "json",
                "engines": "google,duckduckgo,brave",
                "pageno": 1,
                "language": "en",
            },
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        logger.warning("SearXNG web search failed: %s", exc)
        return []

    results: List[Dict[str, Any]] = []
    for i, item in enumerate(data.get("results", [])[:top_k]):
        title = item.get("title", "")
        snippet = item.get("content", "")
        url = item.get("url", "")

        # Only allow http/https URLs
        if url and not url.startswith(("http://", "https://")):
            url = ""

        content = f"{title}\n\n{snippet}" if title else snippet

        # Web results should score lower than high-quality vector results
        score = max(0.0, 0.5 - (i * 0.05))  # 0.50, 0.45, 0.40, ...

        results.append({
            "id": str(uuid4()),
            "document_id": f"web-{i}",
            "content": content,
            "metadata": {
                "source": "web_search",
                "url": url,
                "title": title,
                "engine": item.get("engine", ""),
            },
            "score": score,
            "backend": "web_search",
        })

    logger.debug("Web search returned %d results for: %s", len(results), query[:80])
    return results
