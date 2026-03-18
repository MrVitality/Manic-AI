"""Ingest and embed routes."""

import logging
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
import asyncpg
import httpx

from api.config import settings
from api.dependencies import get_db_optional, get_http_client
from api.schemas.envelope import ok
from api.schemas.ingest import (
    EmbedRequest,
    EmbedResponse,
    IngestAccepted,
    IngestRequest,
    IngestResponse,
    IngestStatusResponse,
)
from api.services.embedding import generate_embedding
from api.services.ingestion import (
    create_ingest_job,
    fetch_ingest_job,
    get_job_status,
    ingest_document,
    run_ingest_background,
    _update_job,
)
from api.services.multimodal_ingest import ingest_pdf_as_images

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/embed", response_model=None, tags=["ingest"])
async def create_embedding(
    request: EmbedRequest,
    client: httpx.AsyncClient = Depends(get_http_client),
):
    try:
        model = request.model or settings.EMBEDDING_MODEL
        embedding = await generate_embedding(request.text, model, client=client)
        return ok(EmbedResponse(embedding=embedding, model=model, dimensions=len(embedding)).model_dump())
    except httpx.HTTPError:
        logger.exception("Embedding generation failed via Ollama")
        raise HTTPException(status_code=502, detail="Embedding service unavailable")


@router.post("/ingest", response_model=None, tags=["ingest"])
async def ingest_document_endpoint(
    request: IngestRequest,
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
    # Route to multimodal pipeline if requested
    if request.multimodal and request.content_type == "application/pdf":
        import base64

        try:
            pdf_bytes = base64.b64decode(request.content)
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="For multimodal PDF ingestion, 'content' must be base64-encoded PDF bytes.",
            )

        document_id = str(uuid4())
        _update_job(document_id, status="pending", filename=request.filename)
        if db:
            await create_ingest_job(db, document_id, request.filename)

        async def _run_multimodal(doc_id: str):
            from api.services.ingestion import _update_job as _uj, _db_set_status
            _uj(doc_id, status="processing")
            if db:
                await _db_set_status(db, doc_id, "processing")
            try:
                result = await ingest_pdf_as_images(
                    pdf_bytes,
                    request.filename,
                    db,
                    client,
                    collection_id=request.collection_id,
                    user_id=request.user_id,
                    metadata=request.metadata,
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
    _update_job(document_id, status="pending", filename=request.filename)

    # Seed database row (best-effort)
    if db:
        await create_ingest_job(db, document_id, request.filename)

    # Schedule actual work in background
    background_tasks.add_task(run_ingest_background, document_id, request, db, client)

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
