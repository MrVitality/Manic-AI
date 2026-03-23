"""OpenAI-compatible API router.

Provides a wire-format-compatible drop-in for OpenAI clients:
  POST /v1/chat/completions  — non-streaming and streaming
  GET  /v1/models            — model list in OpenAI format

All inference is dispatched through the existing model_router service so
backend selection, fallback chains, and Langfuse tracing remain intact.
"""

import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.dependencies import get_http_client
from api.config import settings
from api.services import model_router

logger = logging.getLogger(__name__)

router = APIRouter(tags=["openai-compat"])


# ---------------------------------------------------------------------------
# Request / response schemas (OpenAI wire format)
# ---------------------------------------------------------------------------


class _Message(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[_Message]
    stream: bool = False
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1)


def _completion_id() -> str:
    return f"chatcmpl-{uuid.uuid4().hex}"


def _make_non_streaming_response(
    completion_id: str,
    model: str,
    content: str,
    prompt_tokens: int,
    completion_tokens: int,
    created: int,
) -> Dict[str, Any]:
    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


def _make_stream_chunk(
    completion_id: str,
    model: str,
    content: str,
    created: int,
    finish_reason: Optional[str] = None,
) -> str:
    """Return a single SSE data line (without trailing newlines)."""
    chunk: Dict[str, Any] = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {"content": content} if content else {},
                "finish_reason": finish_reason,
            }
        ],
    }
    return f"data: {json.dumps(chunk)}\n\n"


def _make_stream_role_chunk(
    completion_id: str,
    model: str,
    created: int,
) -> str:
    """First chunk in a stream carries the role field in delta."""
    chunk: Dict[str, Any] = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {"role": "assistant"},
                "finish_reason": None,
            }
        ],
    }
    return f"data: {json.dumps(chunk)}\n\n"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/chat/completions", response_model=None)
async def chat_completions(
    body: ChatCompletionRequest,
    client: httpx.AsyncClient = Depends(get_http_client),
):
    """OpenAI-compatible chat completions endpoint.

    Accepts the standard OpenAI request shape and routes inference through
    the existing model_router service.  Streaming is handled via SSE.
    """
    messages = [{"role": m.role, "content": m.content} for m in body.messages]
    completion_id = _completion_id()
    created = int(time.time())

    if body.stream:
        return StreamingResponse(
            _stream_response(
                completion_id,
                body.model,
                messages,
                client,
                temperature=body.temperature,
                max_tokens=body.max_tokens,
                created=created,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # Non-streaming path
    try:
        result = await model_router.chat_completion(
            messages=messages,
            model=body.model,
            stream=False,
            http_client=client,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
        )
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"Upstream inference error: {exc.response.text}",
        )
    except Exception as exc:
        logger.exception("[openai_compat] chat_completion failed")
        raise HTTPException(status_code=502, detail=f"Inference service error: {exc}")

    return _make_non_streaming_response(
        completion_id=completion_id,
        model=result.get("model", body.model),
        content=result.get("content", ""),
        prompt_tokens=result.get("prompt_tokens", 0),
        completion_tokens=result.get("completion_tokens", 0),
        created=created,
    )


async def _stream_response(
    completion_id: str,
    model: str,
    messages: List[Dict[str, str]],
    client: httpx.AsyncClient,
    *,
    temperature: float,
    max_tokens: Optional[int],
    created: int,
):
    """Async generator that yields OpenAI-format SSE lines."""
    # Role chunk first — mirrors OpenAI's stream behaviour
    yield _make_stream_role_chunk(completion_id, model, created)

    try:
        async for chunk in model_router.chat_completion_stream(
            messages=messages,
            model=model,
            http_client=client,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            chunk_type = chunk.get("type")
            if chunk_type == "content":
                yield _make_stream_chunk(
                    completion_id, model, chunk["content"], created
                )
            elif chunk_type == "done":
                # Emit stop chunk then [DONE] sentinel
                yield _make_stream_chunk(
                    completion_id, model, "", created, finish_reason="stop"
                )
    except Exception:
        logger.exception("[openai_compat] stream failed mid-flight")
        # Emit a final stop chunk so clients don't hang
        yield _make_stream_chunk(
            completion_id, model, "", created, finish_reason="stop"
        )

    yield "data: [DONE]\n\n"


@router.get("/models", response_model=None)
async def list_models(
    client: httpx.AsyncClient = Depends(get_http_client),
):
    """OpenAI-compatible model list.

    Fetches available Ollama models and returns them in the OpenAI
    ``GET /v1/models`` response format so third-party clients work
    without modification.
    """
    model_objects: List[Dict[str, Any]] = []

    try:
        resp = await client.get(f"{settings.OLLAMA_URL}/api/tags", timeout=10.0)
        resp.raise_for_status()
        for m in resp.json().get("models", []):
            name = m.get("name", "unknown")
            model_objects.append({
                "id": name,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "ollama",
            })
    except Exception:
        logger.warning("[openai_compat] Could not fetch Ollama models", exc_info=True)

    return {
        "object": "list",
        "data": model_objects,
    }
