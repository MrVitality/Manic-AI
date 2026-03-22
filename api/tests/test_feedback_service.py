"""Tests for api/services/feedback.py — service-layer unit tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from api.services.feedback import get_feedback_stats, submit_feedback


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pool(conn: AsyncMock) -> MagicMock:
    """Build a minimal mock pool whose acquire() yields *conn*."""
    pool = MagicMock()

    class _CM:
        async def __aenter__(self):
            return conn

        async def __aexit__(self, *args):
            return False

    pool.acquire = MagicMock(side_effect=lambda: _CM())
    return pool


# ---------------------------------------------------------------------------
# submit_feedback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_feedback_inserts_row_and_returns_id():
    """submit_feedback calls INSERT and returns the new row ID string."""
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value="abc-123")
    pool = _make_pool(conn)

    result = await submit_feedback(pool, rating=1)

    conn.fetchval.assert_called_once()
    assert result == "abc-123"


@pytest.mark.asyncio
async def test_submit_feedback_with_all_optional_fields():
    """submit_feedback passes all optional columns to the INSERT statement."""
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value="full-id-000")
    pool = _make_pool(conn)

    result = await submit_feedback(
        pool,
        rating=1,
        comment="Great answer",
        conversation_id="conv-abc",
        message_id="msg-xyz",
        query_text="What is AI?",
        response_text="AI is ...",
        had_rag=True,
    )

    assert result == "full-id-000"
    args = conn.fetchval.call_args[0]
    # The 7 positional params after the SQL string should include all columns
    assert 1 in args          # rating
    assert "Great answer" in args
    assert "conv-abc" in args
    assert "msg-xyz" in args
    assert True in args        # had_rag


@pytest.mark.asyncio
async def test_submit_feedback_returns_none_on_db_error():
    """submit_feedback propagates the exception from the DB layer."""
    conn = AsyncMock()
    conn.fetchval = AsyncMock(side_effect=Exception("DB exploded"))
    pool = _make_pool(conn)

    with pytest.raises(Exception, match="DB exploded"):
        await submit_feedback(pool, rating=-1)


# ---------------------------------------------------------------------------
# get_feedback_stats
# ---------------------------------------------------------------------------


def _make_stats_row(**overrides):
    """Build a fake asyncpg record-like dict for feedback stats."""
    base = {
        "total_feedback": 100,
        "positive_count": 70,
        "negative_count": 10,
        "neutral_count": 20,
        "positive_rate": 70.0,
        "avg_rating": 0.6,
        "rag_positive_rate": 80.0,
        "non_rag_positive_rate": 55.0,
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_get_feedback_stats_returns_correct_structure():
    """get_feedback_stats returns a dict with all expected keys."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=_make_stats_row())
    pool = _make_pool(conn)

    result = await get_feedback_stats(pool, days=30)

    assert result["days"] == 30
    assert result["total_feedback"] == 100
    assert result["positive_count"] == 70
    assert result["negative_count"] == 10
    assert result["neutral_count"] == 20
    assert result["positive_rate"] == 70.0
    assert result["avg_rating"] == 0.6
    assert result["rag_positive_rate"] == 80.0
    assert result["non_rag_positive_rate"] == 55.0


@pytest.mark.asyncio
async def test_get_feedback_stats_handles_none_values_from_db():
    """None values for nullable rate columns are coerced to 0.0."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=_make_stats_row(
        positive_rate=None,
        avg_rating=None,
        rag_positive_rate=None,
        non_rag_positive_rate=None,
    ))
    pool = _make_pool(conn)

    result = await get_feedback_stats(pool, days=30)

    assert result["positive_rate"] == 0.0
    assert result["avg_rating"] == 0.0
    assert result["rag_positive_rate"] == 0.0
    assert result["non_rag_positive_rate"] == 0.0


@pytest.mark.asyncio
async def test_get_feedback_stats_custom_days_parameter():
    """days parameter is forwarded to the SQL query."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=_make_stats_row(
        total_feedback=5, positive_count=4, negative_count=1, neutral_count=0,
        positive_rate=80.0, avg_rating=0.6, rag_positive_rate=None, non_rag_positive_rate=None,
    ))
    pool = _make_pool(conn)

    result = await get_feedback_stats(pool, days=7)

    assert result["days"] == 7
    # Ensure the SQL call included "7" as the days string arg
    call_args = conn.fetchrow.call_args[0]
    assert "7" in call_args


@pytest.mark.asyncio
async def test_get_feedback_stats_returns_zeros_when_no_data():
    """An all-zero result (empty table) is returned cleanly."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=_make_stats_row(
        total_feedback=0, positive_count=0, negative_count=0, neutral_count=0,
        positive_rate=None, avg_rating=None, rag_positive_rate=None, non_rag_positive_rate=None,
    ))
    pool = _make_pool(conn)

    result = await get_feedback_stats(pool, days=30)

    assert result["total_feedback"] == 0
    assert result["positive_count"] == 0
    assert result["avg_rating"] == 0.0


@pytest.mark.asyncio
async def test_get_feedback_stats_returns_none_on_db_error():
    """DB errors propagate out of get_feedback_stats."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(side_effect=Exception("connection reset"))
    pool = _make_pool(conn)

    with pytest.raises(Exception, match="connection reset"):
        await get_feedback_stats(pool, days=30)
