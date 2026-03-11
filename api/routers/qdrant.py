from typing import List, Dict, Any, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from api.config import QDRANT_URL
from api.http_client import get_client
from api.services.embedding import generate_embedding
from api.services.rag import qdrant_search

router = APIRouter()


@router.get("/qdrant/collections")
async def list_qdrant_collections(client: httpx.AsyncClient = Depends(get_client)):
    try:
        response = await client.get(f"{QDRANT_URL}/collections")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Qdrant error: {str(e)}")


@router.post("/qdrant/collections/{collection_name}")
async def create_qdrant_collection(
    collection_name: str,
    vector_size: int = 768,
    client: httpx.AsyncClient = Depends(get_client),
):
    try:
        response = await client.put(
            f"{QDRANT_URL}/collections/{collection_name}",
            json={"vectors": {"size": vector_size, "distance": "Cosine"}},
        )
        if response.status_code in [200, 201]:
            return {"status": "created", "collection": collection_name}
        elif response.status_code == 409:
            return {"status": "exists", "collection": collection_name}
        raise HTTPException(status_code=response.status_code, detail=response.text)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Qdrant error: {str(e)}")


@router.get("/qdrant/collections/{collection_name}")
async def get_qdrant_collection(
    collection_name: str,
    client: httpx.AsyncClient = Depends(get_client),
):
    try:
        response = await client.get(f"{QDRANT_URL}/collections/{collection_name}")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Qdrant error: {str(e)}")


@router.delete("/qdrant/collections/{collection_name}")
async def delete_qdrant_collection(
    collection_name: str,
    client: httpx.AsyncClient = Depends(get_client),
):
    try:
        response = await client.delete(f"{QDRANT_URL}/collections/{collection_name}")
        if response.status_code in [200, 204]:
            return {"status": "deleted", "collection": collection_name}
        raise HTTPException(status_code=response.status_code, detail=response.text)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Qdrant error: {str(e)}")


@router.post("/qdrant/search/{collection_name}")
async def search_qdrant_collection(
    collection_name: str,
    query: str,
    top_k: int = 5,
    threshold: float = 0.7,
    client: httpx.AsyncClient = Depends(get_client),
):
    try:
        query_embedding = await generate_embedding(query, client=client)
        results = await qdrant_search(
            query_embedding,
            client,
            collection_name=collection_name,
            top_k=top_k,
            threshold=threshold,
        )
        return {"results": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
