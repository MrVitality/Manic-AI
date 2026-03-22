"""Tests for the /v1/feedback endpoints."""

from unittest.mock import AsyncMock, patch

import pytest


# ---------------------------------------------------------------------------
# POST /v1/feedback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_feedback_returns_200(client, app):
    """Valid thumbs-up feedback is stored and returns the new row ID."""
    conn = app.state.db_pool._mock_conn
    conn.fetchval = AsyncMock(return_value="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")

    resp = await client.post(
        "/v1/feedback",
        json={
            "rating": 1,
            "comment": "Great answer!",
            "conversation_id": "conv-123",
            "message_id": "msg-456",
            "had_rag": True,
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["rating"] == 1
    assert body["data"]["id"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


@pytest.mark.asyncio
async def test_submit_feedback_thumbs_down(client, app):
    """Thumbs-down (-1) feedback is accepted."""
    conn = app.state.db_pool._mock_conn
    conn.fetchval = AsyncMock(return_value="11111111-2222-3333-4444-555555555555")

    resp = await client.post("/v1/feedback", json={"rating": -1})

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["rating"] == -1


@pytest.mark.asyncio
async def test_submit_feedback_neutral(client, app):
    """Neutral (0) feedback is accepted."""
    conn = app.state.db_pool._mock_conn
    conn.fetchval = AsyncMock(return_value="00000000-0000-0000-0000-000000000000")

    resp = await client.post("/v1/feedback", json={"rating": 0, "had_rag": False})

    assert resp.status_code == 200
    assert resp.json()["data"]["rating"] == 0


@pytest.mark.asyncio
async def test_submit_feedback_invalid_rating_rejected(client):
    """Ratings outside -1/0/1 are rejected with 422."""
    resp = await client.post("/v1/feedback", json={"rating": 5})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_submit_feedback_missing_rating_rejected(client):
    """Omitting rating entirely is rejected with 422."""
    resp = await client.post("/v1/feedback", json={"comment": "No rating field"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_submit_feedback_comment_too_long(client):
    """Comments exceeding 2000 characters are rejected with 422."""
    resp = await client.post("/v1/feedback", json={"rating": 1, "comment": "x" * 2001})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /v1/feedback/stats
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_feedback_stats_returns_aggregated_data(client, app):
    """Stats endpoint returns aggregated counts and rates."""
    conn = app.state.db_pool._mock_conn
    conn.fetchrow = AsyncMock(return_value={
        "total_feedback": 100,
        "positive_count": 70,
        "negative_count": 10,
        "neutral_count": 20,
        "positive_rate": 70.0,
        "avg_rating": 0.6,
        "rag_positive_rate": 80.0,
        "non_rag_positive_rate": 55.0,
    })

    resp = await client.get("/v1/feedback/stats")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert data["total_feedback"] == 100
    assert data["positive_count"] == 70
    assert data["negative_count"] == 10
    assert data["neutral_count"] == 20
    assert data["positive_rate"] == 70.0
    assert data["avg_rating"] == 0.6
    assert data["rag_positive_rate"] == 80.0
    assert data["non_rag_positive_rate"] == 55.0


@pytest.mark.asyncio
async def test_feedback_stats_custom_days(client, app):
    """days query param is forwarded to the service layer."""
    conn = app.state.db_pool._mock_conn
    conn.fetchrow = AsyncMock(return_value={
        "total_feedback": 5,
        "positive_count": 4,
        "negative_count": 1,
        "neutral_count": 0,
        "positive_rate": 80.0,
        "avg_rating": 0.6,
        "rag_positive_rate": None,
        "non_rag_positive_rate": None,
    })

    resp = await client.get("/v1/feedback/stats?days=7")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["days"] == 7
    # None values are coerced to 0.0
    assert body["data"]["rag_positive_rate"] == 0.0
    assert body["data"]["non_rag_positive_rate"] == 0.0


@pytest.mark.asyncio
async def test_feedback_stats_days_out_of_range(client):
    """days outside 1-365 is rejected with 422."""
    resp = await client.get("/v1/feedback/stats?days=400")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_feedback_stats_days_zero_rejected(client):
    """days=0 is rejected with 422."""
    resp = await client.get("/v1/feedback/stats?days=0")
    assert resp.status_code == 422
