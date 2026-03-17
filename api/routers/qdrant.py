"""Qdrant collection management and search routes."""

from fastapi import APIRouter, Depends, HTTPException
import httpx

from api.dependencies import get_http_client, get_qdrant_repo
from api.repositories.qdrant_vector import QdrantVectorRepository
from api.schemas.envelope import ok
from api.services.embedding import generate_embedding

router = APIRouter()


@router.get("/qdrant/collections", response_model=None, tags=["qdrant"])
async def list_qdrant_collections(
    qdrant: QdrantVectorRepository = Depends(get_qdrant_repo),
):
    try:
        return ok(await qdrant.list_collections())
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Qdrant error: {e}")


@router.post("/qdrant/collections/{collection_name}", response_model=None, tags=["qdrant"])
async def create_qdrant_collection(
    collection_name: str,
    vector_size: int = 768,
    qdrant: QdrantVectorRepository = Depends(get_qdrant_repo),
):
    try:
        result = await qdrant.create_collection(collection_name, vector_size)
        return ok(result)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Qdrant error: {e}")


@router.get("/qdrant/collections/{collection_name}", response_model=None, tags=["qdrant"])
async def get_qdrant_collection(
    collection_name: str,
    qdrant: QdrantVectorRepository = Depends(get_qdrant_repo),
):
    try:
        return ok(await qdrant.get_collection(collection_name))
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Qdrant error: {e}")


@router.delete("/qdrant/collections/{collection_name}", response_model=None, tags=["qdrant"])
async def delete_qdrant_collection(
    collection_name: str,
    qdrant: QdrantVectorRepository = Depends(get_qdrant_repo),
):
    try:
        result = await qdrant.delete_collection(collection_name)
        return ok(result)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Qdrant error: {e}")


@router.post("/qdrant/search/{collection_name}", response_model=None, tags=["qdrant"])
async def search_qdrant_collection(
    collection_name: str,
    query: str,
    top_k: int = 5,
    threshold: float = 0.7,
    client: httpx.AsyncClient = Depends(get_http_client),
    qdrant: QdrantVectorRepository = Depends(get_qdrant_repo),
):
    try:
        query_embedding = await generate_embedding(query, client=client)
        results = await qdrant.search(query_embedding, collection_name, top_k, threshold)
        return ok({"results": results, "count": len(results)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
