"""Tests for api/services/context_enricher.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from api.services.context_enricher import enrich_chunk, enrich_chunks_batch


def _make_http_client(content: str = "This chunk explains the introduction.") -> AsyncMock:
    """Return a mock httpx.AsyncClient that returns *content* as the LLM reply."""
    client = AsyncMock(spec=httpx.AsyncClient)
    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.raise_for_status = MagicMock()
    response.json.return_value = {
        "message": {"content": content}
    }
    client.post = AsyncMock(return_value=response)
    return client


# ---------------------------------------------------------------------------
# enrich_chunk
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enrich_chunk_prepends_context_from_llm():
    """enrich_chunk prepends the LLM context sentence to the chunk text."""
    client = _make_http_client("This section covers model architectures.")
    result = await enrich_chunk(
        chunk_text="Transformers use self-attention mechanisms.",
        document_title="Deep Learning Primer",
        full_content="...",
        http_client=client,
    )

    assert result.startswith("[Context:")
    assert "Transformers use self-attention mechanisms." in result
    client.post.assert_called_once()


@pytest.mark.asyncio
async def test_enrich_chunk_returns_original_on_llm_failure():
    """enrich_chunk returns the original chunk text when the HTTP call fails."""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))

    chunk_text = "Some important content here."
    result = await enrich_chunk(
        chunk_text=chunk_text,
        document_title="Any Doc",
        full_content="...",
        http_client=client,
    )

    assert result == chunk_text


@pytest.mark.asyncio
async def test_enrich_chunk_returns_original_on_empty_llm_response():
    """enrich_chunk returns the original when the LLM returns an empty string."""
    client = _make_http_client(content="")
    chunk_text = "Chunk with no enrichment."
    result = await enrich_chunk(
        chunk_text=chunk_text,
        document_title="Empty Response Doc",
        full_content="...",
        http_client=client,
    )

    assert result == chunk_text


# ---------------------------------------------------------------------------
# enrich_chunks_batch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enrich_chunks_batch_processes_multiple_chunks():
    """enrich_chunks_batch enriches every chunk in the input list."""
    client = _make_http_client("Contextual sentence.")
    chunks = [
        {"index": 0, "content": "Chunk A content."},
        {"index": 1, "content": "Chunk B content."},
        {"index": 2, "content": "Chunk C content."},
    ]

    result = await enrich_chunks_batch(
        chunks=chunks,
        document_title="Test Document",
        full_content="...",
        http_client=client,
    )

    assert len(result) == 3
    for chunk in result:
        assert "[Context:" in chunk["content"]


@pytest.mark.asyncio
async def test_enrich_chunks_batch_handles_partial_failures():
    """enrich_chunks_batch falls back to original content for failed chunks."""
    client = AsyncMock(spec=httpx.AsyncClient)

    call_count = 0

    async def _post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise httpx.ConnectError("failed")
        resp = MagicMock(spec=httpx.Response)
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"message": {"content": "Good context."}}
        return resp

    client.post = _post

    chunks = [
        {"index": 0, "content": "First chunk."},
        {"index": 1, "content": "Second chunk — will fail."},
        {"index": 2, "content": "Third chunk."},
    ]

    result = await enrich_chunks_batch(
        chunks=chunks,
        document_title="Doc",
        full_content="...",
        http_client=client,
    )

    assert len(result) == 3
    # The failed chunk should retain original content (no [Context: prefix)
    assert "Second chunk" in result[1]["content"]


@pytest.mark.asyncio
async def test_enrich_chunks_batch_respects_batch_size():
    """enrich_chunks_batch processes chunks in batches of the given size."""
    post_calls = []

    async def _post(*args, **kwargs):
        post_calls.append(True)
        resp = MagicMock(spec=httpx.Response)
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"message": {"content": "ctx"}}
        return resp

    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = _post

    # 7 chunks with batch_size=3 → 3 batches (3 + 3 + 1)
    chunks = [{"index": i, "content": f"Chunk {i}."} for i in range(7)]

    result = await enrich_chunks_batch(
        chunks=chunks,
        document_title="Doc",
        full_content="...",
        http_client=client,
        batch_size=3,
    )

    assert len(result) == 7
    # All 7 HTTP calls were made
    assert len(post_calls) == 7
