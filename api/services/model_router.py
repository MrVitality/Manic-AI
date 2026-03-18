"""Model routing service -- dispatches inference to Ollama or vLLM.

Both backends use an OpenAI-compatible API format for chat completions.
The active backend is determined by ``settings.INFERENCE_BACKEND``.
"""

import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from api.config import settings

logger = logging.getLogger(__name__)


async def chat_completion(
    messages: List[Dict[str, str]],
    model: str,
    stream: bool,
    http_client: httpx.AsyncClient,
    *,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    """Non-streaming chat completion routed to the configured backend.

    Returns a normalised dict with keys:
        - ``content``: the assistant reply text
        - ``prompt_tokens``: token count for the prompt
        - ``completion_tokens``: token count for the completion
        - ``model``: the model that was used
        - ``raw``: the full upstream response dict
    """
    backend = settings.INFERENCE_BACKEND

    if backend == "openai" and settings.OPENAI_API_KEY:
        return await _openai_chat(messages, model, http_client, temperature=temperature, max_tokens=max_tokens)
    if backend == "vllm" and settings.VLLM_URL:
        return await _vllm_chat(messages, model, http_client, temperature=temperature, max_tokens=max_tokens)
    # Default to Ollama
    return await _ollama_chat(messages, model, http_client, temperature=temperature)


async def chat_completion_stream(
    messages: List[Dict[str, str]],
    model: str,
    http_client: httpx.AsyncClient,
    *,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Streaming chat completion routed to the configured backend.

    Yields normalised dicts:
        - ``{"type": "content", "content": "..."}``
        - ``{"type": "done", "prompt_tokens": ..., "completion_tokens": ...}``
    """
    backend = settings.INFERENCE_BACKEND

    if backend == "openai" and settings.OPENAI_API_KEY:
        async for chunk in _openai_chat_stream(messages, model, http_client, temperature=temperature, max_tokens=max_tokens):
            yield chunk
    elif backend == "vllm" and settings.VLLM_URL:
        async for chunk in _vllm_chat_stream(messages, model, http_client, temperature=temperature, max_tokens=max_tokens):
            yield chunk
    else:
        async for chunk in _ollama_chat_stream(messages, model, http_client, temperature=temperature):
            yield chunk


# ---------------------------------------------------------------------------
# Ollama backend
# ---------------------------------------------------------------------------


async def _ollama_chat(
    messages: List[Dict[str, str]],
    model: str,
    client: httpx.AsyncClient,
    *,
    temperature: float = 0.7,
) -> Dict[str, Any]:
    """Ollama /api/chat (non-streaming)."""
    response = await client.post(
        f"{settings.OLLAMA_URL}/api/chat",
        json={
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        },
        timeout=120.0,
    )
    response.raise_for_status()
    data = response.json()

    return {
        "content": data.get("message", {}).get("content", ""),
        "prompt_tokens": data.get("prompt_eval_count", 0),
        "completion_tokens": data.get("eval_count", 0),
        "model": model,
        "raw": data,
    }


async def _ollama_chat_stream(
    messages: List[Dict[str, str]],
    model: str,
    client: httpx.AsyncClient,
    *,
    temperature: float = 0.7,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Ollama /api/chat (streaming)."""
    async with client.stream(
        "POST",
        f"{settings.OLLAMA_URL}/api/chat",
        json={
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": temperature},
        },
    ) as response:
        async for line in response.aiter_lines():
            if not line:
                continue
            chunk = json.loads(line)
            content = chunk.get("message", {}).get("content", "")
            if content:
                yield {"type": "content", "content": content}
            if chunk.get("done"):
                yield {
                    "type": "done",
                    "prompt_tokens": chunk.get("prompt_eval_count", 0),
                    "completion_tokens": chunk.get("eval_count", 0),
                }
                break


# ---------------------------------------------------------------------------
# vLLM backend (OpenAI-compatible API)
# ---------------------------------------------------------------------------


async def _vllm_chat(
    messages: List[Dict[str, str]],
    model: str,
    client: httpx.AsyncClient,
    *,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    """vLLM /v1/chat/completions (non-streaming)."""
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens

    response = await client.post(
        f"{settings.VLLM_URL}/v1/chat/completions",
        json=payload,
        timeout=120.0,
    )
    response.raise_for_status()
    data = response.json()

    choice = data.get("choices", [{}])[0]
    usage = data.get("usage", {})

    return {
        "content": choice.get("message", {}).get("content", ""),
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "model": data.get("model", model),
        "raw": data,
    }


async def _vllm_chat_stream(
    messages: List[Dict[str, str]],
    model: str,
    client: httpx.AsyncClient,
    *,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """vLLM /v1/chat/completions (streaming, SSE)."""
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens

    async with client.stream(
        "POST",
        f"{settings.VLLM_URL}/v1/chat/completions",
        json=payload,
    ) as response:
        prompt_tokens = 0
        completion_tokens = 0
        async for line in response.aiter_lines():
            if not line or not line.startswith("data: "):
                continue
            data_str = line[len("data: "):]
            if data_str.strip() == "[DONE]":
                yield {
                    "type": "done",
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                }
                break
            try:
                chunk = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            delta = chunk.get("choices", [{}])[0].get("delta", {})
            content = delta.get("content", "")
            if content:
                yield {"type": "content", "content": content}

            # vLLM may include usage in the final chunk
            usage = chunk.get("usage")
            if usage:
                prompt_tokens = usage.get("prompt_tokens", prompt_tokens)
                completion_tokens = usage.get("completion_tokens", completion_tokens)


# ---------------------------------------------------------------------------
# OpenAI backend (OpenAI-compatible API with API key auth)
# ---------------------------------------------------------------------------


async def _openai_chat(
    messages: List[Dict[str, str]],
    model: str,
    client: httpx.AsyncClient,
    *,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    """OpenAI /v1/chat/completions (non-streaming)."""
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens

    response = await client.post(
        f"{settings.OPENAI_BASE_URL}/chat/completions",
        json=payload,
        headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
        timeout=120.0,
    )
    response.raise_for_status()
    data = response.json()

    choice = data.get("choices", [{}])[0]
    usage = data.get("usage", {})

    return {
        "content": choice.get("message", {}).get("content", ""),
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "model": data.get("model", model),
        "raw": data,
    }


async def _openai_chat_stream(
    messages: List[Dict[str, str]],
    model: str,
    client: httpx.AsyncClient,
    *,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """OpenAI /v1/chat/completions (streaming, SSE)."""
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens

    async with client.stream(
        "POST",
        f"{settings.OPENAI_BASE_URL}/chat/completions",
        json=payload,
        headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
    ) as response:
        prompt_tokens = 0
        completion_tokens = 0
        async for line in response.aiter_lines():
            if not line or not line.startswith("data: "):
                continue
            data_str = line[len("data: "):]
            if data_str.strip() == "[DONE]":
                yield {
                    "type": "done",
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                }
                break
            try:
                chunk = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            delta = chunk.get("choices", [{}])[0].get("delta", {})
            content = delta.get("content", "")
            if content:
                yield {"type": "content", "content": content}

            # OpenAI includes usage in the final chunk (stream_options)
            usage = chunk.get("usage")
            if usage:
                prompt_tokens = usage.get("prompt_tokens", prompt_tokens)
                completion_tokens = usage.get("completion_tokens", completion_tokens)
