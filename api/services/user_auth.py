"""User authentication service — foundation for multi-user support.

Currently the API uses a single shared API_SECRET_KEY. This module provides
the scaffolding for per-user authentication that can be enabled when ready.

Usage:
    Set AUTH_MODE=multi_user in .env to enable per-user auth.
    Default AUTH_MODE=single (current behavior, shared API key).
"""

import secrets
from typing import Any, Dict, Optional

import asyncpg
import bcrypt


def hash_password(password: str) -> str:
    """Hash a password using bcrypt (constant-time, salted)."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("ascii"))


async def create_user(
    db: asyncpg.Pool,
    email: str,
    password: str,
    username: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new user with bcrypt-hashed password and generated API key.

    Args:
        db: Database connection pool.
        email: User's email address (must be unique).
        password: Plaintext password — stored as bcrypt hash.
        username: Optional display name (must be unique if provided).

    Returns:
        Mapping with id, email, username, api_key, and created_at.

    Raises:
        asyncpg.UniqueViolationError: if email or username already exists.
    """
    password_hash = hash_password(password)
    api_key = f"manic_{secrets.token_urlsafe(32)}"

    async with db.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO public.users (email, username, password_hash, api_key)
            VALUES ($1, $2, $3, $4)
            RETURNING id::text, email, username, api_key, created_at
            """,
            email,
            username,
            password_hash,
            api_key,
        )
    return dict(row)


async def authenticate_by_api_key(
    db: asyncpg.Pool,
    api_key: str,
) -> Optional[Dict[str, Any]]:
    """Look up a user by API key.

    Args:
        db: Database connection pool.
        api_key: The bearer token issued at user creation.

    Returns:
        Mapping with id, email, username, is_admin, rate_limit_override,
        or None if the key is not found or the account is inactive.
    """
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id::text, email, username, is_admin, rate_limit_override
            FROM public.users
            WHERE api_key = $1 AND is_active = TRUE
            """,
            api_key,
        )
    return dict(row) if row else None


async def authenticate_by_email(
    db: asyncpg.Pool,
    email: str,
    password: str,
) -> Optional[Dict[str, Any]]:
    """Authenticate by email + password using bcrypt comparison.

    Args:
        db: Database connection pool.
        email: User's email address.
        password: Plaintext password to verify.

    Returns:
        Mapping with id, email, username, api_key, is_admin,
        or None if credentials are invalid or the account is inactive.
    """
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id::text, email, username, api_key, is_admin, password_hash
            FROM public.users
            WHERE email = $1 AND is_active = TRUE
            """,
            email,
        )
    if not row:
        return None
    if not verify_password(password, row["password_hash"]):
        return None
    result = dict(row)
    result.pop("password_hash", None)
    return result
