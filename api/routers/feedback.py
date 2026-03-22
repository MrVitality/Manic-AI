"""User feedback endpoints for chat response quality tracking."""
import logging
from typing import Any, Dict, Optional

import asyncpg
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from api.dependencies import get_db
from api.schemas.envelope import ok
from api.services.feedback import get_feedback_stats, submit_feedback

logger = logging.getLogger(__name__)
router = APIRouter()


class FeedbackRequest(BaseModel):
    """Payload for submitting feedback on a chat response."""

    rating: int = Field(..., description="Thumbs up (1), neutral (0), or thumbs down (-1)")
    comment: Optional[str] = Field(None, max_length=2000, description="Optional free-text comment")
    conversation_id: Optional[str] = Field(None, description="Conversation session identifier")
    message_id: Optional[str] = Field(None, description="Specific message identifier within the conversation")
    query_text: Optional[str] = Field(None, description="The user query that prompted the response")
    response_text: Optional[str] = Field(None, description="The assistant response being rated")
    had_rag: bool = Field(False, description="Whether the response was generated with RAG context")

    model_config = {"json_schema_extra": {"example": {
        "rating": 1,
        "comment": "Accurate and concise answer",
        "conversation_id": "conv-abc123",
        "message_id": "msg-xyz789",
        "had_rag": True,
    }}}


@router.post("/feedback", response_model=None, tags=["feedback"])
async def create_feedback(
    body: FeedbackRequest,
    db: asyncpg.Pool = Depends(get_db),
) -> Dict[str, Any]:
    """Submit user feedback (thumbs up/neutral/down) on a chat response.

    - **rating**: must be -1, 0, or 1
    - **comment**: optional free-text (max 2 000 chars)
    - **conversation_id** / **message_id**: link back to the originating message
    - **had_rag**: flag whether the response was RAG-augmented
    """
    if body.rating not in (-1, 0, 1):
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="rating must be -1, 0, or 1")

    feedback_id = await submit_feedback(
        db,
        rating=body.rating,
        comment=body.comment,
        conversation_id=body.conversation_id,
        message_id=body.message_id,
        query_text=body.query_text,
        response_text=body.response_text,
        had_rag=body.had_rag,
    )
    return ok({"id": feedback_id, "rating": body.rating})


@router.get("/feedback/stats", response_model=None, tags=["feedback"])
async def feedback_stats(
    days: int = Query(30, ge=1, le=365, description="Lookback window in days"),
    db: asyncpg.Pool = Depends(get_db),
) -> Dict[str, Any]:
    """Return aggregated feedback statistics for the last N days.

    Includes overall counts, positive rate, average rating, and a RAG vs
    non-RAG positive-rate breakdown.
    """
    stats = await get_feedback_stats(db, days=days)
    return ok(stats)
