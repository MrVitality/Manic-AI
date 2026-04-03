"""MFA columns, API key hashing, audit log, and active sessions tables.

Revision ID: 006_mfa_and_audit
Revises: 005_auth_enhancements
"""

from alembic import op

revision = '006_mfa_and_audit'
down_revision = '005_auth_enhancements'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # MFA columns
    op.execute("ALTER TABLE public.users ADD COLUMN IF NOT EXISTS totp_secret TEXT;")
    op.execute("ALTER TABLE public.users ADD COLUMN IF NOT EXISTS mfa_enabled BOOLEAN DEFAULT FALSE;")

    # API key hashing (store hash, keep prefix for display)
    op.execute("ALTER TABLE public.users ADD COLUMN IF NOT EXISTS api_key_hash TEXT;")
    op.execute("ALTER TABLE public.users ADD COLUMN IF NOT EXISTS api_key_prefix VARCHAR(16);")

    # Audit log table
    op.execute("""
        CREATE TABLE IF NOT EXISTS public.api_key_usage_log (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID REFERENCES public.users(id),
            api_key_prefix VARCHAR(16),
            endpoint TEXT,
            method VARCHAR(10),
            ip_address INET,
            user_agent TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_usage_log_user_id ON public.api_key_usage_log(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_usage_log_created_at ON public.api_key_usage_log(created_at)")

    # Active sessions table
    op.execute("""
        CREATE TABLE IF NOT EXISTS public.user_sessions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID REFERENCES public.users(id),
            api_key_prefix VARCHAR(16),
            ip_address INET,
            user_agent TEXT,
            last_active_at TIMESTAMPTZ DEFAULT NOW(),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            is_active BOOLEAN DEFAULT TRUE
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON public.user_sessions(user_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.user_sessions;")
    op.execute("DROP TABLE IF EXISTS public.api_key_usage_log;")
    op.execute("ALTER TABLE public.users DROP COLUMN IF EXISTS api_key_prefix;")
    op.execute("ALTER TABLE public.users DROP COLUMN IF EXISTS api_key_hash;")
    op.execute("ALTER TABLE public.users DROP COLUMN IF EXISTS mfa_enabled;")
    op.execute("ALTER TABLE public.users DROP COLUMN IF EXISTS totp_secret;")
