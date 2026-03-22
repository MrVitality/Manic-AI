"""Web search plugin using SearXNG."""

import httpx

from api.plugins import tool
from api.config import settings


@tool(name="web_search", description="Search the web for information using SearXNG")
async def web_search(query: str, num_results: int = 5) -> list:
    """Search the web and return results."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{settings.SEARXNG_URL}/search",
            params={"q": query, "format": "json", "categories": "general"},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", ""),
            }
            for r in data.get("results", [])[:num_results]
        ]
