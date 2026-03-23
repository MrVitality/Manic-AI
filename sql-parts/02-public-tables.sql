-- =============================================================================
-- PART 2: PUBLIC SCHEMA TABLES
-- Run after Part 1
-- =============================================================================

-- !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
-- WARNING: DATA DESTRUCTIVE — This script drops and recreates all tables.
-- DO NOT run against a database containing real data.
-- For production migrations, use incremental ALTER TABLE statements.
-- !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

-- Drop existing tables (safe cleanup)
DROP TABLE IF EXISTS public.agent_messages CASCADE;
DROP TABLE IF EXISTS public.agent_conversations CASCADE;
DROP TABLE IF EXISTS public.document_rows CASCADE;
DROP TABLE IF EXISTS public.documents CASCADE;
DROP TABLE IF EXISTS public.document_metadata CASCADE;
DROP TABLE IF EXISTS public.requests CASCADE;
DROP TABLE IF EXISTS public.user_profiles CASCADE;
DROP TABLE IF EXISTS public.rag_pipeline_state CASCADE;

-- -----------------------------------------------------------------------------
-- User Profiles Table
-- -----------------------------------------------------------------------------
CREATE TABLE public.user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    full_name TEXT,
    avatar_url TEXT,
    is_admin BOOLEAN DEFAULT FALSE,
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX idx_user_profiles_email ON public.user_profiles(email);
CREATE INDEX idx_user_profiles_is_admin ON public.user_profiles(is_admin);

-- -----------------------------------------------------------------------------
-- Requests Table
-- -----------------------------------------------------------------------------
CREATE TABLE public.requests (
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

CREATE INDEX idx_requests_user_id ON public.requests(user_id);
CREATE INDEX idx_requests_created_at ON public.requests(created_at DESC);

-- -----------------------------------------------------------------------------
-- Agent Conversations Table
-- -----------------------------------------------------------------------------
CREATE TABLE public.agent_conversations (
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

CREATE INDEX idx_agent_conversations_user ON public.agent_conversations(user_id);
CREATE INDEX idx_agent_conversations_last_message ON public.agent_conversations(last_message_at DESC);

-- -----------------------------------------------------------------------------
-- Agent Messages Table
-- -----------------------------------------------------------------------------
CREATE TABLE public.agent_messages (
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

CREATE INDEX idx_agent_messages_session ON public.agent_messages(session_id);
CREATE INDEX idx_agent_messages_computed_user ON public.agent_messages(computed_session_user_id);
CREATE INDEX idx_agent_messages_created_at ON public.agent_messages(created_at);

-- -----------------------------------------------------------------------------
-- Document Metadata Table
-- -----------------------------------------------------------------------------
CREATE TABLE public.document_metadata (
    id TEXT PRIMARY KEY,
    title TEXT,
    url TEXT,
    source_type TEXT,
    schema_definition TEXT,
    row_count INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_document_metadata_source_type ON public.document_metadata(source_type);

-- -----------------------------------------------------------------------------
-- Document Rows Table
-- -----------------------------------------------------------------------------
CREATE TABLE public.document_rows (
    id BIGSERIAL PRIMARY KEY,
    dataset_id TEXT REFERENCES public.document_metadata(id) ON DELETE CASCADE,
    row_data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_document_rows_dataset ON public.document_rows(dataset_id);
CREATE INDEX idx_document_rows_data ON public.document_rows USING gin(row_data);

-- -----------------------------------------------------------------------------
-- Documents Table (Legacy vector storage)
-- -----------------------------------------------------------------------------
CREATE TABLE public.documents (
    id BIGSERIAL PRIMARY KEY,
    content TEXT,
    metadata JSONB,
    embedding VECTOR(768)
);

CREATE INDEX idx_public_documents_embedding ON public.documents 
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

-- -----------------------------------------------------------------------------
-- RAG Pipeline State Table
-- -----------------------------------------------------------------------------
CREATE TABLE public.rag_pipeline_state (
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

CREATE INDEX idx_rag_pipeline_state_type ON public.rag_pipeline_state(pipeline_type);
CREATE INDEX idx_rag_pipeline_state_status ON public.rag_pipeline_state(run_status);

-- Verify
SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;
