"""Store and aggregate user feedback on chat responses."""
import logging
from typing import Any, Dict, Optional

import asyncpg

logger = logging.getLogger(__name__)


async def submit_feedback(
    db: asyncpg.Pool,
    *,
    rating: int,
    comment: Optional[str] = None,
    conversation_id: Optional[str] = None,
    message_id: Optional[str] = None,
    query_text: Optional[str] = None,
    response_text: Optional[str] = None,
    had_rag: bool = False,
) -> str:
    """Store user feedback on a chat response. Returns the new feedback row ID."""
    async with db.acquire() as conn:
        row_id: str = await conn.fetchval(
            """
            INSERT INTO public.chat_feedback
                (rating, comment, conversation_id, message_id,
                 query_text, response_text, had_rag)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id::TEXT
            """,
            rating,
            comment,
            conversation_id,
            message_id,
            query_text,
            response_text,
            had_rag,
        )
    return row_id


async def get_feedback_stats(
    db: asyncpg.Pool,
    days: int = 30,
) -> Dict[str, Any]:
    """Return aggregated feedback statistics for the last N days."""
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                COUNT(*)                                             AS total_feedback,
                COUNT(*) FILTER (WHERE rating = 1)                  AS positive_count,
                COUNT(*) FILTER (WHERE rating = -1)                 AS negative_count,
                COUNT(*) FILTER (WHERE rating = 0)                  AS neutral_count,
                ROUND(
                    COUNT(*) FILTER (WHERE rating = 1)::NUMERIC /
                    NULLIF(COUNT(*), 0) * 100, 2
                )                                                    AS positive_rate,
                ROUND(AVG(rating)::NUMERIC, 4)                      AS avg_rating,
                ROUND(
                    COUNT(*) FILTER (WHERE had_rag AND rating = 1)::NUMERIC /
                    NULLIF(COUNT(*) FILTER (WHERE had_rag), 0) * 100, 2
                )                                                    AS rag_positive_rate,
                ROUND(
                    COUNT(*) FILTER (WHERE NOT had_rag AND rating = 1)::NUMERIC /
                    NULLIF(COUNT(*) FILTER (WHERE NOT had_rag), 0) * 100, 2
                )                                                    AS non_rag_positive_rate
            FROM public.chat_feedback
            WHERE created_at >= NOW() - ($1 || ' days')::INTERVAL
            """,
            str(days),
        )

    return {
        "days": days,
        "total_feedback": int(row["total_feedback"]),
        "positive_count": int(row["positive_count"]),
        "negative_count": int(row["negative_count"]),
        "neutral_count": int(row["neutral_count"]),
        "positive_rate": float(row["positive_rate"]) if row["positive_rate"] is not None else 0.0,
        "avg_rating": float(row["avg_rating"]) if row["avg_rating"] is not None else 0.0,
        "rag_positive_rate": float(row["rag_positive_rate"]) if row["rag_positive_rate"] is not None else 0.0,
        "non_rag_positive_rate": float(row["non_rag_positive_rate"]) if row["non_rag_positive_rate"] is not None else 0.0,
    }
