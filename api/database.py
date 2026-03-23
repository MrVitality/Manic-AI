"""Database pool management.

The pool is stored on ``app.state.db_pool`` at startup time and read from
there by the DI functions in ``dependencies.py``.  The legacy module-level
``db_pool`` reference and helper functions are retained for backward
compatibility with the health-logger background task and the DDL runner.
"""

import asyncpg
import logging
from typing import Optional
from fastapi import HTTPException
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((OSError, asyncpg.PostgresConnectionError)),
    reraise=True,
)
async def _create_pool(dsn: str) -> asyncpg.Pool:
    """Create the asyncpg connection pool with retry on transient failures."""
    return await asyncpg.create_pool(dsn, min_size=2, max_size=10, command_timeout=30)


async def init_pool(dsn: str, *, app=None):
    """Create the connection pool and optionally attach it to app.state."""
    pool = await _create_pool(dsn)
    # Store module reference for legacy callers
    _set_pool(pool)
    if app is not None:
        app.state.db_pool = pool
    return pool


def _set_pool(pool: Optional[asyncpg.Pool]):
    """Replace the module-level pool reference without ``global``."""
    import api.database as _mod
    _mod._pool = pool


async def close_pool(*, app=None):
    pool = _pool
    if app is not None:
        pool = getattr(app.state, "db_pool", pool)
    if pool:
        await pool.close()
    _set_pool(None)
    if app is not None:
        app.state.db_pool = None


async def get_db() -> asyncpg.Pool:
    if not _pool:
        raise HTTPException(status_code=503, detail="Database not connected")
    return _pool


def get_db_optional() -> Optional[asyncpg.Pool]:
    return _pool
