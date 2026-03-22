"""RAG service -- backward-compatible functions delegating to repositories.

The ``check_service`` utility is kept here because it is used by the
health router and background health logger (not strictly a "repository"
concern).  The vector/hybrid search functions are retained as thin wrappers
for any caller that hasn't migrated to the repository layer yet.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import asyncpg
import httpx

from api.config import settings
from api.repositories.qdrant_vector import QdrantVectorRepository
from api.repositories.supabase_vector import SupabaseVectorRepository

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Thin wrappers (delegate to repository classes)
# ---------------------------------------------------------------------------


async def vector_search(
    query_embedding: List[float],
    db: asyncpg.Pool,
    top_k: int = 5,
    threshold: float = 0.7,
    collection_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> List[Dict]:
    repo = SupabaseVectorRepository(db)
    return await repo.vector_search(query_embedding, top_k, threshold, collection_id, user_id)


async def hybrid_search(
    query_text: str,
    query_embedding: List[float],
    db: asyncpg.Pool,
    top_k: int = 5,
    keyword_weight: float = 0.3,
    collection_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> List[Dict]:
    repo = SupabaseVectorRepository(db)
    return await repo.hybrid_search(query_text, query_embedding, top_k, keyword_weight, collection_id, user_id)


def build_rag_prompt(query: str, context_chunks: List[Dict]) -> str:
    from api.services.chat import build_rag_prompt as _build
    return _build(query, context_chunks)


async def qdrant_search(
    query_embedding: List[float],
    client: httpx.AsyncClient,
    collection_name: str = "documents",
    top_k: int = 5,
    threshold: float = 0.7,
    filters: Optional[Dict[str, Any]] = None,
) -> List[Dict]:
    repo = QdrantVectorRepository(settings.QDRANT_URL, client)
    return await repo.search(query_embedding, collection_name, top_k, threshold, filters)


async def qdrant_upsert(
    collection_name: str,
    points: List[Dict],
    client: httpx.AsyncClient,
) -> bool:
    repo = QdrantVectorRepository(settings.QDRANT_URL, client)
    return await repo.upsert(collection_name, points)


async def qdrant_delete_by_document(
    collection_name: str,
    document_id: str,
    client: httpx.AsyncClient,
) -> bool:
    repo = QdrantVectorRepository(settings.QDRANT_URL, client)
    return await repo.delete_by_document(collection_name, document_id)


async def ensure_qdrant_collection(
    collection_name: str,
    vector_size: int,
    client: httpx.AsyncClient,
) -> bool:
    repo = QdrantVectorRepository(settings.QDRANT_URL, client)
    return await repo.ensure_collection(collection_name, vector_size)


# ---------------------------------------------------------------------------
# Utility -- still owned by this module
# ---------------------------------------------------------------------------


async def check_service(
    url: str,
    client: httpx.AsyncClient,
    timeout: float = 5.0,
) -> Dict[str, Any]:
    try:
        start = datetime.now(timezone.utc)
        r = await client.get(url, timeout=timeout)
        latency = (datetime.now(timezone.utc) - start).total_seconds() * 1000
        return {
            "status": "healthy" if r.status_code == 200 else "degraded",
            "latency_ms": round(latency, 1),
        }
    except Exception:
        return {"status": "offline", "latency_ms": None}
