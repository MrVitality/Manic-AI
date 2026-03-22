"""Add search logging tables for RAG evaluation.

Revision ID: 002
Revises: 001
Create Date: 2026-03-21
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Search event log — one row per search request
    op.execute("""
        CREATE TABLE IF NOT EXISTS public.search_log (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            query TEXT NOT NULL,
            backend TEXT NOT NULL DEFAULT 'supabase',
            use_hybrid BOOLEAN NOT NULL DEFAULT TRUE,
            top_k INTEGER NOT NULL DEFAULT 5,
            threshold FLOAT NOT NULL DEFAULT 0.7,
            keyword_weight FLOAT NOT NULL DEFAULT 0.3,
            reranked BOOLEAN NOT NULL DEFAULT FALSE,
            result_count INTEGER NOT NULL DEFAULT 0,
            avg_score FLOAT,
            max_score FLOAT,
            latency_ms FLOAT,
            collection_id UUID,
            user_id UUID,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_search_log_created_at
        ON public.search_log (created_at DESC)
    """)

    # Per-result detail log — one row per returned chunk per search
    op.execute("""
        CREATE TABLE IF NOT EXISTS public.search_result_log (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            search_log_id UUID NOT NULL REFERENCES public.search_log(id) ON DELETE CASCADE,
            chunk_id TEXT NOT NULL,
            retrieval_rank INTEGER NOT NULL,
            vector_score FLOAT,
            keyword_score FLOAT,
            combined_score FLOAT,
            rerank_score FLOAT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_search_result_log_search_id
        ON public.search_result_log (search_log_id)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.search_result_log")
    op.execute("DROP TABLE IF EXISTS public.search_log")
