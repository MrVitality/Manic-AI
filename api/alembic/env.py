"""Alembic environment for Manic-AI FastAPI backend.

Supports both offline (SQL script generation) and online (live DB) modes.
Uses an async engine backed by asyncpg so it is compatible with the
application's asyncpg connection pool.

Usage (from repo root):
    alembic -c api/alembic.ini upgrade head
    alembic -c api/alembic.ini revision --autogenerate -m "describe change"
    alembic -c api/alembic.ini downgrade -1
"""

from __future__ import annotations

import asyncio
import os
import sys
from logging.config import fileConfig

from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ---------------------------------------------------------------------------
# Make the `api` package importable when alembic is run from the repo root.
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from api.config import settings  # noqa: E402  (import after sys.path patch)

# ---------------------------------------------------------------------------
# Alembic Config object — gives access to values in alembic.ini.
# ---------------------------------------------------------------------------
config = context.config

# Set up Python logging from the ini file.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Resolve the database URL from the application settings.
#
# asyncpg dialect string  ->  asyncpg-compatible SQLAlchemy URL
#   "postgresql+asyncpg://..."  stays as-is (used for the async engine)
#   "postgresql://..."          gets "+asyncpg" injected
#   "postgres://..."            gets normalised to "postgresql+asyncpg://..."
# ---------------------------------------------------------------------------
_raw_url: str = settings.SUPABASE_DB_URL or os.environ.get("SUPABASE_DB_URL", "")

if not _raw_url:
    raise RuntimeError(
        "SUPABASE_DB_URL is not set. "
        "Export it before running alembic, e.g.:\n"
        "  export SUPABASE_DB_URL=postgresql+asyncpg://user:pass@host:5432/db"
    )

# Normalise to the asyncpg dialect for the async engine.
_async_url = _raw_url
if _async_url.startswith("postgres://"):
    _async_url = "postgresql+asyncpg://" + _async_url[len("postgres://"):]
elif _async_url.startswith("postgresql://") and "+asyncpg" not in _async_url:
    _async_url = "postgresql+asyncpg://" + _async_url[len("postgresql://"):]

# Sync URL (plain psycopg2/psycopg-style) used only for offline mode.
_sync_url = _async_url.replace("postgresql+asyncpg://", "postgresql://")

config.set_main_option("sqlalchemy.url", _async_url)

# ---------------------------------------------------------------------------
# Target metadata — set to None because we manage DDL via raw SQL in
# migration scripts rather than SQLAlchemy ORM models.  Switch to
# Base.metadata here if you ever add declarative models.
# ---------------------------------------------------------------------------
target_metadata = None


# ---------------------------------------------------------------------------
# OFFLINE mode — emit SQL to stdout without connecting to the database.
# ---------------------------------------------------------------------------
def run_migrations_offline() -> None:
    """Generate SQL migration script without a live DB connection."""
    context.configure(
        url=_sync_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Include the custom search_path so schema-qualified DDL works.
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# ONLINE mode — connect with an async engine and run migrations.
# ---------------------------------------------------------------------------
def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations inside an async context."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        # Ensure the `rag` schema is visible for unqualified references.
        await connection.execute(text("SET search_path TO public, rag"))
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online migration mode."""
    asyncio.run(run_async_migrations())


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
