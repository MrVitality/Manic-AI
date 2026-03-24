"""Ingest and embed routes."""

import logging
from typing import List, Literal, Optional
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request, UploadFile
import asyncpg
import httpx
from pydantic import BaseModel, Field

from api.auth import get_current_user_id
from api.config import settings
from api.middleware.rate_limit import limiter
from api.dependencies import get_db_optional, get_http_client
from api.schemas.envelope import ok
from api.schemas.ingest import (
    EmbedRequest,
    EmbedResponse,
    IngestAccepted,
    IngestRequest,
    IngestStatusResponse,
)
from api.services.embedding import generate_embedding
from api.services.ingestion import (
    compute_content_hash_bytes,
    create_ingest_job,
    fetch_ingest_job,
    find_duplicate_document,
    get_job_status,
    run_ingest_background,
    _update_job,
)
from api.services.multimodal_ingest import ingest_pdf_as_images
from api.services.pii_detector import detect_pii
from api.services.chunking import chunk_document

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/embed", response_model=None, tags=["ingest"])
async def create_embedding(
    body: EmbedRequest,
    client: httpx.AsyncClient = Depends(get_http_client),
):
    try:
        model = body.model or settings.EMBEDDING_MODEL
        embedding = await generate_embedding(body.text, model, client=client)
        return ok(EmbedResponse(embedding=embedding, model=model, dimensions=len(embedding)).model_dump())
    except httpx.HTTPError:
        logger.exception("Embedding generation failed via Ollama")
        raise HTTPException(status_code=502, detail="Embedding service unavailable")


@router.post("/ingest", response_model=None, tags=["ingest"])
@limiter.limit(f"{settings.RATE_LIMIT_INGEST_PER_MINUTE}/minute")
async def ingest_document_endpoint(
    request: Request,
    body: IngestRequest,
    background_tasks: BackgroundTasks,
    db: Optional[asyncpg.Pool] = Depends(get_db_optional),
    client: httpx.AsyncClient = Depends(get_http_client),
):
    """Accept a document for ingestion and process it asynchronously.

    Returns immediately with a ``document_id`` and ``status: processing``.
    Use ``GET /v1/ingest/{document_id}/status`` to poll for completion.

    When ``multimodal=True`` and ``content_type`` is ``application/pdf``,
    the ColPali-style multimodal pipeline is used instead: pages are converted
    to images and described via a vision LLM before embedding.
    """
    # Derive user_id from auth token; fall back to body value in single-key mode.
    effective_user_id = get_current_user_id(request) or body.user_id

    # Route to multimodal pipeline if requested
    if body.multimodal and body.content_type == "application/pdf":
        import base64

        try:
            pdf_bytes = base64.b64decode(body.content)
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Invalid content format for multimodal PDF ingestion.",
            )

        document_id = str(uuid4())
        _update_job(document_id, status="pending", filename=body.filename)
        if db:
            await create_ingest_job(db, document_id, body.filename)

        async def _run_multimodal(doc_id: str):
            from api.services.ingestion import _update_job as _uj, _db_set_status
            _uj(doc_id, status="processing")
            if db:
                await _db_set_status(db, doc_id, "processing")
            try:
                result = await ingest_pdf_as_images(
                    pdf_bytes,
                    body.filename,
                    db,
                    client,
                    collection_id=body.collection_id,
                    user_id=effective_user_id,
                    metadata=body.metadata,
                )
                _uj(doc_id, status=result["status"], chunks_created=result.get("pages_processed", 0))
                if db:
                    await _db_set_status(db, doc_id, result["status"], chunks_created=result.get("pages_processed", 0))
            except Exception as exc:
                _uj(doc_id, status="failed", error=str(exc))
                if db:
                    await _db_set_status(db, doc_id, "failed", error=str(exc))
                logger.exception("Multimodal ingestion failed for %s", doc_id)

        background_tasks.add_task(_run_multimodal, document_id)
        return ok(IngestAccepted(document_id=document_id, status="processing").model_dump())

    document_id = str(uuid4())

    # Seed in-memory tracker
    _update_job(document_id, status="pending", filename=body.filename)

    # Seed database row (best-effort)
    if db:
        await create_ingest_job(db, document_id, body.filename)

    # Propagate the resolved user_id into the request body so the background
    # task stores the correct ownership without trusting client-supplied values.
    if effective_user_id is not None:
        body = body.model_copy(update={"user_id": effective_user_id})

    # Schedule actual work in background
    background_tasks.add_task(run_ingest_background, document_id, body, db, client)

    return ok(IngestAccepted(document_id=document_id, status="processing").model_dump())


@router.get("/ingest/{document_id}/status", response_model=None, tags=["ingest"])
async def ingest_status(
    document_id: str,
    db: Optional[asyncpg.Pool] = Depends(get_db_optional),
):
    """Poll the status of an async ingestion job."""
    # Try database first
    if db:
        row = await fetch_ingest_job(db, document_id)
        if row:
            return ok(
                IngestStatusResponse(
                    document_id=row["document_id"],
                    status=row["status"],
                    filename=row.get("filename"),
                    chunks_created=row.get("chunks_created"),
                    error=row.get("error"),
                    created_at=row.get("created_at"),
                    updated_at=row.get("updated_at"),
                ).model_dump()
            )

    # Fallback to in-memory tracker
    job = get_job_status(document_id)
    if job:
        return ok(
            IngestStatusResponse(
                document_id=document_id,
                status=job.get("status", "pending"),
                filename=job.get("filename"),
                chunks_created=job.get("chunks_created"),
                error=job.get("error"),
            ).model_dump()
        )

    raise HTTPException(status_code=404, detail=f"No ingestion job found for document_id={document_id}")


# ---------------------------------------------------------------------------
# Multipart file upload endpoint
# ---------------------------------------------------------------------------

_ALLOWED_EXTENSIONS = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".html": "text/html",
    ".htm": "text/html",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pdf": "application/pdf",
}


def _detect_content_type(filename: str, mime_hint: Optional[str]) -> str:
    """Return a MIME type string derived from the filename extension.

    Falls back to the ``content_type`` hint from the upload if the extension
    is not explicitly mapped.
    """
    import os
    ext = os.path.splitext(filename.lower())[1]
    return _ALLOWED_EXTENSIONS.get(ext, mime_hint or "text/plain")


@router.post("/ingest/upload", response_model=None, tags=["ingest"])
async def upload_and_ingest(
    request: Request,
    file: UploadFile,
    background_tasks: BackgroundTasks,
    collection_id: Optional[str] = Form(None),
    backend: str = Form("supabase"),
    user_id: Optional[str] = Form(None),
    db: Optional[asyncpg.Pool] = Depends(get_db_optional),
    client: httpx.AsyncClient = Depends(get_http_client),
):
    """Accept a multipart/form-data file upload and ingest it asynchronously.

    Supported file types: ``.txt``, ``.md``, ``.html``, ``.docx``, ``.pdf``

    Returns 202 Accepted immediately with a ``document_id``.
    Use ``GET /v1/ingest/{document_id}/status`` to poll for completion.

    Duplicate files are detected by SHA-256 hash of the raw bytes and return
    ``status: duplicate`` without re-processing.
    """
    import base64
    import os

    filename = file.filename or "upload"
    ext = os.path.splitext(filename.lower())[1]

    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(_ALLOWED_EXTENSIONS)}",
        )

    if backend not in ("supabase", "qdrant", "both"):
        raise HTTPException(
            status_code=400,
            detail="backend must be one of: supabase, qdrant, both",
        )

    raw_bytes: bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    content_type = _detect_content_type(filename, file.content_type)

    # Duplicate detection on raw bytes before doing any work
    if db:
        byte_hash = compute_content_hash_bytes(raw_bytes)
        existing_id = await find_duplicate_document(db, byte_hash)
        if existing_id:
            logger.info("Upload duplicate detected for '%s' — existing id=%s", filename, existing_id)
            return ok({
                "document_id": existing_id,
                "filename": filename,
                "chunks_created": 0,
                "status": "duplicate",
            })

    # Build the IngestRequest payload
    if content_type == "application/pdf":
        # PDF uses base64 binary path
        content_str = base64.b64encode(raw_bytes).decode("ascii")
    elif content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        # .docx: extract text here so the standard pipeline receives plain text
        from api.services.preprocessor import extract_text_from_docx
        content_str = extract_text_from_docx(raw_bytes)
        content_type = "text/plain"
    else:
        try:
            content_str = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=422,
                detail="File content is not valid UTF-8. For binary formats use .pdf or .docx.",
            )

    from api.schemas.ingest import IngestRequest as _IngestRequest

    # Prefer authenticated user_id; fall back to form-supplied value in single-key mode.
    effective_user_id = get_current_user_id(request) or user_id

    ingest_req = _IngestRequest(
        content=content_str,
        filename=filename,
        content_type=content_type,
        user_id=effective_user_id,
        collection_id=collection_id,
        backend=backend,
    )

    document_id = str(uuid4())

    # Seed in-memory tracker
    _update_job(document_id, status="pending", filename=filename)

    # Seed database row (best-effort)
    if db:
        await create_ingest_job(db, document_id, filename)

    # Schedule actual work in the background — return 202 immediately
    background_tasks.add_task(run_ingest_background, document_id, ingest_req, db, client)

    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=202,
        content=ok(IngestAccepted(document_id=document_id, status="processing").model_dump()),
    )


# ---------------------------------------------------------------------------
# PII scan endpoint
# ---------------------------------------------------------------------------


class _PiiScanRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=500_000)


class _PiiEntity(BaseModel):
    entity_type: str
    start: int
    end: int


class _PiiScanResponse(BaseModel):
    entities: List[_PiiEntity]
    total_found: int


@router.post("/ingest/pii-scan", response_model=None, tags=["ingest"])
async def pii_scan(body: _PiiScanRequest):
    """Scan text for PII without storing anything.

    Runs the regex-based PII detector and returns a report of every entity
    found, including its type and character offsets.

    Raw PII values are intentionally omitted from the response to avoid
    echoing sensitive data back to the caller.  Use the ``start``/``end``
    offsets to locate the match in the original text.  No data is persisted
    by this endpoint.
    """
    findings = detect_pii(body.content)
    entities = [
        _PiiEntity(
            entity_type=f["type"],
            start=f["start"],
            end=f["end"],
        )
        for f in findings
    ]
    return ok(_PiiScanResponse(entities=entities, total_found=len(entities)).model_dump())


# ---------------------------------------------------------------------------
# Chunking preview endpoint
# ---------------------------------------------------------------------------


class _ChunkPreviewRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=1_000_000)
    strategy: Literal["simple", "semantic"] = "simple"
    chunk_size: int = Field(default=500, ge=50, le=10_000)
    overlap: int = Field(default=50, ge=0, le=2_000)


class _ChunkPreviewResponse(BaseModel):
    strategy: str
    chunk_count: int
    chunks: List[dict]


@router.post("/ingest/preview-chunks", response_model=None, tags=["ingest"])
async def preview_chunks(body: _ChunkPreviewRequest):
    """Preview how a document would be chunked without storing anything.

    Accepts raw text plus chunking parameters and returns the chunks that
    would be produced by the ingest pipeline.  Use this to compare
    strategies and tune chunk_size / overlap before committing an ingestion.

    For ``strategy="simple"``: ``chunk_size`` and ``overlap`` are character
    counts passed directly to the simple chunker.

    For ``strategy="semantic"``: ``chunk_size`` is treated as the
    retrieval token target (``chunk_size // 4`` characters ≈ tokens) and
    ``overlap`` as the overlap token budget.  The semantic chunker produces
    parent context chunks in addition to retrieval chunks.
    """
    chunks = chunk_document(
        text=body.content,
        strategy=body.strategy,
        chunk_size=body.chunk_size,
        chunk_overlap=body.overlap,
        # Map chunk_size to retrieval_token_size for semantic strategy.
        # Simple heuristic: 1 token ≈ 4 characters.
        retrieval_token_size=max(50, body.chunk_size // 4),
        context_token_size=max(200, body.chunk_size),
    )
    return ok(
        _ChunkPreviewResponse(
            strategy=body.strategy,
            chunk_count=len(chunks),
            chunks=chunks,
        ).model_dump()
    )
