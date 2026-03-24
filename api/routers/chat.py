"""Chat routes -- thin wrappers around services.chat."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
import asyncpg
import httpx

from api.config import settings
from api.dependencies import get_db_optional, get_http_client, get_langfuse
from api.middleware.rate_limit import limiter
from api.schemas.chat import ChatRequest
from api.schemas.envelope import ok
from api.services.chat import complete_chat, stream_chat

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/chat", response_model=None, tags=["chat"])
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def chat(
    request: Request,
    body: ChatRequest,
    client: httpx.AsyncClient = Depends(get_http_client),
    db: Optional[asyncpg.Pool] = Depends(get_db_optional),
    langfuse=Depends(get_langfuse),
):
    try:
        result = await complete_chat(body, client, db, langfuse)
        return ok(result.model_dump())
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Chat service unavailable")
    except Exception:
        logger.exception("Unexpected error during chat")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/chat/stream", tags=["chat"])
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def chat_stream_endpoint(
    request: Request,
    body: ChatRequest,
    client: httpx.AsyncClient = Depends(get_http_client),
    db: Optional[asyncpg.Pool] = Depends(get_db_optional),
):
    return StreamingResponse(
        stream_chat(body, client, db),
        media_type="text/event-stream",
    )
