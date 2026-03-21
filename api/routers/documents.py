"""Document CRUD routes."""

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
import httpx

from api.config import settings
from api.dependencies import get_document_repo, get_http_client, get_qdrant_repo
from api.middleware.rate_limit import limiter
from api.repositories.supabase_documents import SupabaseDocumentRepository
from api.repositories.qdrant_vector import QdrantVectorRepository
from api.schemas.envelope import ok

router = APIRouter()


@router.get("/documents", response_model=None, tags=["documents"])
async def list_documents(
    user_id: Optional[str] = None,
    collection_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    repo: SupabaseDocumentRepository = Depends(get_document_repo),
):
    results, total = await asyncio.gather(
        repo.list_documents(user_id, collection_id, status, limit, offset),
        repo.count_documents(user_id, collection_id, status),
    )
    return ok(results, meta={"total": total, "limit": limit, "offset": offset})


@router.delete("/documents/{document_id}", response_model=None, tags=["documents"])
@limiter.limit(f"{settings.RATE_LIMIT_MUTATIONS_PER_MINUTE}/minute")
async def delete_document(
    request: Request,
    document_id: str,
    repo: SupabaseDocumentRepository = Depends(get_document_repo),
    qdrant: QdrantVectorRepository = Depends(get_qdrant_repo),
):
    deleted = await repo.delete_document(document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    await qdrant.delete_by_document("documents", document_id)
    return ok({"status": "deleted", "document_id": document_id})
