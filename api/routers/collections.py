"""Collection CRUD routes."""

from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.dependencies import get_document_repo
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
    repo: SupabaseDocumentRepository = Depends(get_document_repo),
):
    results = await repo.list_collections(user_id)
    return ok(results)


@router.post("/collections", response_model=None, tags=["collections"])
async def create_collection(
    body: CreateCollectionRequest,
    repo: SupabaseDocumentRepository = Depends(get_document_repo),
):
    collection_id = str(uuid4())
    await repo.create_collection(collection_id, body.user_id, body.name, body.description, body.is_public)
    return ok({"id": collection_id, "name": body.name, "status": "created"})


@router.delete("/collections/{collection_id}", response_model=None, tags=["collections"])
async def delete_collection(
    collection_id: str,
    repo: SupabaseDocumentRepository = Depends(get_document_repo),
):
    deleted = await repo.delete_collection(collection_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Collection not found")
    return ok({"status": "deleted", "collection_id": collection_id})
