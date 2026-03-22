"""Tests for api.services.user_auth — per-user authentication scaffolding."""

from __future__ import annotations

import hashlib
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.services.user_auth import (
    authenticate_by_api_key,
    authenticate_by_email,
    create_user,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pool(fetchrow_return: Optional[Dict[str, Any]]) -> MagicMock:
    """Return a mock asyncpg.Pool whose acquired connection returns the given row."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=fetchrow_return)

    pool = MagicMock()
    # pool.acquire() is used as an async context manager
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool, conn


# ---------------------------------------------------------------------------
# create_user
# ---------------------------------------------------------------------------

class TestCreateUser:
    @pytest.mark.asyncio
    async def test_returns_user_dict(self):
        expected = {
            "id": "abc-123",
            "email": "alice@example.com",
            "username": "alice",
            "api_key": "manic_sometoken",
            "created_at": "2026-01-01T00:00:00+00:00",
        }
        pool, conn = _make_pool(expected)

        result = await create_user(pool, "alice@example.com", "s3cr3t", "alice")

        assert result == expected

    @pytest.mark.asyncio
    async def test_password_is_hashed_not_stored_plaintext(self):
        pool, conn = _make_pool({"id": "x", "email": "a@b.com", "username": None, "api_key": "k", "created_at": None})

        await create_user(pool, "a@b.com", "plaintext")

        _, kwargs = conn.fetchrow.call_args
        args = conn.fetchrow.call_args[0]
        # args[0] is the SQL, args[1] is email, args[2] is username, args[3] is password_hash, args[4] is api_key
        stored_hash = args[3]
        assert stored_hash == hashlib.sha256(b"plaintext").hexdigest()
        assert "plaintext" not in stored_hash

    @pytest.mark.asyncio
    async def test_api_key_has_manic_prefix(self):
        pool, conn = _make_pool({"id": "x", "email": "a@b.com", "username": None, "api_key": "k", "created_at": None})

        await create_user(pool, "a@b.com", "pw")

        args = conn.fetchrow.call_args[0]
        api_key = args[4]
        assert api_key.startswith("manic_")

    @pytest.mark.asyncio
    async def test_username_defaults_to_none(self):
        pool, conn = _make_pool({"id": "x", "email": "a@b.com", "username": None, "api_key": "k", "created_at": None})

        await create_user(pool, "a@b.com", "pw")

        args = conn.fetchrow.call_args[0]
        assert args[2] is None  # username positional arg


# ---------------------------------------------------------------------------
# authenticate_by_api_key
# ---------------------------------------------------------------------------

class TestAuthenticateByApiKey:
    @pytest.mark.asyncio
    async def test_returns_user_when_found(self):
        row = {"id": "u1", "email": "bob@example.com", "username": "bob", "is_admin": False, "rate_limit_override": None}
        pool, _ = _make_pool(row)

        result = await authenticate_by_api_key(pool, "manic_validkey")

        assert result == row

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        pool, _ = _make_pool(None)

        result = await authenticate_by_api_key(pool, "manic_badkey")

        assert result is None

    @pytest.mark.asyncio
    async def test_passes_api_key_to_query(self):
        pool, conn = _make_pool(None)

        await authenticate_by_api_key(pool, "manic_mykey")

        args = conn.fetchrow.call_args[0]
        assert "manic_mykey" in args


# ---------------------------------------------------------------------------
# authenticate_by_email
# ---------------------------------------------------------------------------

class TestAuthenticateByEmail:
    @pytest.mark.asyncio
    async def test_returns_user_on_valid_credentials(self):
        row = {"id": "u2", "email": "carol@example.com", "username": "carol", "api_key": "manic_x", "is_admin": False}
        pool, _ = _make_pool(row)

        result = await authenticate_by_email(pool, "carol@example.com", "correct")

        assert result == row

    @pytest.mark.asyncio
    async def test_returns_none_on_invalid_credentials(self):
        pool, _ = _make_pool(None)

        result = await authenticate_by_email(pool, "carol@example.com", "wrong")

        assert result is None

    @pytest.mark.asyncio
    async def test_password_hashed_before_query(self):
        pool, conn = _make_pool(None)

        await authenticate_by_email(pool, "x@y.com", "mypassword")

        args = conn.fetchrow.call_args[0]
        expected_hash = hashlib.sha256(b"mypassword").hexdigest()
        assert expected_hash in args
        assert "mypassword" not in args
