"""Model management routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
import httpx

from api.dependencies import get_http_client
from api.schemas.envelope import ok
from api.schemas.models import PullModelRequest
from api.services.ollama import delete_model, list_models, stream_pull_model

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/models", response_model=None, tags=["models"])
async def list_models_endpoint(
    client: httpx.AsyncClient = Depends(get_http_client),
):
    try:
        data = await list_models(client)
        return ok(data)
    except httpx.HTTPError:
        logger.exception("Failed to list Ollama models")
        raise HTTPException(status_code=502, detail="Failed to list models")


@router.get("/api/tags", response_model=None, tags=["models"])
async def list_models_compat(
    client: httpx.AsyncClient = Depends(get_http_client),
):
    """Compatibility alias for /models."""
    return await list_models_endpoint(client)


@router.post("/models/pull", tags=["models"])
async def pull_model(
    request: PullModelRequest,
    client: httpx.AsyncClient = Depends(get_http_client),
):
    return StreamingResponse(
        stream_pull_model(request.name, client),
        media_type="text/event-stream",
    )


@router.delete("/models/{name}", response_model=None, tags=["models"])
async def delete_model_endpoint(
    name: str,
    client: httpx.AsyncClient = Depends(get_http_client),
):
    try:
        result = await delete_model(name, client)
        return ok(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except httpx.HTTPError:
        logger.exception("Failed to delete Ollama model %s", name)
        raise HTTPException(status_code=502, detail="Failed to delete model")
