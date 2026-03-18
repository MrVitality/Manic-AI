"""Tests for api/services/ingestion.py — pure-Python paths only.

These tests cover in-memory job tracking, status helpers, and the core
pipeline logic using mocked DB and HTTP clients.  No real DB or network
calls are made.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

import httpx


# ---------------------------------------------------------------------------
# In-memory job tracker
# ---------------------------------------------------------------------------

class TestJobTracker:
    def setup_method(self):
        # Reset the module-level dict before each test
        import api.services.ingestion as ing
        ing._job_status.clear()

    def test_update_job_creates_entry(self):
        from api.services.ingestion import _update_job, _job_status
        _update_job("doc-1", status="pending")
        assert "doc-1" in _job_status
        assert _job_status["doc-1"]["status"] == "pending"

    def test_update_job_merges_fields(self):
        from api.services.ingestion import _update_job, _job_status
        _update_job("doc-2", status="processing")
        _update_job("doc-2", chunks_created=5)
        assert _job_status["doc-2"]["status"] == "processing"
        assert _job_status["doc-2"]["chunks_created"] == 5

    def test_update_job_sets_updated_at(self):
        from api.services.ingestion import _update_job, _job_status
        _update_job("doc-3", status="done")
        assert "updated_at" in _job_status["doc-3"]

    def test_get_job_status_returns_none_for_unknown(self):
        from api.services.ingestion import get_job_status
        assert get_job_status("does-not-exist") is None

    def test_get_job_status_returns_dict(self):
        from api.services.ingestion import _update_job, get_job_status
        _update_job("doc-4", status="completed", chunks_created=3)
        result = get_job_status("doc-4")
        assert result is not None
        assert result["status"] == "completed"
        assert result["chunks_created"] == 3


# ---------------------------------------------------------------------------
# DB helpers — _db_set_status / create_ingest_job / fetch_ingest_job
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_db_set_status_calls_execute(mock_db_pool):
    from api.services.ingestion import _db_set_status
    await _db_set_status(mock_db_pool, "doc-5", "completed", chunks_created=7)
    mock_db_pool.acquire.assert_called()


@pytest.mark.asyncio
async def test_db_set_status_swallows_exception():
    """Should log + not raise when DB is unavailable."""
    from api.services.ingestion import _db_set_status
    bad_pool = AsyncMock()
    bad_pool.acquire.side_effect = Exception("db down")
    # Must not raise
    await _db_set_status(bad_pool, "doc-6", "failed")


@pytest.mark.asyncio
async def test_create_ingest_job_calls_execute(mock_db_pool):
    from api.services.ingestion import create_ingest_job
    await create_ingest_job(mock_db_pool, "doc-7", "file.pdf")
    mock_db_pool.acquire.assert_called()


@pytest.mark.asyncio
async def test_create_ingest_job_swallows_exception():
    from api.services.ingestion import create_ingest_job
    bad_pool = AsyncMock()
    bad_pool.acquire.side_effect = Exception("db down")
    await create_ingest_job(bad_pool, "doc-8", "file.pdf")


@pytest.mark.asyncio
async def test_fetch_ingest_job_returns_none_on_missing(mock_db_pool):
    # conn.fetchrow returns None (default in conftest)
    from api.services.ingestion import fetch_ingest_job
    result = await fetch_ingest_job(mock_db_pool, "doc-9")
    assert result is None


@pytest.mark.asyncio
async def test_fetch_ingest_job_returns_dict_when_found():
    from api.services.ingestion import fetch_ingest_job

    fake_row = {"document_id": "doc-10", "status": "completed", "chunks_created": 4}

    # Build a fresh pool mock with fetchrow returning fake_row
    pool = AsyncMock()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=fake_row)
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=cm)

    result = await fetch_ingest_job(pool, "doc-10")
    assert result == fake_row


# ---------------------------------------------------------------------------
# run_ingest_background — status transitions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_ingest_background_updates_status_on_success(mock_db_pool, mock_http_client):
    import api.services.ingestion as ing
    ing._job_status.clear()

    from api.schemas.ingest import IngestRequest

    request = IngestRequest(
        filename="test.txt",
        content="Hello world",
        content_type="text/plain",
    )

    async def _mock_ingest(req, db, client):
        from api.schemas.ingest import IngestResponse
        return IngestResponse(
            document_id="doc-bg",
            filename="test.txt",
            chunks_created=1,
            status="completed",
        )

    with patch("api.services.ingestion.ingest_document", side_effect=_mock_ingest):
        await ing.run_ingest_background("doc-bg", request, None, mock_http_client)

    status = ing.get_job_status("doc-bg")
    assert status is not None
    assert status["status"] == "completed"
    assert status["chunks_created"] == 1


@pytest.mark.asyncio
async def test_run_ingest_background_updates_status_on_failure(mock_http_client):
    import api.services.ingestion as ing
    ing._job_status.clear()

    from api.schemas.ingest import IngestRequest

    request = IngestRequest(
        filename="broken.txt",
        content="Hello",
        content_type="text/plain",
    )

    async def _boom(req, db, client):
        raise RuntimeError("embedding failed")

    with patch("api.services.ingestion.ingest_document", side_effect=_boom):
        await ing.run_ingest_background("doc-fail", request, None, mock_http_client)

    status = ing.get_job_status("doc-fail")
    assert status["status"] == "failed"
    assert "embedding failed" in status["error"]
