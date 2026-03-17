"""Tests for api.services.reranker with mocked Ollama responses."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from api.services.reranker import rerank_chunks, _score_chunk


@pytest.fixture()
def sample_chunks():
    return [
        {"content": "Python is a programming language.", "score": 0.8},
        {"content": "The weather is nice today.", "score": 0.7},
        {"content": "Machine learning uses algorithms.", "score": 0.6},
    ]


def _make_ollama_response(score: float) -> MagicMock:
    """Build a mock httpx.Response that mimics Ollama's /api/chat output."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "message": {"content": json.dumps({"score": score})}
    }
    return resp


@pytest.mark.asyncio
async def test_rerank_empty_chunks():
    """Empty input should return empty output."""
    client = AsyncMock(spec=httpx.AsyncClient)
    result = await rerank_chunks("test query", [], client)
    assert result == []


@pytest.mark.asyncio
async def test_rerank_returns_top_n(sample_chunks):
    """Should return at most top_n chunks, sorted by rerank score."""
    client = AsyncMock(spec=httpx.AsyncClient)
    # Return different scores for each chunk
    scores = [8.0, 2.0, 6.0]
    client.post = AsyncMock(
        side_effect=[_make_ollama_response(s) for s in scores]
    )

    with patch("api.services.reranker.settings") as mock_settings:
        mock_settings.CHAT_MODEL = "test-model"
        mock_settings.OLLAMA_URL = "http://mock-ollama:11434"
        result = await rerank_chunks("test query", sample_chunks, client, top_n=2)

    assert len(result) == 2
    # First result should have the highest rerank_score
    assert result[0]["rerank_score"] == 8.0
    assert result[1]["rerank_score"] == 6.0


@pytest.mark.asyncio
async def test_rerank_adds_rerank_score(sample_chunks):
    """Each returned chunk should have a rerank_score field."""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(
        side_effect=[_make_ollama_response(5.0) for _ in sample_chunks]
    )

    with patch("api.services.reranker.settings") as mock_settings:
        mock_settings.CHAT_MODEL = "test-model"
        mock_settings.OLLAMA_URL = "http://mock-ollama:11434"
        result = await rerank_chunks("query", sample_chunks, client, top_n=10)

    for chunk in result:
        assert "rerank_score" in chunk
        assert 0.0 <= chunk["rerank_score"] <= 10.0


@pytest.mark.asyncio
async def test_rerank_preserves_original_score(sample_chunks):
    """Original retrieval score should be preserved on returned chunks."""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(
        side_effect=[_make_ollama_response(7.0) for _ in sample_chunks]
    )

    with patch("api.services.reranker.settings") as mock_settings:
        mock_settings.CHAT_MODEL = "test-model"
        mock_settings.OLLAMA_URL = "http://mock-ollama:11434"
        result = await rerank_chunks("query", sample_chunks, client, top_n=10)

    original_scores = {c["content"]: c["score"] for c in sample_chunks}
    for chunk in result:
        assert chunk["score"] == original_scores[chunk["content"]]


@pytest.mark.asyncio
async def test_score_chunk_handles_invalid_json():
    """If Ollama returns non-JSON, _score_chunk should return 0.0."""
    client = AsyncMock(spec=httpx.AsyncClient)
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"message": {"content": "not valid json"}}
    client.post = AsyncMock(return_value=resp)

    with patch("api.services.reranker.settings") as mock_settings:
        mock_settings.OLLAMA_URL = "http://mock-ollama:11434"
        score = await _score_chunk("query", {"content": "text"}, client, "model")

    assert score == 0.0


@pytest.mark.asyncio
async def test_score_chunk_handles_http_error():
    """If Ollama HTTP call fails, _score_chunk should return 0.0."""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(side_effect=httpx.HTTPError("connection refused"))

    with patch("api.services.reranker.settings") as mock_settings:
        mock_settings.OLLAMA_URL = "http://mock-ollama:11434"
        score = await _score_chunk("query", {"content": "text"}, client, "model")

    assert score == 0.0


@pytest.mark.asyncio
async def test_score_chunk_clamps_score():
    """Scores above 10 or below 0 should be clamped."""
    client = AsyncMock(spec=httpx.AsyncClient)
    resp = _make_ollama_response(15.0)
    client.post = AsyncMock(return_value=resp)

    with patch("api.services.reranker.settings") as mock_settings:
        mock_settings.OLLAMA_URL = "http://mock-ollama:11434"
        score = await _score_chunk("query", {"content": "text"}, client, "model")

    assert score == 10.0
