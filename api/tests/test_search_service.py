"""Tests for search service -- unified_search deduplication, routing, and reranking."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chunk(
    content: str,
    score: float = 0.9,
    chunk_id: str = "chunk-1",
    doc_id: str = "doc-1",
    backend: str = "supabase",
) -> dict:
    """Build a minimal search result chunk dict."""
    return {
        "id": chunk_id,
        "document_id": doc_id,
        "content": content,
        "metadata": {},
        "score": score,
        "backend": backend,
    }


def _make_mock_http_client() -> AsyncMock:
    """Return a bare mock httpx.AsyncClient."""
    return AsyncMock(spec=httpx.AsyncClient)


# ---------------------------------------------------------------------------
# unified_search -- supabase-only backend
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unified_search_supabase_only_calls_vector_search(mock_db_pool):
    """backend='supabase' calls SupabaseVectorRepository.vector_search only."""
    from api.services.search import unified_search

    expected = [_make_chunk("chunk content", score=0.85)]

    with patch("api.services.search.SupabaseVectorRepository") as MockRepo:
        mock_repo = MockRepo.return_value
        mock_repo.vector_search = AsyncMock(return_value=expected)

        results = await unified_search(
            query_text="test query",
            query_embedding=[0.1, 0.2],
            backend="supabase",
            top_k=5,
            threshold=0.7,
            use_hybrid=False,
            collection_id=None,
            user_id=None,
            db=mock_db_pool,
            client=_make_mock_http_client(),
        )

    mock_repo.vector_search.assert_called_once()
    assert len(results) == 1
    assert results[0]["content"] == "chunk content"


@pytest.mark.asyncio
async def test_unified_search_supabase_only_does_not_call_qdrant(mock_db_pool):
    """backend='supabase' must never instantiate QdrantVectorRepository."""
    from api.services.search import unified_search

    with patch("api.services.search.SupabaseVectorRepository") as MockSB, \
         patch("api.services.search.QdrantVectorRepository") as MockQdrant:

        mock_sb_repo = MockSB.return_value
        mock_sb_repo.vector_search = AsyncMock(return_value=[])

        await unified_search(
            query_text="test",
            query_embedding=[0.1],
            backend="supabase",
            top_k=5,
            threshold=0.7,
            use_hybrid=False,
            collection_id=None,
            user_id=None,
            db=mock_db_pool,
            client=_make_mock_http_client(),
        )

    MockQdrant.assert_not_called()


@pytest.mark.asyncio
async def test_unified_search_supabase_only_uses_hybrid_when_flag_set(mock_db_pool):
    """When use_hybrid=True, hybrid_search is called instead of vector_search."""
    from api.services.search import unified_search

    with patch("api.services.search.SupabaseVectorRepository") as MockRepo:
        mock_repo = MockRepo.return_value
        mock_repo.hybrid_search = AsyncMock(return_value=[])
        mock_repo.vector_search = AsyncMock(return_value=[])

        await unified_search(
            query_text="hybrid query",
            query_embedding=[0.1, 0.2],
            backend="supabase",
            top_k=5,
            threshold=0.7,
            use_hybrid=True,
            collection_id=None,
            user_id=None,
            db=mock_db_pool,
            client=_make_mock_http_client(),
        )

    mock_repo.hybrid_search.assert_called_once()
    mock_repo.vector_search.assert_not_called()


# ---------------------------------------------------------------------------
# unified_search -- qdrant-only backend
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unified_search_qdrant_only_calls_qdrant_search(mock_db_pool):
    """backend='qdrant' calls QdrantVectorRepository.search only."""
    from api.services.search import unified_search

    expected = [_make_chunk("qdrant chunk", score=0.88, backend="qdrant")]

    with patch("api.services.search.QdrantVectorRepository") as MockQdrant, \
         patch("api.services.search.SupabaseVectorRepository") as MockSB:

        mock_q = MockQdrant.return_value
        mock_q.search = AsyncMock(return_value=expected)

        results = await unified_search(
            query_text="test",
            query_embedding=[0.1],
            backend="qdrant",
            top_k=5,
            threshold=0.7,
            use_hybrid=False,
            collection_id=None,
            user_id=None,
            db=mock_db_pool,
            client=_make_mock_http_client(),
        )

    MockSB.assert_not_called()
    mock_q.search.assert_called_once()
    assert results[0]["content"] == "qdrant chunk"


# ---------------------------------------------------------------------------
# unified_search -- both backends, deduplication
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unified_search_deduplicates_both_backends(mock_db_pool):
    """backend='both' removes duplicate chunks that share the same content prefix."""
    from api.services.search import unified_search

    # Two chunks with identical content (first 100 chars match)
    shared_content = "A" * 120
    chunk_supabase = _make_chunk(shared_content, score=0.9, chunk_id="sb-1", backend="supabase")
    chunk_qdrant = _make_chunk(shared_content, score=0.85, chunk_id="qd-1", backend="qdrant")

    with patch("api.services.search.SupabaseVectorRepository") as MockSB, \
         patch("api.services.search.QdrantVectorRepository") as MockQdrant:

        mock_sb = MockSB.return_value
        mock_sb.vector_search = AsyncMock(return_value=[chunk_supabase])

        mock_q = MockQdrant.return_value
        mock_q.search = AsyncMock(return_value=[chunk_qdrant])

        results = await unified_search(
            query_text="test",
            query_embedding=[0.1],
            backend="both",
            top_k=10,
            threshold=0.7,
            use_hybrid=False,
            collection_id=None,
            user_id=None,
            db=mock_db_pool,
            client=_make_mock_http_client(),
        )

    # Duplicate must be removed -- only 1 result despite 2 backends returning the same content
    assert len(results) == 1


@pytest.mark.asyncio
async def test_unified_search_deduplication_keeps_higher_score(mock_db_pool):
    """When deduplicating, the chunk with the higher score is retained (sorted first)."""
    from api.services.search import unified_search

    shared_content = "B" * 100
    low_score = _make_chunk(shared_content, score=0.75, chunk_id="low", backend="qdrant")
    high_score = _make_chunk(shared_content, score=0.95, chunk_id="high", backend="supabase")

    with patch("api.services.search.SupabaseVectorRepository") as MockSB, \
         patch("api.services.search.QdrantVectorRepository") as MockQdrant:

        mock_sb = MockSB.return_value
        # Return the high-score chunk from supabase
        mock_sb.vector_search = AsyncMock(return_value=[high_score])

        mock_q = MockQdrant.return_value
        mock_q.search = AsyncMock(return_value=[low_score])

        results = await unified_search(
            query_text="test",
            query_embedding=[0.1],
            backend="both",
            top_k=10,
            threshold=0.7,
            use_hybrid=False,
            collection_id=None,
            user_id=None,
            db=mock_db_pool,
            client=_make_mock_http_client(),
        )

    assert len(results) == 1
    assert results[0]["score"] == 0.95


@pytest.mark.asyncio
async def test_unified_search_both_keeps_distinct_chunks(mock_db_pool):
    """When backend='both', distinct content chunks from each source are all retained."""
    from api.services.search import unified_search

    sb_chunk = _make_chunk("unique supabase content", score=0.9, chunk_id="sb-1")
    qd_chunk = _make_chunk("unique qdrant content", score=0.88, chunk_id="qd-1", backend="qdrant")

    with patch("api.services.search.SupabaseVectorRepository") as MockSB, \
         patch("api.services.search.QdrantVectorRepository") as MockQdrant:

        mock_sb = MockSB.return_value
        mock_sb.vector_search = AsyncMock(return_value=[sb_chunk])

        mock_q = MockQdrant.return_value
        mock_q.search = AsyncMock(return_value=[qd_chunk])

        results = await unified_search(
            query_text="test",
            query_embedding=[0.1],
            backend="both",
            top_k=10,
            threshold=0.7,
            use_hybrid=False,
            collection_id=None,
            user_id=None,
            db=mock_db_pool,
            client=_make_mock_http_client(),
        )

    assert len(results) == 2


@pytest.mark.asyncio
async def test_unified_search_both_no_db_skips_supabase():
    """When db=None and backend='both', Supabase branch is silently skipped."""
    from api.services.search import unified_search

    qd_chunk = _make_chunk("qdrant only", score=0.8, chunk_id="qd-1", backend="qdrant")

    with patch("api.services.search.SupabaseVectorRepository") as MockSB, \
         patch("api.services.search.QdrantVectorRepository") as MockQdrant:

        mock_q = MockQdrant.return_value
        mock_q.search = AsyncMock(return_value=[qd_chunk])

        results = await unified_search(
            query_text="test",
            query_embedding=[0.1],
            backend="both",
            top_k=10,
            threshold=0.7,
            use_hybrid=False,
            collection_id=None,
            user_id=None,
            db=None,  # no DB
            client=_make_mock_http_client(),
        )

    MockSB.assert_not_called()
    assert len(results) == 1


# ---------------------------------------------------------------------------
# unified_search -- reranking expands top_k to 20
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unified_search_expands_to_20_when_reranking(mock_db_pool):
    """When rerank=True, vector_search is called with top_k=20 for candidate expansion."""
    from api.services.search import unified_search

    with patch("api.services.search.SupabaseVectorRepository") as MockRepo, \
         patch("api.services.search.rerank_chunks", new_callable=AsyncMock) as mock_rerank:

        mock_repo = MockRepo.return_value
        mock_repo.vector_search = AsyncMock(return_value=[])
        mock_rerank.return_value = []

        await unified_search(
            query_text="rerank query",
            query_embedding=[0.1],
            backend="supabase",
            top_k=5,  # requested top_k
            threshold=0.7,
            use_hybrid=False,
            collection_id=None,
            user_id=None,
            db=mock_db_pool,
            client=_make_mock_http_client(),
            rerank=True,
        )

    call_kwargs = mock_repo.vector_search.call_args.kwargs
    # retrieval_top_k should be overridden to 20
    assert call_kwargs.get("top_k") == 20


@pytest.mark.asyncio
async def test_unified_search_does_not_expand_when_not_reranking(mock_db_pool):
    """When rerank=False, vector_search uses the caller-supplied top_k unchanged."""
    from api.services.search import unified_search

    with patch("api.services.search.SupabaseVectorRepository") as MockRepo:
        mock_repo = MockRepo.return_value
        mock_repo.vector_search = AsyncMock(return_value=[])

        await unified_search(
            query_text="no rerank",
            query_embedding=[0.1],
            backend="supabase",
            top_k=7,
            threshold=0.7,
            use_hybrid=False,
            collection_id=None,
            user_id=None,
            db=mock_db_pool,
            client=_make_mock_http_client(),
            rerank=False,
        )

    call_kwargs = mock_repo.vector_search.call_args.kwargs
    assert call_kwargs.get("top_k") == 7


@pytest.mark.asyncio
async def test_unified_search_calls_rerank_chunks_when_enabled(mock_db_pool):
    """When rerank=True and results exist, rerank_chunks is called with correct args."""
    from api.services.search import unified_search

    chunks = [_make_chunk("some content", score=0.8)]

    with patch("api.services.search.SupabaseVectorRepository") as MockRepo, \
         patch("api.services.search.rerank_chunks", new_callable=AsyncMock) as mock_rerank:

        mock_repo = MockRepo.return_value
        mock_repo.vector_search = AsyncMock(return_value=chunks)
        mock_rerank.return_value = chunks

        http_client = _make_mock_http_client()
        await unified_search(
            query_text="rerank me",
            query_embedding=[0.1],
            backend="supabase",
            top_k=3,
            threshold=0.7,
            use_hybrid=False,
            collection_id=None,
            user_id=None,
            db=mock_db_pool,
            client=http_client,
            rerank=True,
        )

    mock_rerank.assert_called_once()
    call_kwargs = mock_rerank.call_args.kwargs
    assert call_kwargs["query"] == "rerank me"
    assert call_kwargs["chunks"] == chunks
    assert call_kwargs["top_n"] == 3


@pytest.mark.asyncio
async def test_unified_search_skips_rerank_when_no_results(mock_db_pool):
    """rerank_chunks must not be called when the result list is empty."""
    from api.services.search import unified_search

    with patch("api.services.search.SupabaseVectorRepository") as MockRepo, \
         patch("api.services.search.rerank_chunks", new_callable=AsyncMock) as mock_rerank:

        mock_repo = MockRepo.return_value
        mock_repo.vector_search = AsyncMock(return_value=[])

        await unified_search(
            query_text="empty",
            query_embedding=[0.1],
            backend="supabase",
            top_k=5,
            threshold=0.7,
            use_hybrid=False,
            collection_id=None,
            user_id=None,
            db=mock_db_pool,
            client=_make_mock_http_client(),
            rerank=True,
        )

    mock_rerank.assert_not_called()


# ---------------------------------------------------------------------------
# unified_search -- top_k slicing without reranking
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unified_search_slices_to_top_k_without_reranking(mock_db_pool):
    """Without reranking, results are sliced to the requested top_k."""
    from api.services.search import unified_search

    # 8 chunks returned, top_k=3 requested
    many_chunks = [
        _make_chunk(f"content {i}", score=0.9 - i * 0.05, chunk_id=f"c{i}")
        for i in range(8)
    ]

    with patch("api.services.search.SupabaseVectorRepository") as MockRepo:
        mock_repo = MockRepo.return_value
        mock_repo.vector_search = AsyncMock(return_value=many_chunks)

        results = await unified_search(
            query_text="slice test",
            query_embedding=[0.1],
            backend="supabase",
            top_k=3,
            threshold=0.7,
            use_hybrid=False,
            collection_id=None,
            user_id=None,
            db=mock_db_pool,
            client=_make_mock_http_client(),
            rerank=False,
        )

    assert len(results) == 3


# ---------------------------------------------------------------------------
# unified_search -- backend annotation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unified_search_annotates_supabase_results_with_backend(mock_db_pool):
    """Supabase results must have backend='supabase' set on each row."""
    from api.services.search import unified_search

    # Return a chunk without 'backend' key to simulate raw repo output
    raw_chunk = {
        "id": "c1",
        "document_id": "d1",
        "content": "test",
        "metadata": {},
        "score": 0.9,
    }

    with patch("api.services.search.SupabaseVectorRepository") as MockRepo:
        mock_repo = MockRepo.return_value
        mock_repo.vector_search = AsyncMock(return_value=[raw_chunk])

        results = await unified_search(
            query_text="annotation test",
            query_embedding=[0.1],
            backend="supabase",
            top_k=5,
            threshold=0.7,
            use_hybrid=False,
            collection_id=None,
            user_id=None,
            db=mock_db_pool,
            client=_make_mock_http_client(),
        )

    assert results[0]["backend"] == "supabase"


# ---------------------------------------------------------------------------
# unified_search -- collection_id and user_id filtering
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unified_search_passes_collection_id_to_supabase(mock_db_pool):
    """collection_id is forwarded to SupabaseVectorRepository.vector_search."""
    from api.services.search import unified_search

    with patch("api.services.search.SupabaseVectorRepository") as MockRepo:
        mock_repo = MockRepo.return_value
        mock_repo.vector_search = AsyncMock(return_value=[])

        await unified_search(
            query_text="filter test",
            query_embedding=[0.1],
            backend="supabase",
            top_k=5,
            threshold=0.7,
            use_hybrid=False,
            collection_id="coll-123",
            user_id=None,
            db=mock_db_pool,
            client=_make_mock_http_client(),
        )

    call_kwargs = mock_repo.vector_search.call_args.kwargs
    assert call_kwargs.get("collection_id") == "coll-123"


@pytest.mark.asyncio
async def test_unified_search_passes_filters_to_qdrant(mock_db_pool):
    """collection_id and user_id are forwarded as filters to QdrantVectorRepository."""
    from api.services.search import unified_search

    with patch("api.services.search.QdrantVectorRepository") as MockQdrant:
        mock_q = MockQdrant.return_value
        mock_q.search = AsyncMock(return_value=[])

        await unified_search(
            query_text="filter test",
            query_embedding=[0.1],
            backend="qdrant",
            top_k=5,
            threshold=0.7,
            use_hybrid=False,
            collection_id="coll-456",
            user_id="user-789",
            db=mock_db_pool,
            client=_make_mock_http_client(),
        )

    call_kwargs = mock_q.search.call_args.kwargs
    filters = call_kwargs.get("filters", {})
    assert filters.get("collection_id") == "coll-456"
    assert filters.get("user_id") == "user-789"
