"""Document ingestion business logic."""

import asyncio
import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import asyncpg
import httpx

from api.config import settings
from api.repositories.qdrant_vector import QdrantVectorRepository
from api.repositories.supabase_documents import SupabaseDocumentRepository
from api.schemas.ingest import IngestRequest, IngestResponse
from api.services.chunking import chunk_document, chunk_text
from api.services.context_enricher import enrich_chunks_batch
from api.services.embedding import generate_embedding
from api.services.pii_detector import redact_pii
from api.services.preprocessor import detect_and_extract

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# In-memory job tracker (supplement DB tracking for when DB is unavailable)
# ---------------------------------------------------------------------------
_job_status: Dict[str, Dict[str, Any]] = {}


def _update_job(document_id: str, **fields: Any) -> None:
    """Update the in-memory job record."""
    if document_id not in _job_status:
        _job_status[document_id] = {}
    _job_status[document_id].update(fields, updated_at=datetime.now(timezone.utc).isoformat())


def get_job_status(document_id: str) -> Optional[Dict[str, Any]]:
    """Return the in-memory status dict for a job, or None."""
    return _job_status.get(document_id)


# ---------------------------------------------------------------------------
# Database status helpers
# ---------------------------------------------------------------------------

async def _db_set_status(
    db: asyncpg.Pool,
    document_id: str,
    status: str,
    *,
    chunks_created: Optional[int] = None,
    error: Optional[str] = None,
) -> None:
    """Persist ingestion status to the ingest_jobs table."""
    try:
        async with db.acquire() as conn:
            await conn.execute(
                """
                UPDATE public.ingest_jobs
                SET status = $2,
                    chunks_created = COALESCE($3, chunks_created),
                    error = $4,
                    updated_at = NOW()
                WHERE document_id = $1
                """,
                document_id,
                status,
                chunks_created,
                error,
            )
    except Exception:
        logger.warning("Failed to update ingest_jobs status for %s", document_id)


async def create_ingest_job(
    db: asyncpg.Pool,
    document_id: str,
    filename: str,
) -> None:
    """Insert a new pending row in ingest_jobs."""
    try:
        async with db.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO public.ingest_jobs (document_id, filename, status)
                VALUES ($1, $2, 'pending')
                ON CONFLICT (document_id) DO NOTHING
                """,
                document_id,
                filename,
            )
    except Exception:
        logger.warning("Failed to create ingest_jobs row for %s", document_id)


async def fetch_ingest_job(
    db: asyncpg.Pool,
    document_id: str,
) -> Optional[Dict[str, Any]]:
    """Read a single ingest_jobs row."""
    try:
        async with db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM public.ingest_jobs WHERE document_id = $1",
                document_id,
            )
            return dict(row) if row else None
    except Exception:
        logger.warning("Failed to fetch ingest_jobs row for %s", document_id)
        return None


# ---------------------------------------------------------------------------
# Duplicate detection helpers
# ---------------------------------------------------------------------------

def compute_content_hash(content: str) -> str:
    """Return a SHA-256 hex digest of the UTF-8 encoded content string."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def compute_content_hash_bytes(data: bytes) -> str:
    """Return a SHA-256 hex digest of raw bytes (used for binary content like PDFs)."""
    return hashlib.sha256(data).hexdigest()


async def find_duplicate_document(
    db: asyncpg.Pool,
    content_hash: str,
) -> Optional[str]:
    """Return the existing document_id if a document with this hash is already stored, else None."""
    try:
        async with db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id::text FROM rag.documents WHERE content_hash = $1 LIMIT 1",
                content_hash,
            )
            return row["id"] if row else None
    except Exception:
        logger.warning("Duplicate check query failed for hash %s", content_hash[:16])
        return None


# ---------------------------------------------------------------------------
# Core pipeline (runs synchronously or as a background task)
# ---------------------------------------------------------------------------

async def ingest_document(
    request: IngestRequest,
    db: Optional[asyncpg.Pool],
    client: httpx.AsyncClient,
) -> Tuple[IngestResponse, str]:
    """Chunk, embed, and store a document in the requested backend(s).

    Returns a tuple of ``(IngestResponse, status_flag)`` where ``status_flag``
    is ``"duplicate"`` when a document with the same content hash already exists,
    otherwise ``"new"``.
    """
    document_id = str(uuid4())
    backend = request.backend or "both"
    qdrant_success = False
    supabase_success = False
    start_time = time.perf_counter()

    try:
        # Preprocess content based on content_type
        content = detect_and_extract(request.content, request.content_type or "text/plain")

        # Duplicate detection — hash the raw request content (pre-extraction)
        content_hash = compute_content_hash(request.content)
        if db:
            existing_id = await find_duplicate_document(db, content_hash)
            if existing_id:
                logger.info(
                    "Duplicate document detected for '%s' — existing id=%s",
                    request.filename,
                    existing_id,
                )
                return (
                    IngestResponse(
                        document_id=existing_id,
                        filename=request.filename,
                        chunks_created=0,
                        status="duplicate",
                    ),
                    "duplicate",
                )

        # Redact PII from content before chunking when enabled
        if settings.PII_REDACTION_ENABLED:
            content = redact_pii(content)

        chunks = chunk_document(
            content,
            strategy=request.chunking_strategy,
            chunk_size=request.chunk_size,
            chunk_overlap=request.chunk_overlap,
        )

        # Optional contextual enrichment: prepend LLM-generated context to each chunk
        if request.enrich_context:
            logger.info(
                "Enriching %d chunks with contextual summaries for %s",
                len(chunks),
                request.filename,
            )
            chunks = await enrich_chunks_batch(
                chunks=chunks,
                document_title=request.filename,
                full_content=content,
                http_client=client,
            )

        chunk_embeddings = await asyncio.gather(
            *[generate_embedding(chunk["content"], client=client) for chunk in chunks],
            return_exceptions=True,
        )
        failed = [e for e in chunk_embeddings if isinstance(e, BaseException)]
        if failed:
            raise RuntimeError(f"Embedding generation failed for {len(failed)} chunk(s): {failed[0]}")

        # Compute processing time before writing to DB so it covers the full pipeline
        processing_time_ms = round((time.perf_counter() - start_time) * 1000)

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
                raw_content=request.content,
                processing_time_ms=processing_time_ms,
                content_hash=content_hash,
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

        return (
            IngestResponse(
                document_id=document_id,
                filename=request.filename,
                chunks_created=len(chunks),
                status=status,
            ),
            "new",
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


# ---------------------------------------------------------------------------
# Async background wrapper
# ---------------------------------------------------------------------------

async def run_ingest_background(
    document_id: str,
    request: IngestRequest,
    db: Optional[asyncpg.Pool],
    client: httpx.AsyncClient,
) -> None:
    """Execute the full ingestion pipeline as a background task.

    Updates both in-memory tracker and (if available) the database.
    """
    _update_job(document_id, status="processing")
    if db:
        await _db_set_status(db, document_id, "processing")

    try:
        result, _flag = await ingest_document(request, db, client)
        _update_job(
            document_id,
            status=result.status,
            chunks_created=result.chunks_created,
            filename=result.filename,
        )
        if db:
            await _db_set_status(
                db, document_id, result.status, chunks_created=result.chunks_created,
            )
    except Exception as exc:
        error_msg = str(exc)
        _update_job(document_id, status="failed", error=error_msg)
        if db:
            await _db_set_status(db, document_id, "failed", error=error_msg)
        logger.exception("Background ingestion failed for %s", document_id)
