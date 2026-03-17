import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import asyncpg
import httpx

from api.config import OLLAMA_URL, QDRANT_URL

logger = logging.getLogger(__name__)


async def vector_search(
    query_embedding: List[float],
    db: asyncpg.Pool,
    top_k: int = 5,
    threshold: float = 0.7,
    collection_id: str = None,
    user_id: str = None,
) -> List[Dict]:
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
    async with db.acquire() as conn:
        results = await conn.fetch(
            """
            SELECT
                c.id::text,
                c.document_id::text,
                c.content,
                c.metadata,
                1 - (c.embedding <=> $1::vector) as similarity
            FROM rag.chunks c
            JOIN rag.documents d ON c.document_id = d.id
            LEFT JOIN rag.document_collections dc ON c.document_id = dc.document_id
            WHERE
                ($2::uuid IS NULL OR dc.collection_id = $2::uuid)
                AND ($3::uuid IS NULL OR d.user_id = $3::uuid)
                AND 1 - (c.embedding <=> $1::vector) > $4
            ORDER BY c.embedding <=> $1::vector
            LIMIT $5
            """,
            embedding_str, collection_id, user_id, threshold, top_k,
        )
    return [
        {
            "id": r["id"],
            "document_id": r["document_id"],
            "content": r["content"],
            "metadata": json.loads(r["metadata"]) if r["metadata"] else {},
            "score": float(r["similarity"]),
        }
        for r in results
    ]


async def hybrid_search(
    query_text: str,
    query_embedding: List[float],
    db: asyncpg.Pool,
    top_k: int = 5,
    keyword_weight: float = 0.3,
    collection_id: str = None,
    user_id: str = None,
) -> List[Dict]:
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
    async with db.acquire() as conn:
        results = await conn.fetch(
            """
            SELECT
                id::text,
                document_id::text,
                content,
                metadata,
                vector_score,
                keyword_score,
                combined_score as score
            FROM rag.hybrid_search($1, $2::vector, $3, $4, $5::uuid, $6::uuid)
            """,
            query_text, embedding_str, top_k, keyword_weight, collection_id, user_id,
        )
    return [
        {
            "id": r["id"],
            "document_id": r["document_id"],
            "content": r["content"],
            "metadata": json.loads(r["metadata"]) if r["metadata"] else {},
            "score": float(r["score"]),
            "vector_score": float(r["vector_score"]),
            "keyword_score": float(r["keyword_score"]),
        }
        for r in results
    ]


def build_rag_prompt(query: str, context_chunks: List[Dict]) -> str:
    if not context_chunks:
        return query
    context = "\n\n---\n\n".join(
        [f"[Source {i+1}]: {chunk['content']}" for i, chunk in enumerate(context_chunks)]
    )
    return (
        "Use the following context to answer the question. "
        "If the context doesn't contain relevant information, say so and answer based on your general knowledge.\n\n"
        f"Context:\n{context}\n\nQuestion: {query}\n\nAnswer:"
    )


async def qdrant_search(
    query_embedding: List[float],
    client: httpx.AsyncClient,
    collection_name: str = "documents",
    top_k: int = 5,
    threshold: float = 0.7,
    filters: Dict[str, Any] = None,
) -> List[Dict]:
    payload: Dict[str, Any] = {
        "vector": query_embedding,
        "limit": top_k,
        "score_threshold": threshold,
        "with_payload": True,
        "with_vectors": False,
    }
    if filters:
        payload["filter"] = {
            "must": [{"key": k, "match": {"value": v}} for k, v in filters.items() if v]
        }
    try:
        response = await client.post(
            f"{QDRANT_URL}/collections/{collection_name}/points/search",
            json=payload,
            timeout=30.0,
        )
        response.raise_for_status()
        return [
            {
                "id": str(r["id"]),
                "document_id": r.get("payload", {}).get("document_id", ""),
                "content": r.get("payload", {}).get("content", ""),
                "metadata": r.get("payload", {}).get("metadata", {}),
                "score": float(r["score"]),
                "backend": "qdrant",
            }
            for r in response.json().get("result", [])
        ]
    except Exception as e:
        logger.error("Qdrant search: %s", e)
        return []


async def qdrant_upsert(
    collection_name: str,
    points: List[Dict],
    client: httpx.AsyncClient,
) -> bool:
    try:
        response = await client.put(
            f"{QDRANT_URL}/collections/{collection_name}/points",
            json={"points": points},
            timeout=60.0,
        )
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error("Qdrant upsert: %s", e)
        return False


async def qdrant_delete_by_document(
    collection_name: str,
    document_id: str,
    client: httpx.AsyncClient,
) -> bool:
    try:
        response = await client.post(
            f"{QDRANT_URL}/collections/{collection_name}/points/delete",
            json={
                "filter": {
                    "must": [{"key": "document_id", "match": {"value": document_id}}]
                }
            },
            timeout=30.0,
        )
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error("Qdrant delete: %s", e)
        return False


async def ensure_qdrant_collection(
    collection_name: str,
    vector_size: int,
    client: httpx.AsyncClient,
) -> bool:
    try:
        r = await client.get(f"{QDRANT_URL}/collections/{collection_name}", timeout=10.0)
        if r.status_code == 200:
            return True
        r = await client.put(
            f"{QDRANT_URL}/collections/{collection_name}",
            json={"vectors": {"size": vector_size, "distance": "Cosine"}},
            timeout=10.0,
        )
        return r.status_code in [200, 201]
    except Exception as e:
        logger.error("Qdrant ensure collection: %s", e)
        return False


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
