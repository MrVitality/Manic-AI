"""Qdrant collection management and search routes."""

import logging
import re

from fastapi import APIRouter, Depends, HTTPException
import httpx

from api.config import settings
from api.dependencies import get_http_client, get_qdrant_repo
from api.repositories.qdrant_vector import QdrantVectorRepository
from api.schemas.envelope import ok
from api.services.embedding import generate_embedding

logger = logging.getLogger(__name__)
router = APIRouter()

_COLLECTION_NAME_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")


def _validate_collection_name(name: str) -> str:
    """Validate collection name to prevent path traversal."""
    if not _COLLECTION_NAME_RE.match(name):
        raise HTTPException(
            status_code=400,
            detail="Invalid collection name: use only letters, digits, hyphens, underscores (max 64 chars)",
        )
    return name


@router.get("/qdrant/collections", response_model=None, tags=["qdrant"])
async def list_qdrant_collections(
    qdrant: QdrantVectorRepository = Depends(get_qdrant_repo),
):
    try:
        return ok(await qdrant.list_collections())
    except httpx.HTTPError:
        logger.exception("Failed to list Qdrant collections")
        raise HTTPException(status_code=502, detail="Qdrant service unavailable")


@router.post("/qdrant/collections/{collection_name}", response_model=None, tags=["qdrant"])
async def create_qdrant_collection(
    collection_name: str,
    vector_size: int = settings.VECTOR_DIMENSION,
    qdrant: QdrantVectorRepository = Depends(get_qdrant_repo),
):
    collection_name = _validate_collection_name(collection_name)
    try:
        result = await qdrant.create_collection(collection_name, vector_size)
        return ok(result)
    except httpx.HTTPError:
        logger.exception("Failed to create Qdrant collection %s", collection_name)
        raise HTTPException(status_code=502, detail="Qdrant service unavailable")


@router.get("/qdrant/collections/{collection_name}", response_model=None, tags=["qdrant"])
async def get_qdrant_collection(
    collection_name: str,
    qdrant: QdrantVectorRepository = Depends(get_qdrant_repo),
):
    collection_name = _validate_collection_name(collection_name)
    try:
        return ok(await qdrant.get_collection(collection_name))
    except httpx.HTTPError:
        logger.exception("Failed to get Qdrant collection %s", collection_name)
        raise HTTPException(status_code=502, detail="Qdrant service unavailable")


@router.delete("/qdrant/collections/{collection_name}", response_model=None, tags=["qdrant"])
async def delete_qdrant_collection(
    collection_name: str,
    qdrant: QdrantVectorRepository = Depends(get_qdrant_repo),
):
    collection_name = _validate_collection_name(collection_name)
    try:
        result = await qdrant.delete_collection(collection_name)
        return ok(result)
    except httpx.HTTPError:
        logger.exception("Failed to delete Qdrant collection %s", collection_name)
        raise HTTPException(status_code=502, detail="Qdrant service unavailable")


@router.post(
    "/qdrant/search/{collection_name}",
    response_model=None,
    tags=["qdrant"],
    summary="Vector search in a Qdrant collection",
    description="Perform vector similarity search within a named Qdrant collection. "
    "Uses POST to support embedding generation from the query text.",
)
async def search_qdrant_collection(
    collection_name: str,
    query: str,
    top_k: int = 5,
    threshold: float = 0.7,
    client: httpx.AsyncClient = Depends(get_http_client),
    qdrant: QdrantVectorRepository = Depends(get_qdrant_repo),
):
    collection_name = _validate_collection_name(collection_name)
    try:
        query_embedding = await generate_embedding(query, client=client)
        results = await qdrant.search(query_embedding, collection_name, top_k, threshold)
        return ok({"results": results, "count": len(results)})
    except Exception:
        logger.exception("Qdrant search failed for collection %s", collection_name)
        raise HTTPException(status_code=500, detail="Search failed")
