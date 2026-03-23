"""Server-side conversation persistence API.

Manages conversations and their messages stored in ``public.conversations``
and ``public.messages``.  The ``conversations`` table has no dedicated
``user_id`` column; user ownership is stored in the ``metadata`` JSONB field
so that existing rows remain forward-compatible.
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.dependencies import get_db
from api.schemas.envelope import ok

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversations")


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class ConversationCreate(BaseModel):
    title: str = Field(default="New Conversation", max_length=255)
    system_prompt: Optional[str] = None
    user_id: Optional[str] = None


class ConversationUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=255)
    system_prompt: Optional[str] = None


class MessageCreate(BaseModel):
    role: str = Field(..., pattern=r"^(user|assistant|system)$")
    content: str = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# Helper: serialize asyncpg row to dict
# ---------------------------------------------------------------------------


def _conv_row(row: Any) -> Dict[str, Any]:
    return {
        "id": str(row["id"]),
        "title": row["title"],
        "system_prompt": row["system_prompt"],
        "metadata": row["metadata"] or {},
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
    }


def _msg_row(row: Any) -> Dict[str, Any]:
    return {
        "id": str(row["id"]),
        "conversation_id": str(row["conversation_id"]),
        "role": row["role"],
        "content": row["content"],
        "model": row["model"],
        "tokens_used": row["tokens_used"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=None, tags=["conversations"])
async def list_conversations(
    user_id: Optional[str] = Query(None, description="Filter by user_id stored in metadata"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: asyncpg.Pool = Depends(get_db),
):
    """List conversations with optional user_id filter and pagination."""
    async with db.acquire() as conn:
        if user_id:
            rows = await conn.fetch(
                """
                SELECT id, title, system_prompt, metadata, created_at, updated_at
                FROM public.conversations
                WHERE metadata->>'user_id' = $1
                ORDER BY updated_at DESC
                LIMIT $2 OFFSET $3
                """,
                user_id, limit, offset,
            )
            total: int = await conn.fetchval(
                "SELECT COUNT(*) FROM public.conversations WHERE metadata->>'user_id' = $1",
                user_id,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, title, system_prompt, metadata, created_at, updated_at
                FROM public.conversations
                ORDER BY updated_at DESC
                LIMIT $1 OFFSET $2
                """,
                limit, offset,
            )
            total = await conn.fetchval("SELECT COUNT(*) FROM public.conversations")

    return ok(
        [_conv_row(r) for r in rows],
        meta={"total": total, "limit": limit, "offset": offset},
    )


@router.get("/{conversation_id}", response_model=None, tags=["conversations"])
async def get_conversation(
    conversation_id: str,
    db: asyncpg.Pool = Depends(get_db),
):
    """Return a conversation and all its messages ordered by creation time."""
    async with db.acquire() as conn:
        conv = await conn.fetchrow(
            "SELECT id, title, system_prompt, metadata, created_at, updated_at FROM public.conversations WHERE id = $1",
            conversation_id,
        )
        if not conv:
            raise HTTPException(status_code=404, detail=f"Conversation {conversation_id} not found")

        messages = await conn.fetch(
            """
            SELECT id, conversation_id, role, content, model, tokens_used, created_at
            FROM public.messages
            WHERE conversation_id = $1
            ORDER BY created_at ASC
            """,
            conversation_id,
        )

    data = _conv_row(conv)
    data["messages"] = [_msg_row(m) for m in messages]
    return ok(data)


@router.post("", response_model=None, tags=["conversations"])
async def create_conversation(
    body: ConversationCreate,
    db: asyncpg.Pool = Depends(get_db),
):
    """Create a new conversation.  ``user_id`` is persisted inside ``metadata``."""
    conversation_id = str(uuid4())
    metadata: Dict[str, Any] = {}
    if body.user_id:
        metadata["user_id"] = body.user_id

    async with db.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO public.conversations (id, title, system_prompt, metadata)
            VALUES ($1, $2, $3, $4)
            RETURNING id, title, system_prompt, metadata, created_at, updated_at
            """,
            conversation_id,
            body.title,
            body.system_prompt,
            metadata,
        )

    return ok(_conv_row(row))


@router.patch("/{conversation_id}", response_model=None, tags=["conversations"])
async def update_conversation(
    conversation_id: str,
    body: ConversationUpdate,
    db: asyncpg.Pool = Depends(get_db),
):
    """Update ``title`` and/or ``system_prompt`` on an existing conversation."""
    if body.title is None and body.system_prompt is None:
        raise HTTPException(status_code=400, detail="Provide at least one of: title, system_prompt")

    async with db.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT id FROM public.conversations WHERE id = $1", conversation_id,
        )
        if not existing:
            raise HTTPException(status_code=404, detail=f"Conversation {conversation_id} not found")

        row = await conn.fetchrow(
            """
            UPDATE public.conversations
            SET
                title        = COALESCE($2, title),
                system_prompt = COALESCE($3, system_prompt),
                updated_at   = NOW()
            WHERE id = $1
            RETURNING id, title, system_prompt, metadata, created_at, updated_at
            """,
            conversation_id,
            body.title,
            body.system_prompt,
        )

    return ok(_conv_row(row))


@router.delete("/{conversation_id}", response_model=None, tags=["conversations"])
async def delete_conversation(
    conversation_id: str,
    db: asyncpg.Pool = Depends(get_db),
):
    """Delete a conversation and all its messages (cascade is handled by the DB FK)."""
    async with db.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM public.conversations WHERE id = $1", conversation_id,
        )

    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail=f"Conversation {conversation_id} not found")

    return ok({"deleted": True, "conversation_id": conversation_id})


@router.post("/{conversation_id}/messages", response_model=None, tags=["conversations"])
async def add_message(
    conversation_id: str,
    body: MessageCreate,
    db: asyncpg.Pool = Depends(get_db),
):
    """Append a message to a conversation."""
    async with db.acquire() as conn:
        conv_exists = await conn.fetchval(
            "SELECT id FROM public.conversations WHERE id = $1", conversation_id,
        )
        if not conv_exists:
            raise HTTPException(status_code=404, detail=f"Conversation {conversation_id} not found")

        row = await conn.fetchrow(
            """
            INSERT INTO public.messages (id, conversation_id, role, content)
            VALUES ($1, $2, $3, $4)
            RETURNING id, conversation_id, role, content, model, tokens_used, created_at
            """,
            str(uuid4()),
            conversation_id,
            body.role,
            body.content,
        )

        # Keep conversation.updated_at current so list ordering stays accurate
        await conn.execute(
            "UPDATE public.conversations SET updated_at = NOW() WHERE id = $1",
            conversation_id,
        )

    return ok(_msg_row(row))
