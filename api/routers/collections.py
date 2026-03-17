"""Collection CRUD routes."""

from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import get_document_repo
from api.repositories.supabase_documents import SupabaseDocumentRepository
from api.schemas.envelope import ok

router = APIRouter()


@router.get("/collections", response_model=None, tags=["collections"])
async def list_collections(
    user_id: Optional[str] = None,
    repo: SupabaseDocumentRepository = Depends(get_document_repo),
):
    results = await repo.list_collections(user_id)
    return ok(results)


@router.post("/collections", response_model=None, tags=["collections"])
async def create_collection(
    name: str,
    description: Optional[str] = None,
    user_id: Optional[str] = None,
    is_public: bool = False,
    repo: SupabaseDocumentRepository = Depends(get_document_repo),
):
    collection_id = str(uuid4())
    await repo.create_collection(collection_id, user_id, name, description, is_public)
    return ok({"id": collection_id, "name": name, "status": "created"})


@router.delete("/collections/{collection_id}", response_model=None, tags=["collections"])
async def delete_collection(
    collection_id: str,
    repo: SupabaseDocumentRepository = Depends(get_document_repo),
):
    deleted = await repo.delete_collection(collection_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Collection not found")
    return ok({"status": "deleted", "collection_id": collection_id})
