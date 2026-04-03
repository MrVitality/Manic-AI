"""Add key_expires_at to users and user_id FK to conversations.

Revision ID: 005_auth_enhancements
Revises: 004
"""
from alembic import op

revision = '005_auth_enhancements'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade():
    # Add key_expires_at to users table
    op.execute("""
        ALTER TABLE public.users
        ADD COLUMN IF NOT EXISTS key_expires_at TIMESTAMPTZ
        DEFAULT (NOW() + INTERVAL '90 days');
    """)

    # Add user_id FK column to conversations
    op.execute("""
        ALTER TABLE public.conversations
        ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES public.users(id);
    """)

    # Migrate existing user_id from metadata JSONB to the new column
    op.execute("""
        UPDATE public.conversations
        SET user_id = (metadata->>'user_id')::uuid
        WHERE metadata->>'user_id' IS NOT NULL
          AND user_id IS NULL;
    """)

    # Add index on user_id for fast lookups
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_conversations_user_id
        ON public.conversations(user_id);
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_conversations_user_id;")
    op.execute("ALTER TABLE public.conversations DROP COLUMN IF EXISTS user_id;")
    op.execute("ALTER TABLE public.users DROP COLUMN IF EXISTS key_expires_at;")
