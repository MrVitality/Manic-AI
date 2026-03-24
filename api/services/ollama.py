"""Ollama model management service."""

import logging
import re
from typing import Any, AsyncGenerator, Dict

import httpx

from api.config import settings

logger = logging.getLogger(__name__)

_MODEL_NAME_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._:-]*$')


def validate_model_name(name: str) -> str:
    """Validate model name to prevent path traversal and injection."""
    if not name or len(name) > 200 or not _MODEL_NAME_RE.match(name):
        raise ValueError(
            "Invalid model name. Must match [a-zA-Z0-9][a-zA-Z0-9._:-]* and be at most 200 characters."
        )
    return name


async def list_models(client: httpx.AsyncClient) -> Any:
    """Fetch installed models from Ollama."""
    resp = await client.get(f"{settings.OLLAMA_URL}/api/tags")
    resp.raise_for_status()
    return resp.json()


async def delete_model(name: str, client: httpx.AsyncClient) -> Dict[str, str]:
    """Delete an Ollama model by name."""
    validate_model_name(name)
    resp = await client.delete(f"{settings.OLLAMA_URL}/api/delete", json={"name": name})
    if resp.status_code == 200:
        return {"status": "deleted", "model": name}
    raise httpx.HTTPStatusError(
        f"Failed to delete model (status {resp.status_code})",
        request=resp.request,
        response=resp,
    )


async def stream_pull_model(
    name: str, client: httpx.AsyncClient,
) -> AsyncGenerator[str, None]:
    """Stream a model pull from Ollama as SSE lines."""
    validate_model_name(name)
    try:
        async with client.stream(
            "POST",
            f"{settings.OLLAMA_URL}/api/pull",
            json={"name": name, "stream": True},
        ) as response:
            async for line in response.aiter_lines():
                if line:
                    yield f"data: {line}\n\n"
    except Exception:
        logger.exception("Failed to stream model pull for %s", name)
        yield 'data: {"error": "Model pull failed"}\n\n'
