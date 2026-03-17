"""Supabase document and collection CRUD repository."""

import json
import logging
from typing import Any, Dict, List, Optional

import asyncpg

logger = logging.getLogger(__name__)


class SupabaseDocumentRepository:
    """Encapsulates all raw SQL for documents, collections, and chunks."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # ------------------------------------------------------------------
    # Documents
    # ------------------------------------------------------------------

    async def list_documents(
        self,
        user_id: Optional[str] = None,
        collection_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        async with self._pool.acquire() as conn:
            results = await conn.fetch(
                """
                SELECT
                    d.id::text,
                    d.filename,
                    d.content_type,
                    d.file_size,
                    d.status,
                    d.chunk_count,
                    d.metadata,
                    d.created_at,
                    d.updated_at
                FROM rag.documents d
                LEFT JOIN rag.document_collections dc ON d.id = dc.document_id
                WHERE
                    ($1::uuid IS NULL OR d.user_id = $1::uuid)
                    AND ($2::uuid IS NULL OR dc.collection_id = $2::uuid)
                    AND ($3::text IS NULL OR d.status = $3)
                ORDER BY d.created_at DESC
                LIMIT $4
                """,
                user_id, collection_id, status, limit,
            )
        return [
            {
                "id": r["id"],
                "filename": r["filename"],
                "content_type": r["content_type"],
                "file_size": r["file_size"],
                "status": r["status"],
                "chunk_count": r["chunk_count"],
                "metadata": json.loads(r["metadata"]) if r["metadata"] else {},
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
            }
            for r in results
        ]

    async def delete_document(self, document_id: str) -> bool:
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM rag.documents WHERE id = $1", document_id,
            )
            return result != "DELETE 0"

    async def insert_document(
        self,
        document_id: str,
        user_id: Optional[str],
        filename: str,
        content_type: str,
        file_size: int,
        chunk_count: int,
        metadata: str,
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO rag.documents (id, user_id, filename, content_type, file_size, status, chunk_count, metadata)
                VALUES ($1, $2, $3, $4, $5, 'processing', $6, $7)
                """,
                document_id, user_id, filename, content_type, file_size, chunk_count, metadata,
            )

    async def link_document_collection(
        self,
        document_id: str,
        collection_id: str,
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO rag.document_collections (document_id, collection_id)
                VALUES ($1, $2) ON CONFLICT DO NOTHING
                """,
                document_id, collection_id,
            )

    async def insert_chunk(
        self,
        document_id: str,
        chunk_index: int,
        content: str,
        content_tokens: int,
        embedding_str: str,
        metadata: str,
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO rag.chunks (document_id, chunk_index, content, content_tokens, embedding, metadata)
                VALUES ($1, $2, $3, $4, $5::vector, $6)
                """,
                document_id, chunk_index, content, content_tokens, embedding_str, metadata,
            )

    async def insert_document_with_chunks(
        self,
        document_id: str,
        user_id: Optional[str],
        filename: str,
        content_type: str,
        file_size: int,
        chunk_count: int,
        metadata_json: str,
        collection_id: Optional[str],
        chunks: List[Dict[str, Any]],
        chunk_embeddings: List[List[float]],
        raw_content: Optional[str] = None,
    ) -> None:
        """Transactionally insert a document and all its chunks."""
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO rag.documents (id, user_id, filename, content_type, file_size, status, chunk_count, metadata, raw_content)
                    VALUES ($1, $2, $3, $4, $5, 'processing', $6, $7, $8)
                    """,
                    document_id, user_id, filename, content_type, file_size, chunk_count, metadata_json, raw_content,
                )
                if collection_id:
                    await conn.execute(
                        """
                        INSERT INTO rag.document_collections (document_id, collection_id)
                        VALUES ($1, $2) ON CONFLICT DO NOTHING
                        """,
                        document_id, collection_id,
                    )
                for i, chunk in enumerate(chunks):
                    embedding_str = "[" + ",".join(str(x) for x in chunk_embeddings[i]) + "]"
                    chunk_meta: Dict[str, Any] = {
                        "start": chunk["start"],
                        "end": chunk["end"],
                    }
                    if "parent_content" in chunk:
                        chunk_meta["parent_content"] = chunk["parent_content"]
                    if "header" in chunk:
                        chunk_meta["header"] = chunk["header"]
                    await conn.execute(
                        """
                        INSERT INTO rag.chunks (document_id, chunk_index, content, content_tokens, embedding, metadata)
                        VALUES ($1, $2, $3, $4, $5::vector, $6)
                        """,
                        document_id,
                        chunk["index"],
                        chunk["content"],
                        len(chunk["content"]) // 4,
                        embedding_str,
                        json.dumps(chunk_meta),
                    )
                await conn.execute(
                    "UPDATE rag.documents SET status = 'completed' WHERE id = $1",
                    document_id,
                )

    async def mark_document_completed(self, document_id: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE rag.documents SET status = 'completed' WHERE id = $1",
                document_id,
            )

    async def mark_document_failed(self, document_id: str, error: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE rag.documents SET status = 'failed', error_message = $2 WHERE id = $1",
                document_id, error,
            )

    # ------------------------------------------------------------------
    # Collections
    # ------------------------------------------------------------------

    async def list_collections(
        self,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        async with self._pool.acquire() as conn:
            results = await conn.fetch(
                """
                SELECT
                    c.id::text,
                    c.name,
                    c.description,
                    c.is_public,
                    c.embedding_model,
                    c.metadata,
                    c.created_at,
                    COUNT(dc.document_id) as document_count
                FROM rag.collections c
                LEFT JOIN rag.document_collections dc ON c.id = dc.collection_id
                WHERE ($1::uuid IS NULL OR c.user_id = $1::uuid OR c.is_public = TRUE)
                GROUP BY c.id
                ORDER BY c.created_at DESC
                """,
                user_id,
            )
        return [
            {
                "id": r["id"],
                "name": r["name"],
                "description": r["description"],
                "is_public": r["is_public"],
                "embedding_model": r["embedding_model"],
                "metadata": json.loads(r["metadata"]) if r["metadata"] else {},
                "document_count": r["document_count"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in results
        ]

    async def create_collection(
        self,
        collection_id: str,
        user_id: Optional[str],
        name: str,
        description: Optional[str],
        is_public: bool,
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO rag.collections (id, user_id, name, description, is_public)
                VALUES ($1, $2, $3, $4, $5)
                """,
                collection_id, user_id, name, description, is_public,
            )

    async def delete_collection(self, collection_id: str) -> bool:
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM rag.collections WHERE id = $1", collection_id,
            )
            return result != "DELETE 0"

    # ------------------------------------------------------------------
    # Chunks
    # ------------------------------------------------------------------

    async def get_document_chunks(
        self,
        document_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        async with self._pool.acquire() as conn:
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM rag.chunks WHERE document_id = $1", document_id,
            )
            rows = await conn.fetch(
                """
                SELECT id::text, chunk_index, content, content_tokens, metadata, created_at
                FROM rag.chunks WHERE document_id = $1
                ORDER BY chunk_index LIMIT $2 OFFSET $3
                """,
                document_id, limit, offset,
            )
        chunks = [
            {
                "id": r["id"],
                "chunk_index": r["chunk_index"],
                "content": r["content"],
                "content_tokens": r["content_tokens"],
                "metadata": json.loads(r["metadata"]) if r["metadata"] else {},
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
        return {"chunks": chunks, "total": total}

    async def get_document_filenames(
        self,
        document_ids: List[str],
    ) -> Dict[str, str]:
        if not document_ids:
            return {}
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id::text, filename FROM rag.documents WHERE id = ANY($1::uuid[])",
                document_ids,
            )
        return {r["id"]: r["filename"] for r in rows}

    # ------------------------------------------------------------------
    # Analytics helpers
    # ------------------------------------------------------------------

    async def rag_analytics(self) -> Dict[str, Any]:
        async with self._pool.acquire() as conn:
            doc_stats = await conn.fetch(
                "SELECT status, COUNT(*) AS count FROM rag.documents GROUP BY status",
            )
            by_status = {r["status"]: r["count"] for r in doc_stats}
            total_docs = sum(by_status.values())

            chunk_row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*)                              AS total,
                    COALESCE(AVG(content_tokens), 0)      AS avg_tokens,
                    COALESCE(SUM(content_tokens), 0)      AS total_tokens
                FROM rag.chunks
                """,
            )

            coll_row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*)                  AS total,
                    COALESCE(AVG(doc_count), 0) AS avg_docs
                FROM (
                    SELECT c.id, COUNT(dc.document_id) AS doc_count
                    FROM rag.collections c
                    LEFT JOIN rag.document_collections dc ON c.id = dc.collection_id
                    GROUP BY c.id
                ) sub
                """,
            )

        return {
            "documents": {"total": total_docs, "by_status": by_status},
            "chunks": {
                "total": chunk_row["total"],
                "avg_per_document": round(chunk_row["total"] / max(total_docs, 1), 1),
                "total_tokens": chunk_row["total_tokens"],
            },
            "searches": {
                "total": 0,
                "avg_results": 0.0,
                "avg_score": 0.0,
                "avg_latency_ms": 0.0,
            },
            "collections": {
                "total": coll_row["total"],
                "avg_documents_per_collection": round(float(coll_row["avg_docs"]), 1),
            },
        }

    async def rag_stats(self, embedding_model: str, vector_dimension: int) -> Dict[str, Any]:
        async with self._pool.acquire() as conn:
            doc_count = await conn.fetchval("SELECT COUNT(*) FROM rag.documents")
            chunk_row = await conn.fetchrow(
                "SELECT COUNT(*) as total, COALESCE(AVG(content_tokens), 0) as avg_tokens FROM rag.chunks",
            )
            coll_count = await conn.fetchval("SELECT COUNT(*) FROM rag.collections")
            storage = await conn.fetchval("SELECT COALESCE(SUM(file_size), 0) FROM rag.documents")
            by_type = await conn.fetch(
                "SELECT content_type, COUNT(*) as count FROM rag.documents GROUP BY content_type",
            )
            recent = await conn.fetch(
                """SELECT id::text as document_id, filename, chunk_count as chunks_created, status, created_at
                   FROM rag.documents ORDER BY created_at DESC LIMIT 10""",
            )

        return {
            "total_documents": doc_count,
            "total_chunks": chunk_row["total"],
            "total_collections": coll_count,
            "storage_bytes": storage,
            "avg_chunk_tokens": round(float(chunk_row["avg_tokens"]), 1),
            "embedding_model": embedding_model,
            "vector_dimension": vector_dimension,
            "index_type": "pgvector (ivfflat)",
            "documents_by_type": {r["content_type"]: r["count"] for r in by_type},
            "recent_ingestions": [
                {
                    "document_id": r["document_id"],
                    "filename": r["filename"],
                    "chunks_created": r["chunks_created"],
                    "status": r["status"],
                    "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                }
                for r in recent
            ],
        }
