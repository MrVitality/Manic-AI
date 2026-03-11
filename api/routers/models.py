import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.config import OLLAMA_URL
from api.http_client import get_client

router = APIRouter()


class PullModelRequest(BaseModel):
    name: str


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
        raise HTTPException(status_code=502, detail=f"Ollama error: {str(e)}")


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
        except Exception as e:
            yield f'data: {{"error": "{str(e)}"}}\n\n'

    return StreamingResponse(stream_pull(), media_type="text/event-stream")


# =============================================================================
# DELETE /models/{name:path}
# =============================================================================


@router.delete("/models/{name:path}")
async def delete_model(
    name: str,
    client: httpx.AsyncClient = Depends(get_client),
):
    """Delete an Ollama model by name."""
    try:
        resp = await client.delete(f"{OLLAMA_URL}/api/delete", json={"name": name})
        if resp.status_code == 200:
            return {"status": "deleted", "model": name}
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Ollama error: {str(e)}")
