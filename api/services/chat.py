"""Chat business logic -- Ollama completion + RAG context retrieval."""

import json
import logging
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional
from uuid import uuid4

import asyncpg
import httpx

from api.config import settings
from api.repositories.supabase_vector import SupabaseVectorRepository
from api.schemas.chat import ChatMessage, ChatRequest, ChatResponse
from api.services.embedding import generate_embedding

logger = logging.getLogger(__name__)


def build_rag_prompt(query: str, context_chunks: List[Dict]) -> str:
    """Wrap user query with retrieved context."""
    if not context_chunks:
        return query
    context = "\n\n---\n\n".join(
        [f"[Source {i+1}]: {chunk['content']}" for i, chunk in enumerate(context_chunks)]
    )
    return (
        "Use the following context to answer the question. "
        "If the context doesn't contain relevant information, say so and answer based on your general knowledge.\n\n"
        f"Context:\n{context}\n\nQuestion: {query}\n\nAnswer:"
    )


async def retrieve_rag_context(
    request: ChatRequest,
    last_message: str,
    db: Optional[asyncpg.Pool],
    client: httpx.AsyncClient,
) -> List[Dict]:
    """Retrieve RAG context chunks when requested."""
    if not request.use_rag or not last_message or not db:
        return []
    query_embedding = await generate_embedding(last_message, client=client)
    repo = SupabaseVectorRepository(db)
    return await repo.hybrid_search(
        last_message,
        query_embedding,
        top_k=settings.RAG_TOP_K,
        keyword_weight=settings.RAG_KEYWORD_WEIGHT,
        collection_id=request.collection_id,
        user_id=request.user_id,
    )


async def log_chat(
    db: Optional[asyncpg.Pool],
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: float,
    has_rag: bool,
) -> None:
    """Persist a chat_log row."""
    if not db:
        return
    try:
        async with db.acquire() as conn:
            await conn.execute(
                """INSERT INTO public.chat_log
                   (model, prompt_tokens, completion_tokens, total_tokens, latency_ms, has_rag)
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                model, prompt_tokens, completion_tokens,
                prompt_tokens + completion_tokens, latency_ms, has_rag,
            )
    except Exception:
        logger.warning("chat_log write failed", exc_info=True)


async def complete_chat(
    request: ChatRequest,
    client: httpx.AsyncClient,
    db: Optional[asyncpg.Pool],
    langfuse: Any = None,
) -> ChatResponse:
    """Non-streaming chat completion with optional RAG."""
    start_time = datetime.now(timezone.utc)
    model = request.model or settings.CHAT_MODEL
    user_messages = [m for m in request.messages if m.role == "user"]
    last_user_message = user_messages[-1].content if user_messages else ""
    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    trace = None
    if langfuse:
        trace = langfuse.trace(
            name="chat",
            input={"messages": messages, "model": model, "use_rag": request.use_rag},
            metadata={"temperature": request.temperature, "user_id": request.user_id},
        )

    sources = await retrieve_rag_context(request, last_user_message, db, client)
    if sources:
        messages[-1]["content"] = build_rag_prompt(last_user_message, sources)

    try:
        response = await client.post(
            f"{settings.OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": request.temperature},
            },
            timeout=120.0,
        )
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPError:
        logger.exception("Ollama chat request failed")
        if trace:
            trace.update(level="ERROR", status_message="Chat service unavailable")
        raise
    except Exception:
        logger.exception("Unexpected error during chat")
        if trace:
            trace.update(level="ERROR", status_message="Internal server error")
        raise

    response_text = data.get("message", {}).get("content", "")
    prompt_tokens = data.get("prompt_eval_count", 0)
    completion_tokens = data.get("eval_count", 0)
    latency_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

    await log_chat(db, model, prompt_tokens, completion_tokens, latency_ms, bool(sources))

    if trace:
        trace.update(
            output={"response": response_text, "sources_count": len(sources)},
            metadata={"latency_ms": round(latency_ms, 1)},
        )

    return ChatResponse(
        id=str(uuid4()),
        model=model,
        message=ChatMessage(role="assistant", content=response_text),
        sources=sources,
        usage={
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    )


async def stream_chat(
    request: ChatRequest,
    client: httpx.AsyncClient,
    db: Optional[asyncpg.Pool],
) -> AsyncGenerator[str, None]:
    """Streaming chat completion generator (SSE)."""
    model = request.model or settings.CHAT_MODEL
    user_messages = [m for m in request.messages if m.role == "user"]
    last_user_message = user_messages[-1].content if user_messages else ""
    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    sources = await retrieve_rag_context(request, last_user_message, db, client)
    if sources:
        messages[-1]["content"] = build_rag_prompt(last_user_message, sources)
        yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"

    try:
        start = datetime.now(timezone.utc)
        prompt_tokens = 0
        completion_tokens = 0
        async with client.stream(
            "POST",
            f"{settings.OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": True,
                "options": {"temperature": request.temperature},
            },
        ) as response:
            async for line in response.aiter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                content = chunk.get("message", {}).get("content", "")
                if content:
                    yield f"data: {json.dumps({'type': 'content', 'content': content})}\n\n"
                if chunk.get("done"):
                    prompt_tokens = chunk.get("prompt_eval_count", 0)
                    completion_tokens = chunk.get("eval_count", 0)
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    break
        latency_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
        await log_chat(db, model, prompt_tokens, completion_tokens, latency_ms, bool(sources))
    except Exception:
        logger.exception("Chat stream failed for model %s", model)
        yield f"data: {json.dumps({'type': 'error', 'error': 'Chat stream failed'})}\n\n"
