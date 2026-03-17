import json
import logging
from datetime import datetime, timezone
from uuid import uuid4
from typing import List, Dict, Optional

from fastapi import APIRouter, Depends
from fastapi.exceptions import HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import httpx
import asyncpg

from api.config import OLLAMA_URL, CHAT_MODEL, RAG_TOP_K, RAG_KEYWORD_WEIGHT
from api.database import get_db_optional
from api.http_client import get_client
from api.services.embedding import generate_embedding
from api.services.rag import hybrid_search, build_rag_prompt
from api.services.langfuse import get_langfuse

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(system|user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = None
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 2048
    stream: Optional[bool] = False
    use_rag: Optional[bool] = False
    collection_id: Optional[str] = None
    user_id: Optional[str] = None


class ChatResponse(BaseModel):
    id: str
    model: str
    message: ChatMessage
    sources: List[Dict] = []
    usage: Dict = {}


async def _retrieve_rag_context(
    request: ChatRequest,
    last_message: str,
    db,
    client: httpx.AsyncClient,
) -> List[Dict]:
    if not request.use_rag or not last_message or not db:
        return []
    query_embedding = await generate_embedding(last_message, client=client)
    return await hybrid_search(
        last_message, query_embedding, db,
        RAG_TOP_K, RAG_KEYWORD_WEIGHT,
        request.collection_id, request.user_id,
    )


async def _log_chat(
    db,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: float,
    has_rag: bool,
):
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


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    client: httpx.AsyncClient = Depends(get_client),
):
    db = get_db_optional()
    start_time = datetime.now(timezone.utc)
    model = request.model or CHAT_MODEL
    user_messages = [m for m in request.messages if m.role == "user"]
    last_user_message = user_messages[-1].content if user_messages else ""
    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    langfuse = get_langfuse()
    trace = None
    if langfuse:
        trace = langfuse.trace(
            name="chat",
            input={"messages": messages, "model": model, "use_rag": request.use_rag},
            metadata={"temperature": request.temperature, "user_id": request.user_id},
        )

    sources = await _retrieve_rag_context(request, last_user_message, db, client)
    if sources:
        messages[-1]["content"] = build_rag_prompt(last_user_message, sources)

    try:
        response = await client.post(
            f"{OLLAMA_URL}/api/chat",
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
        raise HTTPException(status_code=502, detail="Chat service unavailable")
    except Exception:
        logger.exception("Unexpected error during chat")
        if trace:
            trace.update(level="ERROR", status_message="Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")

    response_text = data.get("message", {}).get("content", "")
    prompt_tokens = data.get("prompt_eval_count", 0)
    completion_tokens = data.get("eval_count", 0)
    latency_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

    await _log_chat(db, model, prompt_tokens, completion_tokens, latency_ms, bool(sources))

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


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    client: httpx.AsyncClient = Depends(get_client),
):
    db = get_db_optional()
    model = request.model or CHAT_MODEL

    async def generate():
        user_messages = [m for m in request.messages if m.role == "user"]
        last_user_message = user_messages[-1].content if user_messages else ""
        messages = [{"role": m.role, "content": m.content} for m in request.messages]

        sources = await _retrieve_rag_context(request, last_user_message, db, client)
        if sources:
            messages[-1]["content"] = build_rag_prompt(last_user_message, sources)
            yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"

        try:
            start = datetime.now(timezone.utc)
            prompt_tokens = 0
            completion_tokens = 0
            async with client.stream(
                "POST",
                f"{OLLAMA_URL}/api/chat",
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
            await _log_chat(db, model, prompt_tokens, completion_tokens, latency_ms, bool(sources))
        except Exception:
            logger.exception("Chat stream failed for model %s", model)
            yield f"data: {json.dumps({'type': 'error', 'error': 'Chat stream failed'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
