"""Query classification and routing for intelligent RAG pipeline control.

Classifies incoming queries into categories to skip RAG for simple questions,
route to keyword-heavy search for exact lookups, or trigger web search for
current events -- reducing latency and improving answer quality.

Two-tier classification:
- Tier 1: Rule-based fast-path (<1ms) for obvious patterns (greetings, math, etc.)
- Tier 2: LLM-based classification (cached in Redis) for ambiguous queries
"""

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from typing import Literal, Optional

import httpx

from api.config import settings

logger = logging.getLogger(__name__)

QueryCategory = Literal["direct_answer", "vector", "keyword", "hybrid", "web_search"]

# Module-level Redis client — injected by init_redis() at app startup.
_redis = None


def _set_redis(client) -> None:
    """Replace the module-level Redis reference."""
    import api.services.query_classifier as _mod
    _mod._redis = client


@dataclass(frozen=True)
class QueryRoute:
    """Result of query classification."""
    category: QueryCategory
    confidence: float
    reasoning: str


# --- Tier 1: Rule-based patterns ---

_GREETING_PATTERNS = re.compile(
    r"^(hi|hello|hey|good\s*(morning|afternoon|evening)|howdy|sup|yo|what'?s\s*up)\b",
    re.IGNORECASE,
)

_MATH_PATTERN = re.compile(
    r"^(what\s+is\s+)?[\d\s\+\-\*\/\(\)\.\^%]+\s*\??$",
    re.IGNORECASE,
)

_TEMPORAL_MARKERS = re.compile(
    r"\b(today|tonight|yesterday|right now|currently|latest|breaking|this week|this month|"
    r"this year|202[4-9]|news|stock price|weather|score)\b",
    re.IGNORECASE,
)

_TRANSLATION_PATTERN = re.compile(
    r"^translate\b|^how\s+do\s+you\s+say\b",
    re.IGNORECASE,
)

_EXACT_LOOKUP_MARKERS = re.compile(
    r"\b(error\s+code|status\s+code|version\s+number|ID|UUID|ISBN|SKU|"
    r"[A-Z]{2,}-\d{2,})\b",
    re.IGNORECASE,
)


def _classify_rule_based(query: str) -> Optional[QueryRoute]:
    """Tier 1: fast rule-based classification (<1ms)."""
    stripped = query.strip()

    if len(stripped) < 4 or _GREETING_PATTERNS.match(stripped):
        return QueryRoute("direct_answer", 0.95, "greeting or very short query")

    if _MATH_PATTERN.match(stripped):
        return QueryRoute("direct_answer", 0.90, "math expression")

    if _TRANSLATION_PATTERN.match(stripped):
        return QueryRoute("direct_answer", 0.85, "translation request")

    if _TEMPORAL_MARKERS.search(stripped):
        return QueryRoute("web_search", 0.80, "temporal/current-events marker detected")

    if _EXACT_LOOKUP_MARKERS.search(stripped):
        return QueryRoute("keyword", 0.75, "exact term/code lookup detected")

    return None


# --- Tier 2: LLM-based classification ---

_CLASSIFICATION_PROMPT = (
    "Classify the following user query into exactly one category. "
    "Respond with ONLY a JSON object.\n\n"
    "Categories:\n"
    '- "direct_answer": Simple factual questions, greetings, math, definitions '
    "that don't need document retrieval\n"
    '- "vector": Conceptual/semantic questions about topics in a knowledge base\n'
    '- "keyword": Exact term lookups, error codes, specific identifiers\n'
    '- "hybrid": Complex questions needing both semantic and keyword matching (default)\n'
    '- "web_search": Current events, real-time data, things unlikely in a local knowledge base\n\n'
    "Query: {query}\n\n"
    'Respond with: {{"category": "<category>", "confidence": <0.0-1.0>, "reasoning": "<brief>"}}'
)


def _cache_key(query: str) -> str:
    """Deterministic cache key for a normalized query."""
    normalized = query.strip().lower()
    digest = hashlib.sha256(normalized.encode()).hexdigest()
    return f"manic:qclass:{digest}"


async def _classify_with_llm(query: str, client: httpx.AsyncClient) -> QueryRoute:
    """Tier 2: LLM-based classification with Redis caching."""
    # Check cache
    if _redis:
        try:
            cached = await _redis.get(_cache_key(query))
            if cached:
                data = json.loads(cached)
                return QueryRoute(**data)
        except Exception as exc:
            logger.debug("Query classification cache miss: %s", exc)

    try:
        prompt = _CLASSIFICATION_PROMPT.format(query=query)
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
        content = response.json().get("message", {}).get("content", "")
        parsed = json.loads(content.strip())

        category = parsed.get("category", "hybrid")
        if category not in ("direct_answer", "vector", "keyword", "hybrid", "web_search"):
            category = "hybrid"

        route = QueryRoute(
            category=category,
            confidence=min(1.0, max(0.0, float(parsed.get("confidence", 0.5)))),
            reasoning=str(parsed.get("reasoning", "LLM classification")),
        )

        # Cache result
        if _redis:
            try:
                cache_data = json.dumps({
                    "category": route.category,
                    "confidence": route.confidence,
                    "reasoning": route.reasoning,
                })
                await _redis.setex(
                    _cache_key(query),
                    settings.QUERY_CLASSIFICATION_CACHE_TTL,
                    cache_data,
                )
            except Exception as exc:
                logger.debug("Query classification cache write failed: %s", exc)

        return route

    except Exception as exc:
        logger.warning("LLM query classification failed: %s", exc)
        return QueryRoute("hybrid", 0.5, f"classification failed: {exc}")


async def classify_query(
    query: str,
    client: httpx.AsyncClient,
) -> QueryRoute:
    """Classify a query to determine the optimal retrieval strategy.

    Uses a two-tier approach:
    1. Rule-based patterns for obvious cases (<1ms)
    2. LLM classification for ambiguous queries (cached)

    When classification confidence is below 0.7, defaults to "hybrid" (safe fallback).
    """
    if not settings.QUERY_CLASSIFICATION_ENABLED:
        return QueryRoute("hybrid", 1.0, "classification disabled")

    # Tier 1: rule-based
    rule_result = _classify_rule_based(query)
    if rule_result and rule_result.confidence >= 0.7:
        logger.debug("Query classified by rules: %s (%s)", rule_result.category, rule_result.reasoning)
        return rule_result

    # Tier 2: LLM-based
    llm_result = await _classify_with_llm(query, client)

    # Low confidence → safe fallback
    if llm_result.confidence < 0.7:
        logger.debug("Low confidence classification (%.2f), falling back to hybrid", llm_result.confidence)
        return QueryRoute("hybrid", 0.7, f"low confidence fallback (was: {llm_result.category})")

    logger.debug("Query classified by LLM: %s (%.2f)", llm_result.category, llm_result.confidence)
    return llm_result
