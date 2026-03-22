"""Add users table and per-user auth scaffolding.

Revision ID: 004
Revises: 003
Create Date: 2026-03-22
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS public.users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE,
            password_hash TEXT NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            is_admin BOOLEAN NOT NULL DEFAULT FALSE,
            api_key TEXT UNIQUE,
            rate_limit_override INTEGER,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX idx_users_email ON public.users (email)")
    op.execute("CREATE INDEX idx_users_api_key ON public.users (api_key)")

    # Add user_id FK to existing tables
    op.execute("ALTER TABLE public.chat_log ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES public.users(id)")
    op.execute("ALTER TABLE public.chat_feedback ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES public.users(id)")
    op.execute("ALTER TABLE public.search_log ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES public.users(id)")


def downgrade() -> None:
    op.execute("ALTER TABLE public.search_log DROP COLUMN IF EXISTS user_id")
    op.execute("ALTER TABLE public.chat_feedback DROP COLUMN IF EXISTS user_id")
    op.execute("ALTER TABLE public.chat_log DROP COLUMN IF EXISTS user_id")
    op.execute("DROP TABLE IF EXISTS public.users")
