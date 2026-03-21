"""Collection CRUD routes."""

import asyncio
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from api.config import settings
from api.dependencies import get_document_repo
from api.middleware.rate_limit import limiter
from api.repositories.supabase_documents import SupabaseDocumentRepository
from api.schemas.envelope import ok

router = APIRouter()


class CreateCollectionRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    user_id: Optional[str] = None
    is_public: bool = False


@router.get("/collections", response_model=None, tags=["collections"])
async def list_collections(
    user_id: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    repo: SupabaseDocumentRepository = Depends(get_document_repo),
):
    results, total = await asyncio.gather(
        repo.list_collections(user_id, limit, offset),
        repo.count_collections(user_id),
    )
    return ok(results, meta={"total": total, "limit": limit, "offset": offset})


@router.post("/collections", response_model=None, tags=["collections"])
@limiter.limit(f"{settings.RATE_LIMIT_MUTATIONS_PER_MINUTE}/minute")
async def create_collection(
    request: Request,
    body: CreateCollectionRequest,
    repo: SupabaseDocumentRepository = Depends(get_document_repo),
):
    collection_id = str(uuid4())
    await repo.create_collection(collection_id, body.user_id, body.name, body.description, body.is_public)
    return ok({"id": collection_id, "name": body.name, "status": "created"})


@router.delete("/collections/{collection_id}", response_model=None, tags=["collections"])
@limiter.limit(f"{settings.RATE_LIMIT_MUTATIONS_PER_MINUTE}/minute")
async def delete_collection(
    request: Request,
    collection_id: str,
    repo: SupabaseDocumentRepository = Depends(get_document_repo),
):
    deleted = await repo.delete_collection(collection_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Collection not found")
    return ok({"status": "deleted", "collection_id": collection_id})
