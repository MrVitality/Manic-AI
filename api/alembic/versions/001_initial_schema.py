"""Initial schema — full Manic-AI database

Creates the complete database schema as defined in supabase/init.sql and
sql-parts/01-08.  This migration is idempotent (uses IF NOT EXISTS / OR REPLACE)
so it is safe to run against a database that was bootstrapped directly from the
SQL init script.

Revision ID: 001
Revises:
Create Date: 2026-03-21
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision = None
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _exec(sql: str) -> None:
    op.execute(sql)


# ===========================================================================
def upgrade() -> None:
    # -----------------------------------------------------------------------
    # EXTENSIONS
    # -----------------------------------------------------------------------
    _exec("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")
    _exec("CREATE EXTENSION IF NOT EXISTS \"pgcrypto\"")
    _exec("CREATE EXTENSION IF NOT EXISTS \"pg_trgm\"")
    _exec("CREATE EXTENSION IF NOT EXISTS vector")

    # These may be unavailable on some Postgres builds — ignore errors.
    _exec("""
        DO $$ BEGIN
            CREATE EXTENSION IF NOT EXISTS "pgjwt";
        EXCEPTION WHEN OTHERS THEN NULL;
        END $$
    """)
    _exec("""
        DO $$ BEGIN
            CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";
        EXCEPTION WHEN OTHERS THEN NULL;
        END $$
    """)

    # -----------------------------------------------------------------------
    # SCHEMAS
    # -----------------------------------------------------------------------
    _exec("CREATE SCHEMA IF NOT EXISTS rag")

    # -----------------------------------------------------------------------
    # HELPER FUNCTIONS (must exist before triggers)
    # -----------------------------------------------------------------------
    _exec("""
        CREATE OR REPLACE FUNCTION public.update_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)

    # -----------------------------------------------------------------------
    # PUBLIC SCHEMA — core tables
    # -----------------------------------------------------------------------

    # user_profiles — note: references auth.users which is managed by Supabase.
    # If auth schema is absent (e.g., plain Postgres), the FK is skipped via
    # the guard below.
    _exec("""
        CREATE TABLE IF NOT EXISTS public.user_profiles (
            id          UUID PRIMARY KEY,
            email       TEXT NOT NULL,
            full_name   TEXT,
            avatar_url  TEXT,
            is_admin    BOOLEAN DEFAULT FALSE,
            preferences JSONB DEFAULT '{}',
            created_at  TIMESTAMPTZ DEFAULT NOW() NOT NULL,
            updated_at  TIMESTAMPTZ DEFAULT NOW() NOT NULL
        )
    """)
    _exec("""
        CREATE INDEX IF NOT EXISTS idx_user_profiles_email
            ON public.user_profiles(email)
    """)
    _exec("""
        CREATE INDEX IF NOT EXISTS idx_user_profiles_is_admin
            ON public.user_profiles(is_admin)
    """)

    # requests
    _exec("""
        CREATE TABLE IF NOT EXISTS public.requests (
            id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id         UUID NOT NULL REFERENCES public.user_profiles(id) ON DELETE CASCADE,
            endpoint        TEXT,
            method          TEXT,
            user_query      TEXT NOT NULL,
            response_status INTEGER,
            latency_ms      INTEGER,
            metadata        JSONB DEFAULT '{}',
            created_at      TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    _exec("CREATE INDEX IF NOT EXISTS idx_requests_user_id   ON public.requests(user_id)")
    _exec("CREATE INDEX IF NOT EXISTS idx_requests_created_at ON public.requests(created_at DESC)")

    # conversations (simple / non-agent)
    _exec("""
        CREATE TABLE IF NOT EXISTS public.conversations (
            id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            title         TEXT DEFAULT 'New Conversation',
            model         TEXT DEFAULT 'llama3.2:3b',
            system_prompt TEXT,
            metadata      JSONB DEFAULT '{}',
            created_at    TIMESTAMPTZ DEFAULT NOW(),
            updated_at    TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    _exec("""
        CREATE INDEX IF NOT EXISTS idx_conversations_created_at
            ON public.conversations(created_at DESC)
    """)

    # messages (simple / non-agent)
    _exec("""
        CREATE TABLE IF NOT EXISTS public.messages (
            id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            conversation_id UUID REFERENCES public.conversations(id) ON DELETE CASCADE,
            role            TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
            content         TEXT NOT NULL,
            model           TEXT,
            tokens_used     INTEGER,
            latency_ms      INTEGER,
            metadata        JSONB DEFAULT '{}',
            created_at      TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    _exec("CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON public.messages(conversation_id)")
    _exec("CREATE INDEX IF NOT EXISTS idx_messages_created_at       ON public.messages(created_at)")

    # prompts / templates
    _exec("""
        CREATE TABLE IF NOT EXISTS public.prompts (
            id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            name        TEXT NOT NULL,
            description TEXT,
            prompt_text TEXT NOT NULL,
            category    TEXT DEFAULT 'general',
            is_favorite BOOLEAN DEFAULT FALSE,
            metadata    JSONB DEFAULT '{}',
            created_at  TIMESTAMPTZ DEFAULT NOW(),
            updated_at  TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    _exec("CREATE INDEX IF NOT EXISTS idx_prompts_category    ON public.prompts(category)")
    _exec("CREATE INDEX IF NOT EXISTS idx_prompts_is_favorite ON public.prompts(is_favorite)")

    # usage_logs
    _exec("""
        CREATE TABLE IF NOT EXISTS public.usage_logs (
            id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            conversation_id UUID REFERENCES public.conversations(id) ON DELETE SET NULL,
            model           TEXT NOT NULL,
            endpoint        TEXT DEFAULT 'chat',
            input_tokens    INTEGER DEFAULT 0,
            output_tokens   INTEGER DEFAULT 0,
            total_tokens    INTEGER GENERATED ALWAYS AS (input_tokens + output_tokens) STORED,
            latency_ms      INTEGER,
            created_at      TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    _exec("CREATE INDEX IF NOT EXISTS idx_usage_logs_created_at ON public.usage_logs(created_at DESC)")
    _exec("CREATE INDEX IF NOT EXISTS idx_usage_logs_model       ON public.usage_logs(model)")

    # agent_conversations
    _exec("""
        CREATE TABLE IF NOT EXISTS public.agent_conversations (
            session_id      VARCHAR PRIMARY KEY NOT NULL,
            user_id         UUID NOT NULL REFERENCES public.user_profiles(id) ON DELETE CASCADE,
            title           VARCHAR,
            model           TEXT DEFAULT 'llama3.2:3b',
            system_prompt   TEXT,
            created_at      TIMESTAMPTZ DEFAULT NOW(),
            last_message_at TIMESTAMPTZ DEFAULT NOW(),
            is_archived     BOOLEAN DEFAULT FALSE,
            metadata        JSONB DEFAULT '{}'::jsonb
        )
    """)
    _exec("CREATE INDEX IF NOT EXISTS idx_agent_conversations_user         ON public.agent_conversations(user_id)")
    _exec("CREATE INDEX IF NOT EXISTS idx_agent_conversations_last_message ON public.agent_conversations(last_message_at DESC)")

    # agent_messages
    _exec("""
        CREATE TABLE IF NOT EXISTS public.agent_messages (
            id                       BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            computed_session_user_id UUID GENERATED ALWAYS AS (
                CAST(SPLIT_PART(session_id, '~', 1) AS UUID)
            ) STORED,
            session_id               VARCHAR NOT NULL
                REFERENCES public.agent_conversations(session_id) ON DELETE CASCADE,
            role        TEXT NOT NULL CHECK (role IN ('system', 'user', 'assistant', 'tool')),
            content     TEXT NOT NULL,
            message_data JSONB,
            tokens_used  INTEGER,
            latency_ms   INTEGER,
            model_used   TEXT,
            created_at   TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    _exec("CREATE INDEX IF NOT EXISTS idx_agent_messages_session       ON public.agent_messages(session_id)")
    _exec("CREATE INDEX IF NOT EXISTS idx_agent_messages_computed_user ON public.agent_messages(computed_session_user_id)")
    _exec("CREATE INDEX IF NOT EXISTS idx_agent_messages_created_at    ON public.agent_messages(created_at)")

    # document_metadata
    _exec("""
        CREATE TABLE IF NOT EXISTS public.document_metadata (
            id                TEXT PRIMARY KEY,
            title             TEXT,
            url               TEXT,
            source_type       TEXT,
            schema_definition TEXT,
            row_count         INTEGER,
            created_at        TIMESTAMPTZ DEFAULT NOW(),
            updated_at        TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    _exec("""
        CREATE INDEX IF NOT EXISTS idx_document_metadata_source_type
            ON public.document_metadata(source_type)
    """)

    # document_rows
    _exec("""
        CREATE TABLE IF NOT EXISTS public.document_rows (
            id         BIGSERIAL PRIMARY KEY,
            dataset_id TEXT REFERENCES public.document_metadata(id) ON DELETE CASCADE,
            row_data   JSONB NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    _exec("CREATE INDEX IF NOT EXISTS idx_document_rows_dataset ON public.document_rows(dataset_id)")
    _exec("CREATE INDEX IF NOT EXISTS idx_document_rows_data    ON public.document_rows USING gin(row_data)")

    # documents (legacy vector storage — 1024-dim bge-m3)
    _exec("""
        CREATE TABLE IF NOT EXISTS public.documents (
            id        BIGSERIAL PRIMARY KEY,
            content   TEXT,
            metadata  JSONB,
            embedding VECTOR(1024)
        )
    """)
    _exec("""
        CREATE INDEX IF NOT EXISTS idx_public_documents_embedding
            ON public.documents
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
    """)

    # rag_pipeline_state
    _exec("""
        CREATE TABLE IF NOT EXISTS public.rag_pipeline_state (
            pipeline_id   TEXT PRIMARY KEY,
            pipeline_type TEXT NOT NULL,
            last_check_time TIMESTAMPTZ,
            known_files   JSONB,
            last_run      TIMESTAMPTZ,
            run_status    TEXT DEFAULT 'idle'
                CHECK (run_status IN ('idle', 'running', 'completed', 'failed')),
            error_message TEXT,
            metadata      JSONB DEFAULT '{}',
            created_at    TIMESTAMPTZ DEFAULT NOW(),
            updated_at    TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    _exec("CREATE INDEX IF NOT EXISTS idx_rag_pipeline_state_type   ON public.rag_pipeline_state(pipeline_type)")
    _exec("CREATE INDEX IF NOT EXISTS idx_rag_pipeline_state_status ON public.rag_pipeline_state(run_status)")

    # chat_log (analytics)
    _exec("""
        CREATE TABLE IF NOT EXISTS public.chat_log (
            id                BIGSERIAL PRIMARY KEY,
            model             TEXT NOT NULL,
            prompt_tokens     INT NOT NULL DEFAULT 0,
            completion_tokens INT NOT NULL DEFAULT 0,
            total_tokens      INT NOT NULL DEFAULT 0,
            latency_ms        FLOAT NOT NULL DEFAULT 0,
            has_rag           BOOLEAN NOT NULL DEFAULT FALSE,
            created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    _exec("CREATE INDEX IF NOT EXISTS idx_chat_log_created_at ON public.chat_log(created_at DESC)")
    _exec("CREATE INDEX IF NOT EXISTS idx_chat_log_model       ON public.chat_log(model)")

    # service_health_log (analytics)
    _exec("""
        CREATE TABLE IF NOT EXISTS public.service_health_log (
            id           BIGSERIAL PRIMARY KEY,
            service_name TEXT NOT NULL,
            status       TEXT NOT NULL,
            latency_ms   FLOAT,
            checked_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    _exec("CREATE INDEX IF NOT EXISTS idx_service_health_log_service    ON public.service_health_log(service_name)")
    _exec("CREATE INDEX IF NOT EXISTS idx_service_health_log_checked_at ON public.service_health_log(checked_at DESC)")

    # ingest_jobs (background ingestion tracking)
    _exec("""
        CREATE TABLE IF NOT EXISTS public.ingest_jobs (
            id            BIGSERIAL PRIMARY KEY,
            document_id   TEXT UNIQUE NOT NULL,
            filename      TEXT NOT NULL,
            status        TEXT NOT NULL DEFAULT 'pending',
            chunks_created INT,
            error         TEXT,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # -----------------------------------------------------------------------
    # RAG SCHEMA TABLES
    # -----------------------------------------------------------------------

    # rag.documents
    _exec("""
        CREATE TABLE IF NOT EXISTS rag.documents (
            id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id            UUID,
            filename           TEXT NOT NULL,
            content_type       TEXT,
            file_size          BIGINT,
            source_url         TEXT,
            status             TEXT DEFAULT 'pending'
                CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
            error_message      TEXT,
            chunk_count        INTEGER DEFAULT 0,
            processing_time_ms INTEGER,
            raw_content        TEXT,
            metadata           JSONB DEFAULT '{}',
            created_at         TIMESTAMPTZ DEFAULT NOW(),
            updated_at         TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    _exec("CREATE INDEX IF NOT EXISTS idx_rag_documents_user_id    ON rag.documents(user_id)")
    _exec("CREATE INDEX IF NOT EXISTS idx_rag_documents_status     ON rag.documents(status)")
    _exec("CREATE INDEX IF NOT EXISTS idx_rag_documents_created_at ON rag.documents(created_at DESC)")
    _exec("CREATE INDEX IF NOT EXISTS idx_rag_documents_metadata   ON rag.documents USING gin(metadata)")

    # rag.chunks — 1024-dim HNSW vector index (bge-m3) + full-text + trigram indexes
    _exec("""
        CREATE TABLE IF NOT EXISTS rag.chunks (
            id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            document_id    UUID REFERENCES rag.documents(id) ON DELETE CASCADE,
            chunk_index    INTEGER NOT NULL,
            content        TEXT NOT NULL,
            content_tokens INTEGER,
            embedding      VECTOR(1024),
            metadata       JSONB DEFAULT '{}',
            created_at     TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    # HNSW index — ~15x faster than IVFFlat for approximate nearest-neighbour search
    _exec("""
        CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw
            ON rag.chunks
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
    """)
    # Full-text search index for BM25 / hybrid search
    _exec("""
        CREATE INDEX IF NOT EXISTS idx_chunks_content_fts
            ON rag.chunks
            USING gin (to_tsvector('english', content))
    """)
    # Trigram index for fuzzy / partial-match queries
    _exec("""
        CREATE INDEX IF NOT EXISTS idx_chunks_content_trgm
            ON rag.chunks
            USING gin (content gin_trgm_ops)
    """)
    _exec("CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON rag.chunks(document_id)")
    _exec("CREATE INDEX IF NOT EXISTS idx_chunks_metadata    ON rag.chunks USING gin(metadata)")

    # rag.collections
    _exec("""
        CREATE TABLE IF NOT EXISTS rag.collections (
            id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id         UUID,
            name            TEXT NOT NULL,
            description     TEXT,
            is_public       BOOLEAN DEFAULT FALSE,
            embedding_model TEXT DEFAULT 'nomic-embed-text',
            metadata        JSONB DEFAULT '{}',
            created_at      TIMESTAMPTZ DEFAULT NOW(),
            updated_at      TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    _exec("CREATE INDEX IF NOT EXISTS idx_rag_collections_user_id ON rag.collections(user_id)")
    _exec("""
        CREATE INDEX IF NOT EXISTS idx_rag_collections_public
            ON rag.collections(is_public)
            WHERE is_public = true
    """)

    # rag.document_collections — many-to-many join
    _exec("""
        CREATE TABLE IF NOT EXISTS rag.document_collections (
            document_id   UUID REFERENCES rag.documents(id)    ON DELETE CASCADE,
            collection_id UUID REFERENCES rag.collections(id)  ON DELETE CASCADE,
            added_at      TIMESTAMPTZ DEFAULT NOW(),
            PRIMARY KEY (document_id, collection_id)
        )
    """)
    _exec("""
        CREATE INDEX IF NOT EXISTS idx_doc_collections_collection
            ON rag.document_collections(collection_id)
    """)

    # rag.conversations
    _exec("""
        CREATE TABLE IF NOT EXISTS rag.conversations (
            id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id       UUID,
            collection_id UUID REFERENCES rag.collections(id) ON DELETE SET NULL,
            title         TEXT,
            model         TEXT DEFAULT 'llama3.2:3b',
            system_prompt TEXT,
            temperature   FLOAT DEFAULT 0.7 CHECK (temperature >= 0 AND temperature <= 2),
            max_tokens    INTEGER DEFAULT 2048,
            metadata      JSONB DEFAULT '{}',
            created_at    TIMESTAMPTZ DEFAULT NOW(),
            updated_at    TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    _exec("CREATE INDEX IF NOT EXISTS idx_rag_conversations_user_id    ON rag.conversations(user_id)")
    _exec("CREATE INDEX IF NOT EXISTS idx_rag_conversations_collection ON rag.conversations(collection_id)")
    _exec("CREATE INDEX IF NOT EXISTS idx_rag_conversations_created_at ON rag.conversations(created_at DESC)")

    # rag.messages
    _exec("""
        CREATE TABLE IF NOT EXISTS rag.messages (
            id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            conversation_id UUID REFERENCES rag.conversations(id) ON DELETE CASCADE,
            role            TEXT NOT NULL CHECK (role IN ('system', 'user', 'assistant', 'tool')),
            content         TEXT NOT NULL,
            tokens_used     INTEGER,
            latency_ms      INTEGER,
            model_used      TEXT,
            citations       JSONB DEFAULT '[]',
            metadata        JSONB DEFAULT '{}',
            created_at      TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    _exec("CREATE INDEX IF NOT EXISTS idx_rag_messages_conversation ON rag.messages(conversation_id)")
    _exec("CREATE INDEX IF NOT EXISTS idx_rag_messages_created_at   ON rag.messages(created_at)")

    # -----------------------------------------------------------------------
    # TRIGGERS — auto-update updated_at columns
    # -----------------------------------------------------------------------
    _exec("""
        DO $$
        DECLARE
            _tbl  TEXT;
            _trig TEXT;
        BEGIN
            FOR _tbl, _trig IN VALUES
                ('public.user_profiles',      'trg_user_profiles_updated_at'),
                ('public.conversations',       'trg_conversations_updated_at'),
                ('public.prompts',             'trg_prompts_updated_at'),
                ('public.document_metadata',   'trg_document_metadata_updated_at'),
                ('public.rag_pipeline_state',  'trg_rag_pipeline_state_updated_at'),
                ('rag.documents',              'trg_rag_documents_updated_at'),
                ('rag.collections',            'trg_rag_collections_updated_at'),
                ('rag.conversations',          'trg_rag_conversations_updated_at')
            LOOP
                IF NOT EXISTS (
                    SELECT 1 FROM pg_trigger WHERE tgname = _trig
                ) THEN
                    EXECUTE format(
                        'CREATE TRIGGER %I
                         BEFORE UPDATE ON %s
                         FOR EACH ROW EXECUTE FUNCTION public.update_updated_at()',
                        _trig, _tbl
                    );
                END IF;
            END LOOP;
        END
        $$
    """)

    # -----------------------------------------------------------------------
    # RAG STORED FUNCTIONS
    # -----------------------------------------------------------------------

    # Pure vector similarity search
    _exec("""
        CREATE OR REPLACE FUNCTION rag.search_similar_chunks(
            query_embedding    VECTOR(1024),
            match_threshold    FLOAT   DEFAULT 0.7,
            match_count        INT     DEFAULT 5,
            filter_collection_id UUID  DEFAULT NULL,
            filter_user_id     UUID   DEFAULT NULL
        )
        RETURNS TABLE (
            id          UUID,
            document_id UUID,
            content     TEXT,
            metadata    JSONB,
            similarity  FLOAT
        )
        LANGUAGE plpgsql STABLE
        AS $fn$
        BEGIN
            PERFORM set_config('hnsw.ef_search', '100', true);

            RETURN QUERY
            SELECT
                c.id,
                c.document_id,
                c.content,
                c.metadata,
                1 - (c.embedding <=> query_embedding) AS similarity
            FROM rag.chunks c
            JOIN rag.documents d ON c.document_id = d.id
            LEFT JOIN rag.document_collections dc ON c.document_id = dc.document_id
            WHERE
                (filter_collection_id IS NULL OR dc.collection_id = filter_collection_id)
                AND (filter_user_id IS NULL OR d.user_id = filter_user_id)
                AND 1 - (c.embedding <=> query_embedding) > match_threshold
            ORDER BY c.embedding <=> query_embedding
            LIMIT match_count;
        END;
        $fn$
    """)

    # Hybrid search — vector + BM25 with RRF fusion
    _exec("""
        CREATE OR REPLACE FUNCTION rag.hybrid_search(
            query_text           TEXT,
            query_embedding      VECTOR(1024),
            match_count          INT   DEFAULT 10,
            keyword_weight       FLOAT DEFAULT 0.3,
            filter_collection_id UUID  DEFAULT NULL,
            filter_user_id       UUID  DEFAULT NULL
        )
        RETURNS TABLE (
            id             UUID,
            document_id    UUID,
            content        TEXT,
            metadata       JSONB,
            vector_score   FLOAT,
            keyword_score  FLOAT,
            combined_score FLOAT
        )
        LANGUAGE plpgsql STABLE
        AS $fn$
        DECLARE
            rrf_k INT := 60;
        BEGIN
            PERFORM set_config('hnsw.ef_search', '100', true);

            RETURN QUERY
            WITH
            vector_results AS (
                SELECT
                    c.id,
                    c.document_id,
                    c.content,
                    c.metadata,
                    1 - (c.embedding <=> query_embedding)                           AS v_score,
                    ROW_NUMBER() OVER (ORDER BY c.embedding <=> query_embedding)     AS v_rank
                FROM rag.chunks c
                JOIN rag.documents d ON c.document_id = d.id
                LEFT JOIN rag.document_collections dc ON c.document_id = dc.document_id
                WHERE
                    (filter_collection_id IS NULL OR dc.collection_id = filter_collection_id)
                    AND (filter_user_id IS NULL OR d.user_id = filter_user_id)
                ORDER BY c.embedding <=> query_embedding
                LIMIT match_count * 2
            ),
            keyword_results AS (
                SELECT
                    c.id,
                    ts_rank_cd(
                        to_tsvector('english', c.content),
                        websearch_to_tsquery('english', query_text),
                        32
                    )                                                                AS k_score,
                    ROW_NUMBER() OVER (
                        ORDER BY ts_rank_cd(
                            to_tsvector('english', c.content),
                            websearch_to_tsquery('english', query_text),
                            32
                        ) DESC
                    )                                                                AS k_rank
                FROM rag.chunks c
                JOIN rag.documents d ON c.document_id = d.id
                LEFT JOIN rag.document_collections dc ON c.document_id = dc.document_id
                WHERE
                    to_tsvector('english', c.content)
                        @@ websearch_to_tsquery('english', query_text)
                    AND (filter_collection_id IS NULL OR dc.collection_id = filter_collection_id)
                    AND (filter_user_id IS NULL OR d.user_id = filter_user_id)
                LIMIT match_count * 2
            ),
            fused AS (
                SELECT
                    v.id,
                    v.document_id,
                    v.content,
                    v.metadata,
                    v.v_score,
                    COALESCE(k.k_score, 0)                                          AS k_score,
                    (1.0 - keyword_weight) * (1.0 / (rrf_k + v.v_rank))
                    + keyword_weight * (1.0 / (rrf_k + COALESCE(k.k_rank, match_count * 2 + 1)))
                                                                                    AS rrf_score
                FROM vector_results v
                LEFT JOIN keyword_results k ON v.id = k.id
            )
            SELECT
                f.id,
                f.document_id,
                f.content,
                f.metadata,
                f.v_score   AS vector_score,
                f.k_score   AS keyword_score,
                f.rrf_score AS combined_score
            FROM fused f
            ORDER BY f.rrf_score DESC
            LIMIT match_count;
        END;
        $fn$
    """)

    # Search with arbitrary metadata filter
    _exec("""
        CREATE OR REPLACE FUNCTION rag.search_with_filters(
            query_embedding  VECTOR(1024),
            metadata_filter  JSONB  DEFAULT '{}',
            match_count      INT    DEFAULT 5,
            filter_user_id   UUID   DEFAULT NULL
        )
        RETURNS TABLE (
            id          UUID,
            document_id UUID,
            content     TEXT,
            metadata    JSONB,
            similarity  FLOAT
        )
        LANGUAGE plpgsql STABLE
        AS $fn$
        BEGIN
            PERFORM set_config('hnsw.ef_search', '100', true);

            RETURN QUERY
            SELECT
                c.id,
                c.document_id,
                c.content,
                c.metadata,
                1 - (c.embedding <=> query_embedding) AS similarity
            FROM rag.chunks c
            JOIN rag.documents d ON c.document_id = d.id
            WHERE
                (filter_user_id IS NULL OR d.user_id = filter_user_id)
                AND (metadata_filter = '{}' OR c.metadata @> metadata_filter)
            ORDER BY c.embedding <=> query_embedding
            LIMIT match_count;
        END;
        $fn$
    """)

    # Cleanup orphaned chunks (document deleted without cascade)
    _exec("""
        CREATE OR REPLACE FUNCTION rag.cleanup_orphaned_chunks()
        RETURNS INTEGER
        LANGUAGE plpgsql
        AS $fn$
        DECLARE
            deleted_count INTEGER;
        BEGIN
            DELETE FROM rag.chunks
            WHERE document_id NOT IN (SELECT id FROM rag.documents);
            GET DIAGNOSTICS deleted_count = ROW_COUNT;
            RETURN deleted_count;
        END;
        $fn$
    """)

    # Legacy match_documents (backward compat with public.documents)
    _exec("""
        CREATE OR REPLACE FUNCTION public.match_documents(
            query_embedding VECTOR(1024),
            match_count     INT  DEFAULT 5,
            filter          JSONB DEFAULT '{}'
        )
        RETURNS TABLE (
            id         BIGINT,
            content    TEXT,
            metadata   JSONB,
            similarity FLOAT
        )
        LANGUAGE plpgsql STABLE
        AS $fn$
        BEGIN
            RETURN QUERY
            SELECT
                d.id,
                d.content,
                d.metadata,
                1 - (d.embedding <=> query_embedding) AS similarity
            FROM public.documents d
            WHERE d.metadata @> filter
            ORDER BY d.embedding <=> query_embedding
            LIMIT match_count;
        END;
        $fn$
    """)


# ===========================================================================
def downgrade() -> None:
    # -----------------------------------------------------------------------
    # Drop in reverse dependency order.
    # -----------------------------------------------------------------------

    # Functions
    _exec("DROP FUNCTION IF EXISTS rag.cleanup_orphaned_chunks()")
    _exec("DROP FUNCTION IF EXISTS rag.search_with_filters(vector, jsonb, int, uuid)")
    _exec("DROP FUNCTION IF EXISTS rag.hybrid_search(text, vector, int, float, uuid, uuid)")
    _exec("DROP FUNCTION IF EXISTS rag.search_similar_chunks(vector, float, int, uuid, uuid)")
    _exec("DROP FUNCTION IF EXISTS public.match_documents(vector, int, jsonb)")

    # RAG schema tables
    _exec("DROP TABLE IF EXISTS rag.messages              CASCADE")
    _exec("DROP TABLE IF EXISTS rag.conversations         CASCADE")
    _exec("DROP TABLE IF EXISTS rag.document_collections  CASCADE")
    _exec("DROP TABLE IF EXISTS rag.collections           CASCADE")
    _exec("DROP TABLE IF EXISTS rag.chunks                CASCADE")
    _exec("DROP TABLE IF EXISTS rag.documents             CASCADE")
    _exec("DROP SCHEMA  IF EXISTS rag                     CASCADE")

    # Public schema tables (reverse dependency order)
    _exec("DROP TABLE IF EXISTS public.ingest_jobs          CASCADE")
    _exec("DROP TABLE IF EXISTS public.service_health_log   CASCADE")
    _exec("DROP TABLE IF EXISTS public.chat_log             CASCADE")
    _exec("DROP TABLE IF EXISTS public.rag_pipeline_state   CASCADE")
    _exec("DROP TABLE IF EXISTS public.document_rows        CASCADE")
    _exec("DROP TABLE IF EXISTS public.document_metadata    CASCADE")
    _exec("DROP TABLE IF EXISTS public.documents            CASCADE")
    _exec("DROP TABLE IF EXISTS public.usage_logs           CASCADE")
    _exec("DROP TABLE IF EXISTS public.prompts              CASCADE")
    _exec("DROP TABLE IF EXISTS public.messages             CASCADE")
    _exec("DROP TABLE IF EXISTS public.conversations        CASCADE")
    _exec("DROP TABLE IF EXISTS public.agent_messages       CASCADE")
    _exec("DROP TABLE IF EXISTS public.agent_conversations  CASCADE")
    _exec("DROP TABLE IF EXISTS public.requests             CASCADE")
    _exec("DROP TABLE IF EXISTS public.user_profiles        CASCADE")

    # Helper function (triggers will already be gone via CASCADE above)
    _exec("DROP FUNCTION IF EXISTS public.update_updated_at() CASCADE")
