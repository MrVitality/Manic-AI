-- =============================================================================
-- Manic AI - Database Initialization
-- Complete schema for Supabase PostgreSQL with pgvector RAG support
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
        CREATE ROLE authenticator NOINHERIT LOGIN PASSWORD 'postgres';
    END IF;
END
$$;

GRANT anon TO authenticator;
GRANT authenticated TO authenticator;
GRANT service_role TO authenticator;

GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
GRANT USAGE ON SCHEMA rag TO anon, authenticated, service_role;

-- ========================
-- RAG DOCUMENTS TABLE
-- ========================
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

-- ========================
-- RAG CHUNKS TABLE (768-dim vectors for nomic-embed-text)
-- ========================
CREATE TABLE IF NOT EXISTS rag.chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID REFERENCES rag.documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    content_tokens INTEGER,
    embedding VECTOR(768),
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

-- ========================
-- RAG COLLECTIONS TABLE
-- ========================
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

-- ========================
-- DOCUMENT-COLLECTION MAPPING
-- ========================
CREATE TABLE IF NOT EXISTS rag.document_collections (
    document_id UUID REFERENCES rag.documents(id) ON DELETE CASCADE,
    collection_id UUID REFERENCES rag.collections(id) ON DELETE CASCADE,
    added_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (document_id, collection_id)
);

CREATE INDEX IF NOT EXISTS idx_doc_collections_collection ON rag.document_collections(collection_id);

-- ========================
-- FUNCTIONS
-- ========================

-- Update timestamp trigger
CREATE OR REPLACE FUNCTION public.update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Auto-update triggers
DO $$
BEGIN
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
END
$$;

-- RAG: Pure vector similarity search
CREATE OR REPLACE FUNCTION rag.search_similar_chunks(
    query_embedding VECTOR(768),
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
    query_embedding VECTOR(768),
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

-- ========================
-- PERMISSIONS
-- ========================
GRANT ALL ON ALL TABLES IN SCHEMA rag TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA rag TO authenticated;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA rag TO service_role;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA rag TO authenticated;

SELECT 'Manic AI database initialization complete!' as status;
