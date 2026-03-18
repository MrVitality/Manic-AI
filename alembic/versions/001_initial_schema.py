"""Initial schema — chat_log, service_health_log, ingest_jobs

Revision ID: 001
Revises:
Create Date: 2026-03-18
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS public.chat_log (
            id BIGSERIAL PRIMARY KEY,
            model TEXT NOT NULL,
            prompt_tokens INT NOT NULL DEFAULT 0,
            completion_tokens INT NOT NULL DEFAULT 0,
            total_tokens INT NOT NULL DEFAULT 0,
            latency_ms FLOAT NOT NULL DEFAULT 0,
            has_rag BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS public.service_health_log (
            id BIGSERIAL PRIMARY KEY,
            service_name TEXT NOT NULL,
            status TEXT NOT NULL,
            latency_ms FLOAT,
            checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS public.ingest_jobs (
            id BIGSERIAL PRIMARY KEY,
            document_id TEXT UNIQUE NOT NULL,
            filename TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            chunks_created INT,
            error TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.ingest_jobs")
    op.execute("DROP TABLE IF EXISTS public.service_health_log")
    op.execute("DROP TABLE IF EXISTS public.chat_log")
