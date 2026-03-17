"""Document ingestion business logic."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

import asyncpg
import httpx

from api.config import settings
from api.repositories.qdrant_vector import QdrantVectorRepository
from api.repositories.supabase_documents import SupabaseDocumentRepository
from api.schemas.ingest import IngestRequest, IngestResponse
from api.services.chunking import chunk_text
from api.services.embedding import generate_embedding

logger = logging.getLogger(__name__)


async def ingest_document(
    request: IngestRequest,
    db: Optional[asyncpg.Pool],
    client: httpx.AsyncClient,
) -> IngestResponse:
    """Chunk, embed, and store a document in the requested backend(s)."""
    document_id = str(uuid4())
    backend = request.backend or "both"
    qdrant_success = False
    supabase_success = False

    try:
        chunks = chunk_text(request.content, request.chunk_size, request.chunk_overlap)

        chunk_embeddings = await asyncio.gather(
            *[generate_embedding(chunk["content"], client=client) for chunk in chunks],
            return_exceptions=True,
        )
        failed = [e for e in chunk_embeddings if isinstance(e, BaseException)]
        if failed:
            raise RuntimeError(f"Embedding generation failed for {len(failed)} chunk(s): {failed[0]}")

        # Ingest to Supabase
        if backend in ["supabase", "both"] and db:
            doc_repo = SupabaseDocumentRepository(db)
            await doc_repo.insert_document_with_chunks(
                document_id=document_id,
                user_id=request.user_id,
                filename=request.filename,
                content_type=request.content_type or "text/plain",
                file_size=len(request.content),
                chunk_count=len(chunks),
                metadata_json=json.dumps(request.metadata or {}),
                collection_id=request.collection_id,
                chunks=chunks,
                chunk_embeddings=chunk_embeddings,
            )
            supabase_success = True

        # Ingest to Qdrant
        if backend in ["qdrant", "both"]:
            qdrant = QdrantVectorRepository(settings.QDRANT_URL, client)
            await qdrant.ensure_collection("documents", settings.VECTOR_DIMENSION)
            qdrant_points: List[Dict[str, Any]] = []
            for i, chunk in enumerate(chunks):
                point_id = str(uuid4())
                qdrant_points.append({
                    "id": point_id,
                    "vector": chunk_embeddings[i],
                    "payload": {
                        "document_id": document_id,
                        "chunk_index": chunk["index"],
                        "content": chunk["content"],
                        "filename": request.filename,
                        "user_id": request.user_id,
                        "collection_id": request.collection_id,
                        "metadata": request.metadata or {},
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    },
                })
            qdrant_success = await qdrant.upsert("documents", qdrant_points)

        # Determine final status
        if backend == "both":
            if supabase_success and qdrant_success:
                status = "completed"
            elif supabase_success or qdrant_success:
                status = "partial"
            else:
                status = "failed"
        elif backend == "qdrant":
            status = "completed" if qdrant_success else "failed"
        else:
            status = "completed" if supabase_success else "failed"

        return IngestResponse(
            document_id=document_id,
            filename=request.filename,
            chunks_created=len(chunks),
            status=status,
        )

    except Exception as e:
        if db and backend in ["supabase", "both"]:
            try:
                doc_repo = SupabaseDocumentRepository(db)
                await doc_repo.mark_document_failed(document_id, str(e))
            except Exception:
                logger.warning("Failed to update document status to 'failed' for %s", document_id)
        logger.exception("Document ingestion failed for %s", request.filename)
        raise
