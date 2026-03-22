"""Add chat feedback table for RAG evaluation signal.

Revision ID: 003
Revises: 002
Create Date: 2026-03-21
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS public.chat_feedback (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            chat_log_id UUID,
            conversation_id TEXT,
            message_id TEXT,
            rating INTEGER NOT NULL CHECK (rating IN (-1, 0, 1)),
            comment TEXT,
            query_text TEXT,
            response_text TEXT,
            had_rag BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_chat_feedback_created ON public.chat_feedback (created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_chat_feedback_rating ON public.chat_feedback (rating)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.chat_feedback")
