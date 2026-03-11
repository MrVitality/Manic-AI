import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.config import EMBEDDING_MODEL, VECTOR_DIMENSION
from api.database import get_db_optional
from api.http_client import get_client
from api.services.chunking import chunk_text
from api.services.embedding import generate_embedding
from api.services.rag import ensure_qdrant_collection, qdrant_upsert

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class EmbedRequest(BaseModel):
    text: str
    model: Optional[str] = None


class EmbedResponse(BaseModel):
    embedding: List[float]
    model: str
    dimensions: int


class IngestRequest(BaseModel):
    content: str
    filename: str
    content_type: Optional[str] = "text/plain"
    user_id: Optional[str] = None
    collection_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = {}
    chunk_size: int = Field(default=500, ge=1, le=10000)
    chunk_overlap: int = Field(default=50, ge=0)
    backend: Literal["supabase", "qdrant", "both"] = "both"


class IngestResponse(BaseModel):
    document_id: str
    filename: str
    chunks_created: int
    status: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/embed", response_model=EmbedResponse)
async def create_embedding(
    request: EmbedRequest,
    client: httpx.AsyncClient = Depends(get_client),
):
    try:
        model = request.model or EMBEDDING_MODEL
        embedding = await generate_embedding(request.text, model, client=client)
        return EmbedResponse(embedding=embedding, model=model, dimensions=len(embedding))
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Ollama error: {str(e)}")


@router.post("/ingest", response_model=IngestResponse)
async def ingest_document(
    request: IngestRequest,
    db=Depends(get_db_optional),
    client: httpx.AsyncClient = Depends(get_client),
):
    document_id = str(uuid4())
    backend = request.backend or "both"
    qdrant_success = False
    supabase_success = False

    try:
        chunks = chunk_text(request.content, request.chunk_size, request.chunk_overlap)

        # Generate embeddings for all chunks in parallel (key performance improvement)
        chunk_embeddings = await asyncio.gather(
            *[generate_embedding(chunk["content"], client=client) for chunk in chunks],
            return_exceptions=True,
        )
        failed = [e for e in chunk_embeddings if isinstance(e, BaseException)]
        if failed:
            raise RuntimeError(f"Embedding generation failed for {len(failed)} chunk(s): {failed[0]}")

        # Ingest to Supabase
        if backend in ["supabase", "both"] and db:
            async with db.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(
                        """
                        INSERT INTO rag.documents (id, user_id, filename, content_type, file_size, status, chunk_count, metadata)
                        VALUES ($1, $2, $3, $4, $5, 'processing', $6, $7)
                        """,
                        document_id,
                        request.user_id,
                        request.filename,
                        request.content_type,
                        len(request.content),
                        len(chunks),
                        json.dumps(request.metadata),
                    )
                    if request.collection_id:
                        await conn.execute(
                            """
                            INSERT INTO rag.document_collections (document_id, collection_id)
                            VALUES ($1, $2) ON CONFLICT DO NOTHING
                            """,
                            document_id,
                            request.collection_id,
                        )
                    for i, chunk in enumerate(chunks):
                        embedding_str = "[" + ",".join(str(x) for x in chunk_embeddings[i]) + "]"
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
                            json.dumps({"start": chunk["start"], "end": chunk["end"]}),
                        )
                    await conn.execute(
                        "UPDATE rag.documents SET status = 'completed' WHERE id = $1",
                        document_id,
                    )
            supabase_success = True

        # Ingest to Qdrant
        if backend in ["qdrant", "both"]:
            await ensure_qdrant_collection("documents", VECTOR_DIMENSION, client)
            qdrant_points = []
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
                        "created_at": datetime.utcnow().isoformat(),
                    },
                })
            qdrant_success = await qdrant_upsert("documents", qdrant_points, client)

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
        elif backend == "supabase":
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
                async with db.acquire() as conn:
                    await conn.execute(
                        "UPDATE rag.documents SET status = 'failed', error_message = $2 WHERE id = $1",
                        document_id,
                        str(e),
                    )
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=str(e))
