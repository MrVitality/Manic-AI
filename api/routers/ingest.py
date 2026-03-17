"""Ingest and embed routes."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
import asyncpg
import httpx

from api.config import settings
from api.dependencies import get_db_optional, get_http_client
from api.schemas.envelope import ok
from api.schemas.ingest import EmbedRequest, EmbedResponse, IngestRequest, IngestResponse
from api.services.embedding import generate_embedding
from api.services.ingestion import ingest_document

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
    db: Optional[asyncpg.Pool] = Depends(get_db_optional),
    client: httpx.AsyncClient = Depends(get_http_client),
):
    try:
        result = await ingest_document(request, db, client)
        return ok(result.model_dump())
    except Exception:
        logger.exception("Document ingestion failed for %s", request.filename)
        raise HTTPException(status_code=500, detail="Internal server error")
