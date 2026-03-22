"""Admin service — user management and system statistics.

All functions accept an asyncpg connection pool and return plain dicts
so the router layer can serialise them directly via the envelope helpers.
"""

from typing import Any, Dict, List, Optional

import asyncpg


async def list_users(
    db: asyncpg.Pool,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """Return a paginated list of users with total count.

    Args:
        db: Database connection pool.
        limit: Maximum number of users to return (1–200).
        offset: Number of rows to skip.

    Returns:
        Mapping with ``users`` list and ``total`` count.
    """
    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                id::text,
                email,
                username,
                is_active,
                is_admin,
                -- Mask the API key: show only the first 12 chars
                LEFT(api_key, 12) || '...' AS api_key_masked,
                rate_limit_override,
                created_at,
                updated_at
            FROM public.users
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
        )
        total = await conn.fetchval("SELECT COUNT(*) FROM public.users")

    return {
        "users": [dict(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


async def get_user(db: asyncpg.Pool, user_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a single user by UUID.

    Args:
        db: Database connection pool.
        user_id: UUID string of the target user.

    Returns:
        User mapping or None if not found.
    """
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                id::text,
                email,
                username,
                is_active,
                is_admin,
                LEFT(api_key, 12) || '...' AS api_key_masked,
                rate_limit_override,
                created_at,
                updated_at
            FROM public.users
            WHERE id = $1::uuid
            """,
            user_id,
        )
    return dict(row) if row else None


async def update_user(
    db: asyncpg.Pool,
    user_id: str,
    *,
    is_active: Optional[bool] = None,
    is_admin: Optional[bool] = None,
    rate_limit_override: Optional[int] = None,
    username: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Partially update a user's mutable fields.

    Only the fields explicitly passed (non-None) are written. Returns the
    updated user mapping or None if the user was not found.

    Args:
        db: Database connection pool.
        user_id: UUID string of the target user.
        is_active: Override the account active flag.
        is_admin: Override the admin flag.
        rate_limit_override: Custom per-user rate limit (requests/min).
        username: New display name.

    Returns:
        Updated user mapping or None.
    """
    set_clauses: List[str] = []
    values: List[Any] = []
    idx = 1

    if is_active is not None:
        set_clauses.append(f"is_active = ${idx}")
        values.append(is_active)
        idx += 1

    if is_admin is not None:
        set_clauses.append(f"is_admin = ${idx}")
        values.append(is_admin)
        idx += 1

    if rate_limit_override is not None:
        set_clauses.append(f"rate_limit_override = ${idx}")
        values.append(rate_limit_override)
        idx += 1

    if username is not None:
        set_clauses.append(f"username = ${idx}")
        values.append(username)
        idx += 1

    if not set_clauses:
        # Nothing to update — fetch and return current state
        return await get_user(db, user_id)

    set_clauses.append("updated_at = NOW()")
    values.append(user_id)

    query = f"""
        UPDATE public.users
        SET {', '.join(set_clauses)}
        WHERE id = ${idx}::uuid
        RETURNING
            id::text,
            email,
            username,
            is_active,
            is_admin,
            LEFT(api_key, 12) || '...' AS api_key_masked,
            rate_limit_override,
            created_at,
            updated_at
    """

    async with db.acquire() as conn:
        row = await conn.fetchrow(query, *values)
    return dict(row) if row else None


async def deactivate_user(db: asyncpg.Pool, user_id: str) -> bool:
    """Soft-delete a user by setting is_active = FALSE.

    Args:
        db: Database connection pool.
        user_id: UUID string of the target user.

    Returns:
        True if a row was updated, False if the user was not found.
    """
    async with db.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE public.users
            SET is_active = FALSE, updated_at = NOW()
            WHERE id = $1::uuid
            """,
            user_id,
        )
    # asyncpg returns e.g. "UPDATE 1" or "UPDATE 0"
    return result == "UPDATE 1"


async def get_system_stats(db: asyncpg.Pool) -> Dict[str, Any]:
    """Aggregate system-wide statistics in a single DB round trip.

    Args:
        db: Database connection pool.

    Returns:
        Mapping with total_users, active_users, admin_users,
        total_chats, total_searches, total_feedback.
    """
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            """
            WITH user_counts AS (
                SELECT
                    COUNT(*)                           AS total_users,
                    COUNT(*) FILTER (WHERE is_active)  AS active_users,
                    COUNT(*) FILTER (WHERE is_admin)   AS admin_users
                FROM public.users
            ),
            existing_tables AS (
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name IN ('chat_messages', 'search_logs', 'feedback')
            ),
            chat_count AS (
                SELECT CASE
                    WHEN EXISTS (SELECT 1 FROM existing_tables WHERE table_name = 'chat_messages')
                    THEN (SELECT COUNT(*) FROM public.chat_messages)
                    ELSE 0
                END AS total_chats
            ),
            search_count AS (
                SELECT CASE
                    WHEN EXISTS (SELECT 1 FROM existing_tables WHERE table_name = 'search_logs')
                    THEN (SELECT COUNT(*) FROM public.search_logs)
                    ELSE 0
                END AS total_searches
            ),
            feedback_count AS (
                SELECT CASE
                    WHEN EXISTS (SELECT 1 FROM existing_tables WHERE table_name = 'feedback')
                    THEN (SELECT COUNT(*) FROM public.feedback)
                    ELSE 0
                END AS total_feedback
            )
            SELECT
                u.total_users, u.active_users, u.admin_users,
                c.total_chats, s.total_searches, f.total_feedback
            FROM user_counts u, chat_count c, search_count s, feedback_count f
            """
        )

    return {
        "total_users": row["total_users"],
        "active_users": row["active_users"],
        "admin_users": row["admin_users"],
        "total_chats": row["total_chats"],
        "total_searches": row["total_searches"],
        "total_feedback": row["total_feedback"],
    }
