"""Supabase pgvector search repository."""

import json
import logging
from typing import Any, Dict, List, Optional

import asyncpg

logger = logging.getLogger(__name__)


class SupabaseVectorRepository:
    """Wraps pgvector similarity and hybrid search queries."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def vector_search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        threshold: float = 0.7,
        collection_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
        async with self._pool.acquire() as conn:
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
        self,
        query_text: str,
        query_embedding: List[float],
        top_k: int = 5,
        keyword_weight: float = 0.3,
        collection_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
        async with self._pool.acquire() as conn:
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
