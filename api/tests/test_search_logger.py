"""Tests for api/services/search_logger.py."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from api.services.search_logger import get_search_history, log_search


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pool(conn: AsyncMock) -> MagicMock:
    pool = MagicMock()

    class _CM:
        async def __aenter__(self):
            return conn

        async def __aexit__(self, *args):
            return False

    pool.acquire = MagicMock(side_effect=lambda: _CM())
    return pool


_COMMON_KWARGS = dict(
    query="What is AI?",
    backend="supabase",
    use_hybrid=True,
    top_k=5,
    threshold=0.5,
    keyword_weight=0.3,
    reranked=False,
    results=[],
    latency_ms=42.0,
)


# ---------------------------------------------------------------------------
# log_search
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_log_search_inserts_event_and_returns_id():
    """log_search returns a UUID string on success."""
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="OK")
    pool = _make_pool(conn)

    result = await log_search(pool, **_COMMON_KWARGS)

    assert result is not None
    assert len(result) == 36  # UUID format
    conn.execute.assert_called()


@pytest.mark.asyncio
async def test_log_search_returns_none_when_db_is_none():
    """log_search returns None immediately when db=None."""
    result = await log_search(None, **_COMMON_KWARGS)

    assert result is None


@pytest.mark.asyncio
async def test_log_search_returns_none_on_db_error():
    """log_search swallows DB exceptions and returns None."""
    conn = AsyncMock()
    conn.execute = AsyncMock(side_effect=Exception("insert failed"))
    pool = _make_pool(conn)

    result = await log_search(pool, **_COMMON_KWARGS)

    assert result is None


@pytest.mark.asyncio
async def test_log_search_logs_individual_results():
    """log_search calls execute for each result entry too."""
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="OK")
    pool = _make_pool(conn)

    results = [
        {"id": "chunk-1", "score": 0.9, "vector_score": 0.85, "keyword_score": 0.95, "rerank_score": None},
        {"id": "chunk-2", "score": 0.7, "vector_score": 0.70, "keyword_score": 0.70, "rerank_score": None},
    ]

    await log_search(pool, **{**_COMMON_KWARGS, "results": results})

    # Called once for the main row + once per result
    assert conn.execute.call_count == 3


@pytest.mark.asyncio
async def test_log_search_with_optional_fields():
    """log_search accepts collection_id and user_id without error."""
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="OK")
    pool = _make_pool(conn)

    result = await log_search(
        pool,
        **_COMMON_KWARGS,
        collection_id="col-abc",
        user_id="user-xyz",
    )

    assert result is not None


# ---------------------------------------------------------------------------
# get_search_history
# ---------------------------------------------------------------------------


def _make_search_row(**overrides):
    from datetime import datetime, timezone
    base = {
        "id": "search-001",
        "query": "test query",
        "backend": "supabase",
        "use_hybrid": True,
        "top_k": 5,
        "threshold": 0.5,
        "keyword_weight": 0.3,
        "reranked": False,
        "result_count": 3,
        "avg_score": 0.75,
        "max_score": 0.92,
        "latency_ms": 50.0,
        "collection_id": None,
        "created_at": datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_get_search_history_returns_formatted_list():
    """get_search_history returns a list of dicts with correct shape."""
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[_make_search_row()])
    pool = _make_pool(conn)

    result = await get_search_history(pool)

    assert isinstance(result, list)
    assert len(result) == 1
    row = result[0]
    assert row["id"] == "search-001"
    assert row["query"] == "test query"
    assert row["backend"] == "supabase"
    assert isinstance(row["avg_score"], float)
    assert isinstance(row["latency_ms"], float)
    assert row["created_at"] is not None


@pytest.mark.asyncio
async def test_get_search_history_with_pagination_params():
    """get_search_history passes limit and offset to the DB query."""
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    pool = _make_pool(conn)

    await get_search_history(pool, limit=10, offset=20)

    args = conn.fetch.call_args[0]
    assert 10 in args
    assert 20 in args
