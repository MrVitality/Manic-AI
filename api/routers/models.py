import logging
import re

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.config import OLLAMA_URL
from api.http_client import get_client

logger = logging.getLogger(__name__)

router = APIRouter()

_MODEL_NAME_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._:-]*$')


def _validate_model_name(name: str) -> str:
    """Validate model name to prevent path traversal and injection."""
    if not name or len(name) > 200 or not _MODEL_NAME_RE.match(name):
        raise HTTPException(
            status_code=400,
            detail="Invalid model name. Must match [a-zA-Z0-9][a-zA-Z0-9._:-]* and be at most 200 characters.",
        )
    return name


class PullModelRequest(BaseModel):
    name: str = Field(..., max_length=200)


# =============================================================================
# GET /models
# =============================================================================


@router.get("/models")
async def list_models(client: httpx.AsyncClient = Depends(get_client)):
    """List available Ollama models."""
    try:
        resp = await client.get(f"{OLLAMA_URL}/api/tags")
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as e:
        logger.exception("Failed to list Ollama models")
        raise HTTPException(status_code=502, detail="Failed to list models")


# =============================================================================
# GET /api/tags  (compat alias)
# =============================================================================


@router.get("/api/tags")
async def list_models_compat(client: httpx.AsyncClient = Depends(get_client)):
    """Compatibility alias for /models."""
    return await list_models(client)


# =============================================================================
# POST /models/pull
# =============================================================================


@router.post("/models/pull")
async def pull_model(
    request: PullModelRequest,
    client: httpx.AsyncClient = Depends(get_client),
):
    """Stream a model pull from Ollama."""
    _validate_model_name(request.name)

    async def stream_pull():
        try:
            async with client.stream(
                "POST",
                f"{OLLAMA_URL}/api/pull",
                json={"name": request.name, "stream": True},
            ) as response:
                async for line in response.aiter_lines():
                    if line:
                        yield f"data: {line}\n\n"
        except Exception:
            logger.exception("Failed to stream model pull for %s", request.name)
            yield f'data: {{"error": "Model pull failed"}}\n\n'

    return StreamingResponse(stream_pull(), media_type="text/event-stream")


# =============================================================================
# DELETE /models/{name}
# =============================================================================


@router.delete("/models/{name}")
async def delete_model(
    name: str,
    client: httpx.AsyncClient = Depends(get_client),
):
    """Delete an Ollama model by name."""
    _validate_model_name(name)
    try:
        resp = await client.delete(f"{OLLAMA_URL}/api/delete", json={"name": name})
        if resp.status_code == 200:
            return {"status": "deleted", "model": name}
        raise HTTPException(status_code=resp.status_code, detail="Failed to delete model")
    except httpx.HTTPError as e:
        logger.exception("Failed to delete Ollama model %s", name)
        raise HTTPException(status_code=502, detail="Failed to delete model")
