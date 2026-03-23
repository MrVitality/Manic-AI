-- =============================================================================
-- DEPRECATED - DO NOT USE
-- =============================================================================
-- This file is superseded by supabase/init.sql which is the single canonical
-- schema. That file is mounted as the Docker entrypoint init script and
-- contains ALL tables, functions, triggers, RLS policies, and permissions
-- consolidated from every schema source in the project.
--
-- This file is kept for historical reference only. Any schema changes should
-- be made in supabase/init.sql.
--
-- Canonical source: supabase/init.sql
-- Deprecated: 2026-03-17
-- =============================================================================
--
-- (Original content follows for reference)
-- =============================================================================
-- Manic AI - Complete Database Schema (Single User)
-- Run in Supabase Studio SQL Editor
-- =============================================================================

-- ========================
-- EXTENSIONS
-- ========================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS vector;

DO $$ BEGIN CREATE EXTENSION IF NOT EXISTS "pgjwt"; EXCEPTION WHEN OTHERS THEN NULL; END $$;

-- ========================
-- SCHEMAS
-- ========================
CREATE SCHEMA IF NOT EXISTS rag;

-- ========================
-- HELPER FUNCTION (must exist first)
-- ========================
CREATE OR REPLACE FUNCTION public.update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- PART 1: RAG DOCUMENTS & EMBEDDINGS
-- =============================================================================

-- Document collections
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

-- Documents
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
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rag_documents_user_id ON rag.documents(user_id);
CREATE INDEX IF NOT EXISTS idx_rag_documents_status ON rag.documents(status);
CREATE INDEX IF NOT EXISTS idx_rag_documents_created_at ON rag.documents(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_rag_documents_metadata ON rag.documents USING gin(metadata);

-- Document chunks with embeddings (1024-dim for bge-m3)
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

-- HNSW index for fast vector search
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw ON rag.chunks
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

-- Full-text search index
CREATE INDEX IF NOT EXISTS idx_chunks_content_fts ON rag.chunks
    USING gin (to_tsvector('english', content));

-- Trigram index for fuzzy search
CREATE INDEX IF NOT EXISTS idx_chunks_content_trgm ON rag.chunks
    USING gin (content gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON rag.chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_metadata ON rag.chunks USING gin(metadata);

-- Document-collection mapping (many-to-many)
CREATE TABLE IF NOT EXISTS rag.document_collections (
    document_id UUID REFERENCES rag.documents(id) ON DELETE CASCADE,
    collection_id UUID REFERENCES rag.collections(id) ON DELETE CASCADE,
    added_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (document_id, collection_id)
);

CREATE INDEX IF NOT EXISTS idx_doc_collections_collection ON rag.document_collections(collection_id);

-- =============================================================================
-- PART 2: CONVERSATIONS & MESSAGES
-- =============================================================================

-- Conversations
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

-- Messages
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

-- =============================================================================
-- PART 3: PROMPTS & UTILITIES
-- =============================================================================

-- Saved prompts/templates
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

-- Usage tracking
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

-- =============================================================================
-- TRIGGERS
-- =============================================================================

-- Auto-update timestamps
DROP TRIGGER IF EXISTS trg_documents_updated_at ON rag.documents;
CREATE TRIGGER trg_documents_updated_at
    BEFORE UPDATE ON rag.documents
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();

DROP TRIGGER IF EXISTS trg_collections_updated_at ON rag.collections;
CREATE TRIGGER trg_collections_updated_at
    BEFORE UPDATE ON rag.collections
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();

DROP TRIGGER IF EXISTS trg_conversations_updated_at ON public.conversations;
CREATE TRIGGER trg_conversations_updated_at
    BEFORE UPDATE ON public.conversations
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();

DROP TRIGGER IF EXISTS trg_prompts_updated_at ON public.prompts;
CREATE TRIGGER trg_prompts_updated_at
    BEFORE UPDATE ON public.prompts
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();

-- =============================================================================
-- ROW LEVEL SECURITY (RLS)
-- =============================================================================
-- Note: For single-user setup, these policies allow full access.
-- If you add authentication later, update policies to use auth.uid()

-- Enable RLS on all tables
ALTER TABLE rag.collections ENABLE ROW LEVEL SECURITY;
ALTER TABLE rag.documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE rag.chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE rag.document_collections ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.prompts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.usage_logs ENABLE ROW LEVEL SECURITY;

-- ========================
-- RAG SCHEMA POLICIES
-- ========================

-- Collections: Full access (single user)
DROP POLICY IF EXISTS "collections_all_access" ON rag.collections;
CREATE POLICY "collections_all_access" ON rag.collections
    FOR ALL USING (true) WITH CHECK (true);

-- Documents: Full access (single user)
DROP POLICY IF EXISTS "documents_all_access" ON rag.documents;
CREATE POLICY "documents_all_access" ON rag.documents
    FOR ALL USING (true) WITH CHECK (true);

-- Chunks: Full access (single user)
DROP POLICY IF EXISTS "chunks_all_access" ON rag.chunks;
CREATE POLICY "chunks_all_access" ON rag.chunks
    FOR ALL USING (true) WITH CHECK (true);

-- Document-Collection mappings: Full access (single user)
DROP POLICY IF EXISTS "doc_collections_all_access" ON rag.document_collections;
CREATE POLICY "doc_collections_all_access" ON rag.document_collections
    FOR ALL USING (true) WITH CHECK (true);

-- ========================
-- PUBLIC SCHEMA POLICIES
-- ========================

-- Conversations: Full access (single user)
DROP POLICY IF EXISTS "conversations_all_access" ON public.conversations;
CREATE POLICY "conversations_all_access" ON public.conversations
    FOR ALL USING (true) WITH CHECK (true);

-- Messages: Full access (single user)
DROP POLICY IF EXISTS "messages_all_access" ON public.messages;
CREATE POLICY "messages_all_access" ON public.messages
    FOR ALL USING (true) WITH CHECK (true);

-- Prompts: Full access (single user)
DROP POLICY IF EXISTS "prompts_all_access" ON public.prompts;
CREATE POLICY "prompts_all_access" ON public.prompts
    FOR ALL USING (true) WITH CHECK (true);

-- Usage logs: Full access (single user)
DROP POLICY IF EXISTS "usage_logs_all_access" ON public.usage_logs;
CREATE POLICY "usage_logs_all_access" ON public.usage_logs
    FOR ALL USING (true) WITH CHECK (true);

-- ========================
-- SERVICE ROLE BYPASS
-- ========================
-- Grant service role full access (bypasses RLS)
GRANT ALL ON ALL TABLES IN SCHEMA rag TO service_role;
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT USAGE ON SCHEMA rag TO service_role;
GRANT USAGE ON SCHEMA public TO service_role;

-- Grant anon role access for API calls
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA rag TO anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO anon;
GRANT USAGE ON SCHEMA rag TO anon;
GRANT USAGE ON SCHEMA public TO anon;

-- =============================================================================
-- RAG SEARCH FUNCTIONS
-- =============================================================================

-- Pure vector similarity search
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

-- Hybrid search (vector + BM25 keyword with RRF fusion)
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

-- =============================================================================
-- HELPER FUNCTIONS
-- =============================================================================

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

-- Cleanup orphaned chunks
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
-- SAMPLE DATA
-- =============================================================================

-- Sample prompts
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
    table_count INTEGER;
    function_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO table_count
    FROM information_schema.tables
    WHERE table_schema IN ('public', 'rag')
    AND table_name IN ('conversations', 'messages', 'prompts', 'usage_logs', 'documents', 'chunks', 'collections', 'document_collections');

    SELECT COUNT(*) INTO function_count
    FROM pg_proc p
    JOIN pg_namespace n ON p.pronamespace = n.oid
    WHERE n.nspname IN ('public', 'rag')
    AND p.proname IN ('hybrid_search', 'search_similar_chunks', 'get_conversation_with_messages', 'get_usage_stats', 'get_rag_stats');

    RAISE NOTICE '========================================';
    RAISE NOTICE 'Manic AI Schema Installation Complete';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Tables created: %', table_count;
    RAISE NOTICE 'Functions created: %', function_count;
    RAISE NOTICE '========================================';
END
$$;

SELECT 'Manic AI complete schema installed successfully!' AS status;
