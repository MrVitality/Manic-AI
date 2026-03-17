"""Chat routes -- thin wrappers around services.chat."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
import asyncpg
import httpx

from api.dependencies import get_db_optional, get_http_client, get_langfuse
from api.schemas.chat import ChatRequest, ChatResponse
from api.schemas.envelope import ok
from api.services.chat import complete_chat, stream_chat

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/chat", response_model=None, tags=["chat"])
async def chat(
    request: ChatRequest,
    client: httpx.AsyncClient = Depends(get_http_client),
    db: Optional[asyncpg.Pool] = Depends(get_db_optional),
    langfuse=Depends(get_langfuse),
):
    try:
        result = await complete_chat(request, client, db, langfuse)
        return ok(result.model_dump())
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Chat service unavailable")
    except Exception:
        logger.exception("Unexpected error during chat")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/chat/stream", tags=["chat"])
async def chat_stream_endpoint(
    request: ChatRequest,
    client: httpx.AsyncClient = Depends(get_http_client),
    db: Optional[asyncpg.Pool] = Depends(get_db_optional),
):
    return StreamingResponse(
        stream_chat(request, client, db),
        media_type="text/event-stream",
    )
