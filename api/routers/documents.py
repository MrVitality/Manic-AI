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
    # Fetch the document's owner before deleting so we can enforce IDOR
    # protection.  We return 404 in all non-owned cases to avoid enumeration.
    caller_id: Optional[str] = request.headers.get("X-User-Id") or None
    owner_id = await repo.get_document_user_id(document_id)

    if owner_id is None and caller_id is not None:
        # Document does not exist — return 404 regardless of caller identity.
        raise HTTPException(status_code=404, detail="Document not found")

    if caller_id is not None and owner_id is not None and owner_id != caller_id:
        # Caller exists, document exists, but caller is not the owner.
        # Return 404 (not 403) to prevent enumeration of other users' docs.
        raise HTTPException(status_code=404, detail="Document not found")

    deleted = await repo.delete_document(document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    await qdrant.delete_by_document("documents", document_id)
    return ok({"status": "deleted", "document_id": document_id})
