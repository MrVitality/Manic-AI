"""Router-level integration tests for /v1/feedback endpoints.

These tests use the shared ``client`` fixture from conftest.py which wires
a real FastAPI app with mocked DB/HTTP/Redis dependencies.
"""

from unittest.mock import AsyncMock

import pytest


# ---------------------------------------------------------------------------
# POST /v1/feedback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_feedback_valid_thumbs_up_returns_200(client, app):
    """Valid thumbs-up rating (1) returns 200 with id and rating in data."""
    conn = app.state.db_pool._mock_conn
    conn.fetchval = AsyncMock(return_value="feed-id-001")

    resp = await client.post("/v1/feedback", json={"rating": 1})

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["rating"] == 1
    assert body["data"]["id"] == "feed-id-001"


@pytest.mark.asyncio
async def test_post_feedback_invalid_rating_returns_422(client):
    """Ratings outside -1/0/1 are rejected with 422 Unprocessable Entity."""
    resp = await client.post("/v1/feedback", json={"rating": 99})

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_post_feedback_missing_rating_returns_422(client):
    """Omitting the required rating field returns 422."""
    resp = await client.post("/v1/feedback", json={"comment": "no rating"})

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_post_feedback_with_comment_returns_200(client, app):
    """Optional comment field is accepted alongside a valid rating."""
    conn = app.state.db_pool._mock_conn
    conn.fetchval = AsyncMock(return_value="feed-id-002")

    resp = await client.post(
        "/v1/feedback",
        json={"rating": 0, "comment": "Mediocre but acceptable."},
    )

    assert resp.status_code == 200
    assert resp.json()["data"]["rating"] == 0


@pytest.mark.asyncio
async def test_post_feedback_with_all_fields_returns_200(client, app):
    """All optional fields together are accepted and return 200."""
    conn = app.state.db_pool._mock_conn
    conn.fetchval = AsyncMock(return_value="feed-id-003")

    resp = await client.post(
        "/v1/feedback",
        json={
            "rating": -1,
            "comment": "Wrong answer.",
            "conversation_id": "conv-aaa",
            "message_id": "msg-bbb",
            "query_text": "Tell me a joke",
            "response_text": "That was not funny.",
            "had_rag": True,
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["rating"] == -1


# ---------------------------------------------------------------------------
# GET /v1/feedback/stats
# ---------------------------------------------------------------------------


def _stats_row():
    return {
        "total_feedback": 50,
        "positive_count": 35,
        "negative_count": 5,
        "neutral_count": 10,
        "positive_rate": 70.0,
        "avg_rating": 0.5,
        "rag_positive_rate": 75.0,
        "non_rag_positive_rate": 65.0,
    }


@pytest.mark.asyncio
async def test_get_feedback_stats_returns_200(client, app):
    """GET /v1/feedback/stats returns 200 with aggregated data."""
    conn = app.state.db_pool._mock_conn
    conn.fetchrow = AsyncMock(return_value=_stats_row())

    resp = await client.get("/v1/feedback/stats")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "total_feedback" in body["data"]
    assert "positive_rate" in body["data"]


@pytest.mark.asyncio
async def test_get_feedback_stats_with_days_7_returns_200(client, app):
    """?days=7 is accepted and the days field in the response equals 7."""
    conn = app.state.db_pool._mock_conn
    conn.fetchrow = AsyncMock(return_value=_stats_row())

    resp = await client.get("/v1/feedback/stats?days=7")

    assert resp.status_code == 200
    assert resp.json()["data"]["days"] == 7


@pytest.mark.asyncio
async def test_get_feedback_stats_days_zero_returns_422(client):
    """days=0 is below the minimum (ge=1) and returns 422."""
    resp = await client.get("/v1/feedback/stats?days=0")

    assert resp.status_code == 422
