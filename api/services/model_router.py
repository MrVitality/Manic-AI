"""Model routing service -- dispatches inference to Ollama, vLLM, OpenAI, or Anthropic.

The active backend is determined by ``settings.INFERENCE_BACKEND``.
If ``settings.MODEL_FALLBACK_CHAIN`` is set (e.g. "ollama,anthropic,openai"),
connection/timeout errors on the primary backend cause the router to try each
backend in chain order.  4xx HTTP errors are never retried.
"""

import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from api.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION = "2023-06-01"

# Errors that warrant a fallback attempt (infrastructure-level failures only).
_RETRYABLE = (httpx.ConnectError, httpx.TimeoutException)


def _fallback_chain() -> List[str]:
    """Return the ordered list of fallback backends from config.

    The primary backend is NOT included; callers prepend it themselves.
    """
    raw = settings.MODEL_FALLBACK_CHAIN.strip()
    if not raw:
        return []
    return [b.strip() for b in raw.split(",") if b.strip()]


def _build_anthropic_payload(
    messages: List[Dict[str, str]],
    model: str,
    *,
    temperature: float,
    max_tokens: Optional[int],
    stream: bool,
) -> tuple[Dict[str, Any], Dict[str, str]]:
    """Convert the OpenAI-style message list to Anthropic's format.

    Anthropic separates the system prompt from the conversation messages and
    does not accept a ``"system"`` role inside the ``messages`` array.

    Returns ``(payload, headers)``.
    """
    system_parts: List[str] = []
    user_messages: List[Dict[str, str]] = []

    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "system":
            system_parts.append(content)
        else:
            # Anthropic accepts "user" and "assistant" roles directly.
            user_messages.append({"role": role, "content": content})

    payload: Dict[str, Any] = {
        "model": model,
        "messages": user_messages,
        "temperature": temperature,
        "stream": stream,
        # Anthropic requires max_tokens; fall back to a safe default.
        "max_tokens": max_tokens if max_tokens is not None else 4096,
    }
    if system_parts:
        payload["system"] = "\n\n".join(system_parts)

    headers = {
        "x-api-key": settings.ANTHROPIC_API_KEY,
        "anthropic-version": _ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    return payload, headers


# ---------------------------------------------------------------------------
# Public dispatch functions
# ---------------------------------------------------------------------------


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
    primary = settings.INFERENCE_BACKEND
    chain = [primary] + _fallback_chain()

    last_error: Exception = RuntimeError("No backends configured")

    for backend in chain:
        try:
            return await _dispatch_chat(
                backend, messages, model, http_client,
                temperature=temperature, max_tokens=max_tokens,
            )
        except _RETRYABLE as exc:
            last_error = exc
            logger.warning(
                "[model_router] backend=%s connection/timeout error (%s); "
                "trying next fallback",
                backend, exc,
            )
        # Any non-retryable error (4xx, 5xx, parse errors) propagates immediately.

    raise last_error


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

    Fallback on streaming is attempted only before the first chunk is yielded.
    Once streaming has begun the connection is committed to that backend.
    """
    primary = settings.INFERENCE_BACKEND
    chain = [primary] + _fallback_chain()

    last_error: Exception = RuntimeError("No backends configured")

    for backend in chain:
        try:
            # Collect from the async generator; yield as we go.
            # We must attempt the generator before yielding to catch connect
            # errors before the first byte is sent to the caller.
            async for chunk in _dispatch_chat_stream(
                backend, messages, model, http_client,
                temperature=temperature, max_tokens=max_tokens,
            ):
                yield chunk
            return  # stream completed successfully
        except _RETRYABLE as exc:
            last_error = exc
            logger.warning(
                "[model_router] backend=%s stream connection/timeout error (%s); "
                "trying next fallback",
                backend, exc,
            )

    raise last_error


# ---------------------------------------------------------------------------
# Internal per-backend dispatch
# ---------------------------------------------------------------------------


async def _dispatch_chat(
    backend: str,
    messages: List[Dict[str, str]],
    model: str,
    client: httpx.AsyncClient,
    *,
    temperature: float,
    max_tokens: Optional[int],
) -> Dict[str, Any]:
    """Route a non-streaming request to the named backend."""
    if backend == "openai" and settings.OPENAI_API_KEY:
        return await _openai_chat(messages, model, client, temperature=temperature, max_tokens=max_tokens)
    if backend == "vllm" and settings.VLLM_URL:
        return await _vllm_chat(messages, model, client, temperature=temperature, max_tokens=max_tokens)
    if backend == "anthropic" and settings.ANTHROPIC_API_KEY:
        return await _anthropic_chat(messages, model, client, temperature=temperature, max_tokens=max_tokens)
    # Default / fallback-to-ollama
    return await _ollama_chat(messages, model, client, temperature=temperature)


async def _dispatch_chat_stream(
    backend: str,
    messages: List[Dict[str, str]],
    model: str,
    client: httpx.AsyncClient,
    *,
    temperature: float,
    max_tokens: Optional[int],
) -> AsyncGenerator[Dict[str, Any], None]:
    """Route a streaming request to the named backend."""
    if backend == "openai" and settings.OPENAI_API_KEY:
        async for chunk in _openai_chat_stream(messages, model, client, temperature=temperature, max_tokens=max_tokens):
            yield chunk
    elif backend == "vllm" and settings.VLLM_URL:
        async for chunk in _vllm_chat_stream(messages, model, client, temperature=temperature, max_tokens=max_tokens):
            yield chunk
    elif backend == "anthropic" and settings.ANTHROPIC_API_KEY:
        async for chunk in _anthropic_chat_stream(messages, model, client, temperature=temperature, max_tokens=max_tokens):
            yield chunk
    else:
        async for chunk in _ollama_chat_stream(messages, model, client, temperature=temperature):
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


# ---------------------------------------------------------------------------
# Anthropic backend
# ---------------------------------------------------------------------------


async def _anthropic_chat(
    messages: List[Dict[str, str]],
    model: str,
    client: httpx.AsyncClient,
    *,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    """Anthropic /v1/messages (non-streaming).

    Converts the OpenAI-style message list to Anthropic's format:
    - ``system`` role messages are extracted and sent in the top-level
      ``system`` field; they are not permitted inside ``messages``.
    - ``user`` and ``assistant`` roles are passed through unchanged.
    """
    payload, headers = _build_anthropic_payload(
        messages, model, temperature=temperature, max_tokens=max_tokens, stream=False,
    )

    response = await client.post(
        _ANTHROPIC_API_URL,
        json=payload,
        headers=headers,
        timeout=120.0,
    )
    response.raise_for_status()
    data = response.json()

    # Anthropic returns content as a list of blocks; grab the first text block.
    content_blocks = data.get("content", [])
    text = next(
        (block.get("text", "") for block in content_blocks if block.get("type") == "text"),
        "",
    )

    usage = data.get("usage", {})
    return {
        "content": text,
        "prompt_tokens": usage.get("input_tokens", 0),
        "completion_tokens": usage.get("output_tokens", 0),
        "model": data.get("model", model),
        "raw": data,
    }


async def _anthropic_chat_stream(
    messages: List[Dict[str, str]],
    model: str,
    client: httpx.AsyncClient,
    *,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Anthropic /v1/messages (streaming, SSE).

    Anthropic's SSE stream emits typed events.  We handle:
    - ``content_block_delta`` with ``delta.type == "text_delta"`` for text chunks
    - ``message_delta`` for the final usage counters
    - ``message_stop`` as the end-of-stream sentinel
    """
    payload, headers = _build_anthropic_payload(
        messages, model, temperature=temperature, max_tokens=max_tokens, stream=True,
    )

    prompt_tokens = 0
    completion_tokens = 0

    async with client.stream(
        "POST",
        _ANTHROPIC_API_URL,
        json=payload,
        headers=headers,
    ) as response:
        response.raise_for_status()
        async for line in response.aiter_lines():
            if not line or not line.startswith("data: "):
                continue
            data_str = line[len("data: "):]
            try:
                event = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            event_type = event.get("type", "")

            if event_type == "message_start":
                # Initial usage info (input tokens) is in message_start.
                usage = event.get("message", {}).get("usage", {})
                prompt_tokens = usage.get("input_tokens", prompt_tokens)

            elif event_type == "content_block_delta":
                delta = event.get("delta", {})
                if delta.get("type") == "text_delta":
                    text = delta.get("text", "")
                    if text:
                        yield {"type": "content", "content": text}

            elif event_type == "message_delta":
                # Final usage update (output tokens).
                usage = event.get("usage", {})
                completion_tokens = usage.get("output_tokens", completion_tokens)

            elif event_type == "message_stop":
                yield {
                    "type": "done",
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                }
                break
