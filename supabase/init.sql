-- =============================================================================
-- Manic AI - Canonical Database Schema
-- =============================================================================
-- This is the SINGLE SOURCE OF TRUTH for the database schema.
-- Mounted as Docker entrypoint init script.
--
-- Consolidated from:
--   - supabase/migrations/complete_schema.sql (conversations, prompts, usage)
--   - sql-parts/01-08 (user profiles, agents, documents, RLS policies)
--   - api/app.py inline DDL (chat_log, service_health_log)
--
-- Last consolidated: 2026-03-17
-- =============================================================================

-- ========================
-- EXTENSIONS
-- ========================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS vector;

DO $$ BEGIN CREATE EXTENSION IF NOT EXISTS "pgjwt"; EXCEPTION WHEN OTHERS THEN NULL; END $$;
DO $$ BEGIN CREATE EXTENSION IF NOT EXISTS "pg_stat_statements"; EXCEPTION WHEN OTHERS THEN NULL; END $$;

-- ========================
-- SCHEMAS
-- ========================
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS storage;
CREATE SCHEMA IF NOT EXISTS rag;

-- ========================
-- ROLES
-- ========================
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'anon') THEN
        CREATE ROLE anon NOLOGIN NOINHERIT;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'authenticated') THEN
        CREATE ROLE authenticated NOLOGIN NOINHERIT;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'service_role') THEN
        CREATE ROLE service_role NOLOGIN NOINHERIT BYPASSRLS;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'authenticator') THEN
        -- SECURITY: Password is read from current_setting('app.authenticator_password') if set,
        -- otherwise falls back to the literal below. After init you MUST run:
        --   ALTER ROLE authenticator PASSWORD '<strong-random-secret>';
        -- or set the GUC before running this script.
        CREATE ROLE authenticator NOINHERIT LOGIN PASSWORD
            COALESCE(current_setting('app.authenticator_password', true),
                     'change-me-immediately-' || gen_random_uuid()::text);
    END IF;
END
$$;

GRANT anon TO authenticator;
GRANT authenticated TO authenticator;
GRANT service_role TO authenticator;

GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
GRANT USAGE ON SCHEMA rag TO anon, authenticated, service_role;

-- =============================================================================
-- HELPER FUNCTIONS (must exist before triggers)
-- =============================================================================

-- Update timestamp trigger function
CREATE OR REPLACE FUNCTION public.update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Handle new user signup (auto-create profile)
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.user_profiles (id, email, full_name, avatar_url)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.raw_user_meta_data->>'name'),
        NEW.raw_user_meta_data->>'avatar_url'
    );
    RETURN NEW;
EXCEPTION WHEN unique_violation THEN
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Check if current user is admin
CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS BOOLEAN AS $$
DECLARE
    admin_status BOOLEAN;
BEGIN
    SELECT COALESCE(is_admin, FALSE) INTO admin_status
    FROM public.user_profiles
    WHERE id = auth.uid();

    RETURN COALESCE(admin_status, FALSE);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER STABLE;

-- =============================================================================
-- PUBLIC SCHEMA TABLES
-- =============================================================================

-- -----------------------------------------------------------------------------
-- User Profiles
-- (from sql-parts/02)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    full_name TEXT,
    avatar_url TEXT,
    is_admin BOOLEAN DEFAULT FALSE,
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_user_profiles_email ON public.user_profiles(email);
CREATE INDEX IF NOT EXISTS idx_user_profiles_is_admin ON public.user_profiles(is_admin);

-- -----------------------------------------------------------------------------
-- Requests
-- (from sql-parts/02)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.user_profiles(id) ON DELETE CASCADE,
    endpoint TEXT,
    method TEXT,
    user_query TEXT NOT NULL,
    response_status INTEGER,
    latency_ms INTEGER,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_requests_user_id ON public.requests(user_id);
CREATE INDEX IF NOT EXISTS idx_requests_created_at ON public.requests(created_at DESC);

-- -----------------------------------------------------------------------------
-- Agent Conversations
-- (from sql-parts/02)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.agent_conversations (
    session_id VARCHAR PRIMARY KEY NOT NULL,
    user_id UUID NOT NULL REFERENCES public.user_profiles(id) ON DELETE CASCADE,
    title VARCHAR,
    model TEXT DEFAULT 'llama3.2:3b',
    system_prompt TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_message_at TIMESTAMPTZ DEFAULT NOW(),
    is_archived BOOLEAN DEFAULT FALSE,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_agent_conversations_user ON public.agent_conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_agent_conversations_last_message ON public.agent_conversations(last_message_at DESC);

-- -----------------------------------------------------------------------------
-- Agent Messages
-- (from sql-parts/02)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.agent_messages (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    computed_session_user_id UUID GENERATED ALWAYS AS (
        CAST(SPLIT_PART(session_id, '~', 1) AS UUID)
    ) STORED,
    session_id VARCHAR NOT NULL REFERENCES public.agent_conversations(session_id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('system', 'user', 'assistant', 'tool')),
    content TEXT NOT NULL,
    message_data JSONB,
    tokens_used INTEGER,
    latency_ms INTEGER,
    model_used TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_messages_session ON public.agent_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_agent_messages_computed_user ON public.agent_messages(computed_session_user_id);
CREATE INDEX IF NOT EXISTS idx_agent_messages_created_at ON public.agent_messages(created_at);

-- -----------------------------------------------------------------------------
-- Conversations (simple/non-agent)
-- (from complete_schema.sql)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT DEFAULT 'New Conversation',
    model TEXT DEFAULT 'llama3.2:3b',
    system_prompt TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON public.conversations(created_at DESC);

-- -----------------------------------------------------------------------------
-- Messages (simple/non-agent)
-- (from complete_schema.sql)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID REFERENCES public.conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    model TEXT,
    tokens_used INTEGER,
    latency_ms INTEGER,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON public.messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON public.messages(created_at);

-- -----------------------------------------------------------------------------
-- Prompts / Templates
-- (from complete_schema.sql)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.prompts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    description TEXT,
    prompt_text TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    is_favorite BOOLEAN DEFAULT FALSE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prompts_category ON public.prompts(category);
CREATE INDEX IF NOT EXISTS idx_prompts_is_favorite ON public.prompts(is_favorite);

-- -----------------------------------------------------------------------------
-- Usage Logs
-- (from complete_schema.sql)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.usage_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID REFERENCES public.conversations(id) ON DELETE SET NULL,
    model TEXT NOT NULL,
    endpoint TEXT DEFAULT 'chat',
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER GENERATED ALWAYS AS (input_tokens + output_tokens) STORED,
    latency_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_usage_logs_created_at ON public.usage_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_usage_logs_model ON public.usage_logs(model);

-- -----------------------------------------------------------------------------
-- Document Metadata
-- (from sql-parts/02)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.document_metadata (
    id TEXT PRIMARY KEY,
    title TEXT,
    url TEXT,
    source_type TEXT,
    schema_definition TEXT,
    row_count INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_document_metadata_source_type ON public.document_metadata(source_type);

-- -----------------------------------------------------------------------------
-- Document Rows
-- (from sql-parts/02)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.document_rows (
    id BIGSERIAL PRIMARY KEY,
    dataset_id TEXT REFERENCES public.document_metadata(id) ON DELETE CASCADE,
    row_data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_document_rows_dataset ON public.document_rows(dataset_id);
CREATE INDEX IF NOT EXISTS idx_document_rows_data ON public.document_rows USING gin(row_data);

-- -----------------------------------------------------------------------------
-- Documents (Legacy vector storage)
-- (from sql-parts/02)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.documents (
    id BIGSERIAL PRIMARY KEY,
    content TEXT,
    metadata JSONB,
    embedding VECTOR(1024)
);

CREATE INDEX IF NOT EXISTS idx_public_documents_embedding ON public.documents
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

-- -----------------------------------------------------------------------------
-- RAG Pipeline State
-- (from sql-parts/02)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.rag_pipeline_state (
    pipeline_id TEXT PRIMARY KEY,
    pipeline_type TEXT NOT NULL,
    last_check_time TIMESTAMPTZ,
    known_files JSONB,
    last_run TIMESTAMPTZ,
    run_status TEXT DEFAULT 'idle' CHECK (run_status IN ('idle', 'running', 'completed', 'failed')),
    error_message TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rag_pipeline_state_type ON public.rag_pipeline_state(pipeline_type);
CREATE INDEX IF NOT EXISTS idx_rag_pipeline_state_status ON public.rag_pipeline_state(run_status);

-- -----------------------------------------------------------------------------
-- Chat Log (analytics)
-- (from api/app.py inline DDL)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.chat_log (
    id BIGSERIAL PRIMARY KEY,
    model TEXT NOT NULL,
    prompt_tokens INT NOT NULL DEFAULT 0,
    completion_tokens INT NOT NULL DEFAULT 0,
    total_tokens INT NOT NULL DEFAULT 0,
    latency_ms FLOAT NOT NULL DEFAULT 0,
    has_rag BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_log_created_at ON public.chat_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_log_model ON public.chat_log(model);

-- -----------------------------------------------------------------------------
-- Service Health Log (analytics)
-- (from api/app.py inline DDL)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.service_health_log (
    id BIGSERIAL PRIMARY KEY,
    service_name TEXT NOT NULL,
    status TEXT NOT NULL,
    latency_ms FLOAT,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_service_health_log_service ON public.service_health_log(service_name);
CREATE INDEX IF NOT EXISTS idx_service_health_log_checked_at ON public.service_health_log(checked_at DESC);

-- =============================================================================
-- RAG SCHEMA TABLES
-- =============================================================================

-- -----------------------------------------------------------------------------
-- RAG Documents
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS rag.documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID,
    filename TEXT NOT NULL,
    content_type TEXT,
    file_size BIGINT,
    source_url TEXT,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    error_message TEXT,
    chunk_count INTEGER DEFAULT 0,
    processing_time_ms INTEGER,
    raw_content TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON COLUMN rag.documents.raw_content IS 'Full original document text stored at ingestion time';

CREATE INDEX IF NOT EXISTS idx_rag_documents_user_id ON rag.documents(user_id);
CREATE INDEX IF NOT EXISTS idx_rag_documents_status ON rag.documents(status);
CREATE INDEX IF NOT EXISTS idx_rag_documents_created_at ON rag.documents(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_rag_documents_metadata ON rag.documents USING gin(metadata);

-- -----------------------------------------------------------------------------
-- RAG Chunks (1024-dim vectors for bge-m3)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS rag.chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID REFERENCES rag.documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    content_tokens INTEGER,
    embedding VECTOR(1024),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw ON rag.chunks
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_chunks_content_fts ON rag.chunks
    USING gin (to_tsvector('english', content));

CREATE INDEX IF NOT EXISTS idx_chunks_content_trgm ON rag.chunks
    USING gin (content gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON rag.chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_metadata ON rag.chunks USING gin(metadata);

-- -----------------------------------------------------------------------------
-- RAG Collections
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS rag.collections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID,
    name TEXT NOT NULL,
    description TEXT,
    is_public BOOLEAN DEFAULT FALSE,
    embedding_model TEXT DEFAULT 'nomic-embed-text',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rag_collections_user_id ON rag.collections(user_id);
CREATE INDEX IF NOT EXISTS idx_rag_collections_public ON rag.collections(is_public) WHERE is_public = true;

-- -----------------------------------------------------------------------------
-- Document-Collection Mapping (many-to-many)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS rag.document_collections (
    document_id UUID REFERENCES rag.documents(id) ON DELETE CASCADE,
    collection_id UUID REFERENCES rag.collections(id) ON DELETE CASCADE,
    added_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (document_id, collection_id)
);

CREATE INDEX IF NOT EXISTS idx_doc_collections_collection ON rag.document_collections(collection_id);

-- -----------------------------------------------------------------------------
-- RAG Conversations
-- (from sql-parts/03)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS rag.conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID,
    collection_id UUID REFERENCES rag.collections(id) ON DELETE SET NULL,
    title TEXT,
    model TEXT DEFAULT 'llama3.2:3b',
    system_prompt TEXT,
    temperature FLOAT DEFAULT 0.7 CHECK (temperature >= 0 AND temperature <= 2),
    max_tokens INTEGER DEFAULT 2048,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rag_conversations_user_id ON rag.conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_rag_conversations_collection ON rag.conversations(collection_id);
CREATE INDEX IF NOT EXISTS idx_rag_conversations_created_at ON rag.conversations(created_at DESC);

-- -----------------------------------------------------------------------------
-- RAG Messages
-- (from sql-parts/03)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS rag.messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID REFERENCES rag.conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('system', 'user', 'assistant', 'tool')),
    content TEXT NOT NULL,
    tokens_used INTEGER,
    latency_ms INTEGER,
    model_used TEXT,
    citations JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rag_messages_conversation ON rag.messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_rag_messages_created_at ON rag.messages(created_at);

-- =============================================================================
-- TRIGGERS
-- =============================================================================

-- Auto-create user profile on auth signup
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'on_auth_user_created') THEN
        CREATE TRIGGER on_auth_user_created
            AFTER INSERT ON auth.users
            FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();
    END IF;
END
$$;

-- Auto-update timestamps
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_user_profiles_updated_at') THEN
        CREATE TRIGGER trg_user_profiles_updated_at
            BEFORE UPDATE ON public.user_profiles
            FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_conversations_updated_at') THEN
        CREATE TRIGGER trg_conversations_updated_at
            BEFORE UPDATE ON public.conversations
            FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_prompts_updated_at') THEN
        CREATE TRIGGER trg_prompts_updated_at
            BEFORE UPDATE ON public.prompts
            FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_document_metadata_updated_at') THEN
        CREATE TRIGGER trg_document_metadata_updated_at
            BEFORE UPDATE ON public.document_metadata
            FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_rag_pipeline_state_updated_at') THEN
        CREATE TRIGGER trg_rag_pipeline_state_updated_at
            BEFORE UPDATE ON public.rag_pipeline_state
            FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_documents_updated_at') THEN
        CREATE TRIGGER trg_documents_updated_at
            BEFORE UPDATE ON rag.documents
            FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_collections_updated_at') THEN
        CREATE TRIGGER trg_collections_updated_at
            BEFORE UPDATE ON rag.collections
            FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_rag_conversations_updated_at') THEN
        CREATE TRIGGER trg_rag_conversations_updated_at
            BEFORE UPDATE ON rag.conversations
            FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();
    END IF;
END
$$;

-- =============================================================================
-- FUNCTIONS
-- =============================================================================

-- Legacy: Match documents (backward compatibility with public.documents)
CREATE OR REPLACE FUNCTION public.match_documents(
    query_embedding VECTOR(1024),
    match_count INT DEFAULT 5,
    filter JSONB DEFAULT '{}'
)
RETURNS TABLE (
    id BIGINT,
    content TEXT,
    metadata JSONB,
    similarity FLOAT
)
LANGUAGE plpgsql STABLE
AS $$
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
$$;

-- execute_custom_sql was removed: dynamic EXECUTE with string concatenation is
-- architecturally unsound and cannot be made safe regardless of input checks.
-- Callers should use parameterised queries or dedicated typed functions instead.

-- Get conversation with all messages
CREATE OR REPLACE FUNCTION get_conversation_with_messages(conv_id UUID)
RETURNS TABLE (
    conversation_id UUID,
    title TEXT,
    model TEXT,
    system_prompt TEXT,
    messages JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        c.title,
        c.model,
        c.system_prompt,
        COALESCE(
            jsonb_agg(
                jsonb_build_object(
                    'id', m.id,
                    'role', m.role,
                    'content', m.content,
                    'created_at', m.created_at
                ) ORDER BY m.created_at
            ) FILTER (WHERE m.id IS NOT NULL),
            '[]'::jsonb
        ) as messages
    FROM public.conversations c
    LEFT JOIN public.messages m ON c.id = m.conversation_id
    WHERE c.id = conv_id
    GROUP BY c.id;
END;
$$ LANGUAGE plpgsql;

-- Get usage statistics
CREATE OR REPLACE FUNCTION get_usage_stats(days_back INTEGER DEFAULT 30)
RETURNS TABLE (
    total_conversations BIGINT,
    total_messages BIGINT,
    total_tokens BIGINT,
    avg_latency_ms NUMERIC,
    top_model TEXT,
    date_range TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        (SELECT COUNT(*) FROM public.conversations WHERE created_at > NOW() - (days_back || ' days')::INTERVAL),
        (SELECT COUNT(*) FROM public.messages WHERE created_at > NOW() - (days_back || ' days')::INTERVAL),
        (SELECT COALESCE(SUM(u.total_tokens), 0) FROM public.usage_logs u WHERE created_at > NOW() - (days_back || ' days')::INTERVAL),
        (SELECT ROUND(AVG(latency_ms), 1) FROM public.usage_logs WHERE created_at > NOW() - (days_back || ' days')::INTERVAL),
        (SELECT model FROM public.usage_logs WHERE created_at > NOW() - (days_back || ' days')::INTERVAL GROUP BY model ORDER BY COUNT(*) DESC LIMIT 1),
        ('Last ' || days_back || ' days')::TEXT;
END;
$$ LANGUAGE plpgsql;

-- Get RAG stats
CREATE OR REPLACE FUNCTION get_rag_stats()
RETURNS TABLE (
    total_documents BIGINT,
    total_chunks BIGINT,
    total_collections BIGINT,
    avg_chunks_per_doc NUMERIC,
    total_size_bytes BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        (SELECT COUNT(*) FROM rag.documents),
        (SELECT COUNT(*) FROM rag.chunks),
        (SELECT COUNT(*) FROM rag.collections),
        (SELECT ROUND(AVG(chunk_count), 1) FROM rag.documents WHERE chunk_count > 0),
        (SELECT COALESCE(SUM(file_size), 0) FROM rag.documents);
END;
$$ LANGUAGE plpgsql;

-- RAG: Pure vector similarity search
CREATE OR REPLACE FUNCTION rag.search_similar_chunks(
    query_embedding VECTOR(1024),
    match_threshold FLOAT DEFAULT 0.7,
    match_count INT DEFAULT 5,
    filter_collection_id UUID DEFAULT NULL,
    filter_user_id UUID DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    document_id UUID,
    content TEXT,
    metadata JSONB,
    similarity FLOAT
)
LANGUAGE plpgsql STABLE
AS $$
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
$$;

-- RAG: Hybrid search (vector + BM25 keyword with RRF fusion)
CREATE OR REPLACE FUNCTION rag.hybrid_search(
    query_text TEXT,
    query_embedding VECTOR(1024),
    match_count INT DEFAULT 10,
    keyword_weight FLOAT DEFAULT 0.3,
    filter_collection_id UUID DEFAULT NULL,
    filter_user_id UUID DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    document_id UUID,
    content TEXT,
    metadata JSONB,
    vector_score FLOAT,
    keyword_score FLOAT,
    combined_score FLOAT
)
LANGUAGE plpgsql STABLE
AS $$
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
            1 - (c.embedding <=> query_embedding) AS v_score,
            ROW_NUMBER() OVER (ORDER BY c.embedding <=> query_embedding) AS v_rank
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
            ) AS k_score,
            ROW_NUMBER() OVER (
                ORDER BY ts_rank_cd(
                    to_tsvector('english', c.content),
                    websearch_to_tsquery('english', query_text),
                    32
                ) DESC
            ) AS k_rank
        FROM rag.chunks c
        JOIN rag.documents d ON c.document_id = d.id
        LEFT JOIN rag.document_collections dc ON c.document_id = dc.document_id
        WHERE
            to_tsvector('english', c.content) @@ websearch_to_tsquery('english', query_text)
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
            COALESCE(k.k_score, 0) AS k_score,
            (1.0 - keyword_weight) * (1.0 / (rrf_k + v.v_rank)) +
            keyword_weight * (1.0 / (rrf_k + COALESCE(k.k_rank, match_count * 2 + 1))) AS rrf_score
        FROM vector_results v
        LEFT JOIN keyword_results k ON v.id = k.id
    )
    SELECT
        f.id,
        f.document_id,
        f.content,
        f.metadata,
        f.v_score AS vector_score,
        f.k_score AS keyword_score,
        f.rrf_score AS combined_score
    FROM fused f
    ORDER BY f.rrf_score DESC
    LIMIT match_count;
END;
$$;

-- RAG: Search with metadata filtering
CREATE OR REPLACE FUNCTION rag.search_with_filters(
    query_embedding VECTOR(1024),
    metadata_filter JSONB DEFAULT '{}',
    match_count INT DEFAULT 5,
    filter_user_id UUID DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    document_id UUID,
    content TEXT,
    metadata JSONB,
    similarity FLOAT
)
LANGUAGE plpgsql STABLE
AS $$
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
$$;

-- RAG: Cleanup orphaned chunks
CREATE OR REPLACE FUNCTION rag.cleanup_orphaned_chunks()
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM rag.chunks
    WHERE document_id NOT IN (SELECT id FROM rag.documents);
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$;

-- =============================================================================
-- ROW LEVEL SECURITY
-- =============================================================================

-- Enable RLS on all public tables
ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.prompts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.usage_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.document_metadata ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.document_rows ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rag_pipeline_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.service_health_log ENABLE ROW LEVEL SECURITY;

-- Enable RLS on all rag tables
ALTER TABLE rag.documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE rag.chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE rag.collections ENABLE ROW LEVEL SECURITY;
ALTER TABLE rag.document_collections ENABLE ROW LEVEL SECURITY;
ALTER TABLE rag.conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE rag.messages ENABLE ROW LEVEL SECURITY;

-- ========================
-- PUBLIC SCHEMA RLS POLICIES
-- ========================

-- User Profiles
DROP POLICY IF EXISTS "Users can view own profile" ON public.user_profiles;
DROP POLICY IF EXISTS "Users can update own profile" ON public.user_profiles;
DROP POLICY IF EXISTS "Admins can view all profiles" ON public.user_profiles;
DROP POLICY IF EXISTS "Admins can update all profiles" ON public.user_profiles;
DROP POLICY IF EXISTS "Only admins can change admin status" ON public.user_profiles;
DROP POLICY IF EXISTS "Service role full access to user_profiles" ON public.user_profiles;
DROP POLICY IF EXISTS "Deny delete for user_profiles" ON public.user_profiles;

CREATE POLICY "Users can view own profile" ON public.user_profiles
    FOR SELECT USING (auth.uid() = id);
CREATE POLICY "Users can update own profile" ON public.user_profiles
    FOR UPDATE USING (auth.uid() = id)
    WITH CHECK (auth.uid() = id AND is_admin IS NOT DISTINCT FROM FALSE);
CREATE POLICY "Admins can view all profiles" ON public.user_profiles
    FOR SELECT USING (public.is_admin());
CREATE POLICY "Admins can update all profiles" ON public.user_profiles
    FOR UPDATE USING (public.is_admin());
CREATE POLICY "Only admins can change admin status" ON public.user_profiles
    FOR UPDATE TO authenticated
    USING (public.is_admin())
    WITH CHECK (public.is_admin());
CREATE POLICY "Service role full access to user_profiles" ON public.user_profiles
    FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Deny delete for user_profiles" ON public.user_profiles
    FOR DELETE USING (false);

-- Requests
DROP POLICY IF EXISTS "Users can view own requests" ON public.requests;
DROP POLICY IF EXISTS "Users can insert own requests" ON public.requests;
DROP POLICY IF EXISTS "Admins can view all requests" ON public.requests;
DROP POLICY IF EXISTS "Service role full access to requests" ON public.requests;
DROP POLICY IF EXISTS "Deny delete for requests" ON public.requests;

CREATE POLICY "Users can view own requests" ON public.requests
    FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own requests" ON public.requests
    FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Admins can view all requests" ON public.requests
    FOR SELECT USING (public.is_admin());
CREATE POLICY "Service role full access to requests" ON public.requests
    FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Deny delete for requests" ON public.requests
    FOR DELETE USING (false);

-- Agent Conversations
DROP POLICY IF EXISTS "Users can view own conversations" ON public.agent_conversations;
DROP POLICY IF EXISTS "Users can insert own conversations" ON public.agent_conversations;
DROP POLICY IF EXISTS "Users can update own conversations" ON public.agent_conversations;
DROP POLICY IF EXISTS "Admins can view all conversations" ON public.agent_conversations;
DROP POLICY IF EXISTS "Service role full access to agent_conversations" ON public.agent_conversations;
DROP POLICY IF EXISTS "Deny delete for agent_conversations" ON public.agent_conversations;

CREATE POLICY "Users can view own conversations" ON public.agent_conversations
    FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own conversations" ON public.agent_conversations
    FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own conversations" ON public.agent_conversations
    FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Admins can view all conversations" ON public.agent_conversations
    FOR SELECT USING (public.is_admin());
CREATE POLICY "Service role full access to agent_conversations" ON public.agent_conversations
    FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Deny delete for agent_conversations" ON public.agent_conversations
    FOR DELETE USING (false);

-- Agent Messages
DROP POLICY IF EXISTS "Users can view own messages" ON public.agent_messages;
DROP POLICY IF EXISTS "Users can insert own messages" ON public.agent_messages;
DROP POLICY IF EXISTS "Admins can view all messages" ON public.agent_messages;
DROP POLICY IF EXISTS "Service role full access to agent_messages" ON public.agent_messages;
DROP POLICY IF EXISTS "Deny delete for agent_messages" ON public.agent_messages;

CREATE POLICY "Users can view own messages" ON public.agent_messages
    FOR SELECT USING (auth.uid() = computed_session_user_id);
CREATE POLICY "Users can insert own messages" ON public.agent_messages
    FOR INSERT WITH CHECK (auth.uid() = computed_session_user_id);
CREATE POLICY "Admins can view all messages" ON public.agent_messages
    FOR SELECT USING (public.is_admin());
CREATE POLICY "Service role full access to agent_messages" ON public.agent_messages
    FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Deny delete for agent_messages" ON public.agent_messages
    FOR DELETE USING (false);

-- Conversations: authenticated users and service_role only
DROP POLICY IF EXISTS "conversations_all_access" ON public.conversations;
CREATE POLICY "conversations_all_access" ON public.conversations
    FOR ALL
    USING  (auth.role() = 'authenticated' OR auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'authenticated' OR auth.role() = 'service_role');

-- Messages: authenticated users and service_role only
DROP POLICY IF EXISTS "messages_all_access" ON public.messages;
CREATE POLICY "messages_all_access" ON public.messages
    FOR ALL
    USING  (auth.role() = 'authenticated' OR auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'authenticated' OR auth.role() = 'service_role');

-- Prompts: authenticated users and service_role only
DROP POLICY IF EXISTS "prompts_all_access" ON public.prompts;
CREATE POLICY "prompts_all_access" ON public.prompts
    FOR ALL
    USING  (auth.role() = 'authenticated' OR auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'authenticated' OR auth.role() = 'service_role');

-- Usage logs: service_role only (contains billing/cost data)
DROP POLICY IF EXISTS "usage_logs_all_access" ON public.usage_logs;
CREATE POLICY "usage_logs_all_access" ON public.usage_logs
    FOR ALL
    USING  (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- Document tables (backend-only, service role access)
DROP POLICY IF EXISTS "Service role access to document_metadata" ON public.document_metadata;
DROP POLICY IF EXISTS "Service role access to document_rows" ON public.document_rows;
DROP POLICY IF EXISTS "Service role access to public documents" ON public.documents;
DROP POLICY IF EXISTS "Service role access to rag_pipeline_state" ON public.rag_pipeline_state;

CREATE POLICY "Service role access to document_metadata" ON public.document_metadata
    FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role access to document_rows" ON public.document_rows
    FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role access to public documents" ON public.documents
    FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role access to rag_pipeline_state" ON public.rag_pipeline_state
    FOR ALL USING (auth.role() = 'service_role');

-- Chat log & service health log (backend-only, service role access)
DROP POLICY IF EXISTS "Service role access to chat_log" ON public.chat_log;
DROP POLICY IF EXISTS "Service role access to service_health_log" ON public.service_health_log;

CREATE POLICY "Service role access to chat_log" ON public.chat_log
    FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role access to service_health_log" ON public.service_health_log
    FOR ALL USING (auth.role() = 'service_role');

-- ========================
-- RAG SCHEMA RLS POLICIES
-- ========================

-- RAG Documents
DROP POLICY IF EXISTS "Users can view own rag documents" ON rag.documents;
DROP POLICY IF EXISTS "Users can insert own rag documents" ON rag.documents;
DROP POLICY IF EXISTS "Users can update own rag documents" ON rag.documents;
DROP POLICY IF EXISTS "Users can delete own rag documents" ON rag.documents;
DROP POLICY IF EXISTS "Service role full access to rag documents" ON rag.documents;

CREATE POLICY "Users can view own rag documents" ON rag.documents
    FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own rag documents" ON rag.documents
    FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own rag documents" ON rag.documents
    FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete own rag documents" ON rag.documents
    FOR DELETE USING (auth.uid() = user_id);
CREATE POLICY "Service role full access to rag documents" ON rag.documents
    FOR ALL USING (auth.role() = 'service_role');

-- RAG Chunks
DROP POLICY IF EXISTS "Users can view own chunks" ON rag.chunks;
DROP POLICY IF EXISTS "Service role full access to rag chunks" ON rag.chunks;

CREATE POLICY "Users can view own chunks" ON rag.chunks
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM rag.documents d
            WHERE d.id = document_id AND d.user_id = auth.uid()
        )
    );
CREATE POLICY "Service role full access to rag chunks" ON rag.chunks
    FOR ALL USING (auth.role() = 'service_role');

-- RAG Collections
DROP POLICY IF EXISTS "Users can view own collections" ON rag.collections;
DROP POLICY IF EXISTS "Users can insert own collections" ON rag.collections;
DROP POLICY IF EXISTS "Users can update own collections" ON rag.collections;
DROP POLICY IF EXISTS "Users can delete own collections" ON rag.collections;
DROP POLICY IF EXISTS "Service role full access to rag collections" ON rag.collections;

CREATE POLICY "Users can view own collections" ON rag.collections
    FOR SELECT USING (auth.uid() = user_id OR is_public = true);
CREATE POLICY "Users can insert own collections" ON rag.collections
    FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own collections" ON rag.collections
    FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete own collections" ON rag.collections
    FOR DELETE USING (auth.uid() = user_id);
CREATE POLICY "Service role full access to rag collections" ON rag.collections
    FOR ALL USING (auth.role() = 'service_role');

-- RAG Document Collections
DROP POLICY IF EXISTS "Users can manage own document_collections" ON rag.document_collections;
DROP POLICY IF EXISTS "Service role full access to rag document_collections" ON rag.document_collections;

CREATE POLICY "Users can manage own document_collections" ON rag.document_collections
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM rag.documents d
            WHERE d.id = document_id AND d.user_id = auth.uid()
        )
    );
CREATE POLICY "Service role full access to rag document_collections" ON rag.document_collections
    FOR ALL USING (auth.role() = 'service_role');

-- RAG Conversations
DROP POLICY IF EXISTS "Users can view own rag conversations" ON rag.conversations;
DROP POLICY IF EXISTS "Users can insert own rag conversations" ON rag.conversations;
DROP POLICY IF EXISTS "Users can update own rag conversations" ON rag.conversations;
DROP POLICY IF EXISTS "Users can delete own rag conversations" ON rag.conversations;
DROP POLICY IF EXISTS "Service role full access to rag conversations" ON rag.conversations;

CREATE POLICY "Users can view own rag conversations" ON rag.conversations
    FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own rag conversations" ON rag.conversations
    FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own rag conversations" ON rag.conversations
    FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete own rag conversations" ON rag.conversations
    FOR DELETE USING (auth.uid() = user_id);
CREATE POLICY "Service role full access to rag conversations" ON rag.conversations
    FOR ALL USING (auth.role() = 'service_role');

-- RAG Messages
DROP POLICY IF EXISTS "Users can view own rag messages" ON rag.messages;
DROP POLICY IF EXISTS "Users can insert own rag messages" ON rag.messages;
DROP POLICY IF EXISTS "Service role full access to rag messages" ON rag.messages;

CREATE POLICY "Users can view own rag messages" ON rag.messages
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM rag.conversations c
            WHERE c.id = conversation_id AND c.user_id = auth.uid()
        )
    );
CREATE POLICY "Users can insert own rag messages" ON rag.messages
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM rag.conversations c
            WHERE c.id = conversation_id AND c.user_id = auth.uid()
        )
    );
CREATE POLICY "Service role full access to rag messages" ON rag.messages
    FOR ALL USING (auth.role() = 'service_role');

-- =============================================================================
-- PERMISSIONS
-- =============================================================================

-- Public schema
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO service_role;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA public TO service_role;

GRANT SELECT, INSERT, UPDATE ON public.user_profiles TO authenticated;
GRANT SELECT, INSERT ON public.requests TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.agent_conversations TO authenticated;
GRANT SELECT, INSERT ON public.agent_messages TO authenticated;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO anon;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO authenticated;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO anon;

-- RAG schema
GRANT ALL ON ALL TABLES IN SCHEMA rag TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA rag TO service_role;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA rag TO service_role;

GRANT SELECT, INSERT, UPDATE, DELETE ON rag.documents TO authenticated;
GRANT SELECT ON rag.chunks TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON rag.collections TO authenticated;
GRANT SELECT, INSERT, DELETE ON rag.document_collections TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON rag.conversations TO authenticated;
GRANT SELECT, INSERT ON rag.messages TO authenticated;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA rag TO authenticated;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA rag TO authenticated;

-- =============================================================================
-- SAMPLE DATA
-- =============================================================================

INSERT INTO public.prompts (name, description, prompt_text, category, is_favorite) VALUES
    ('Code Review', 'Review code for bugs and improvements', 'Review this code for potential bugs, security issues, and suggest improvements. Focus on best practices and readability.', 'coding', true),
    ('Explain Code', 'Explain what code does', 'Explain what this code does step by step. Include the purpose, inputs, outputs, and any important details.', 'coding', true),
    ('Write Tests', 'Generate unit tests', 'Write comprehensive unit tests for this code. Include edge cases and use appropriate assertions.', 'coding', false),
    ('Summarize', 'Summarize text or document', 'Summarize the following content in a clear and concise way. Highlight the key points.', 'general', true),
    ('SQL Query', 'Help write SQL queries', 'Help me write a SQL query for the following requirement. Explain your approach.', 'database', false),
    ('Debug', 'Help debug an issue', 'Help me debug this issue. Analyze the error and suggest potential fixes.', 'coding', true),
    ('Refactor', 'Refactor code for better quality', 'Refactor this code to improve readability, maintainability, and performance while preserving functionality.', 'coding', false),
    ('Document', 'Generate documentation', 'Generate comprehensive documentation for this code including docstrings, comments, and usage examples.', 'coding', false)
ON CONFLICT DO NOTHING;

-- =============================================================================
-- VERIFICATION
-- =============================================================================

DO $$
DECLARE
    public_table_count INTEGER;
    rag_table_count INTEGER;
    func_count INTEGER;
    idx_count INTEGER;
    policy_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO public_table_count
    FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_type = 'BASE TABLE';

    SELECT COUNT(*) INTO rag_table_count
    FROM information_schema.tables
    WHERE table_schema = 'rag'
    AND table_type = 'BASE TABLE';

    SELECT COUNT(*) INTO func_count
    FROM pg_proc p
    JOIN pg_namespace n ON p.pronamespace = n.oid
    WHERE n.nspname IN ('public', 'rag');

    SELECT COUNT(*) INTO idx_count
    FROM pg_indexes
    WHERE indexdef LIKE '%hnsw%';

    SELECT COUNT(*) INTO policy_count
    FROM pg_policies
    WHERE schemaname IN ('public', 'rag');

    RAISE NOTICE '========================================';
    RAISE NOTICE 'Manic AI Schema Installation Complete';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Public tables: %', public_table_count;
    RAISE NOTICE 'RAG tables:    %', rag_table_count;
    RAISE NOTICE 'Functions:     %', func_count;
    RAISE NOTICE 'HNSW indexes:  %', idx_count;
    RAISE NOTICE 'RLS policies:  %', policy_count;
    RAISE NOTICE '========================================';
END
$$;

SELECT 'Manic AI database initialization complete!' AS status;
