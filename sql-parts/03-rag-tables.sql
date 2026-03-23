-- =============================================================================
-- PART 3: RAG SCHEMA TABLES
-- Run after Part 2
-- =============================================================================

-- Drop existing tables (safe cleanup)
DROP TABLE IF EXISTS rag.messages CASCADE;
DROP TABLE IF EXISTS rag.conversations CASCADE;
DROP TABLE IF EXISTS rag.document_collections CASCADE;
DROP TABLE IF EXISTS rag.collections CASCADE;
DROP TABLE IF EXISTS rag.chunks CASCADE;
DROP TABLE IF EXISTS rag.documents CASCADE;

-- -----------------------------------------------------------------------------
-- RAG Documents Table
-- -----------------------------------------------------------------------------
CREATE TABLE rag.documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    -- NOT NULL: system-owned documents should use a dedicated system user UUID
    user_id UUID NOT NULL,
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

CREATE INDEX idx_rag_documents_user_id ON rag.documents(user_id);
CREATE INDEX idx_rag_documents_status ON rag.documents(status);
CREATE INDEX idx_rag_documents_created_at ON rag.documents(created_at DESC);
CREATE INDEX idx_rag_documents_metadata ON rag.documents USING gin(metadata);

-- -----------------------------------------------------------------------------
-- RAG Chunks Table (Vector embeddings)
-- Using 1024 dimensions for bge-m3 (standardized embedding model)
-- -----------------------------------------------------------------------------
CREATE TABLE rag.chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID REFERENCES rag.documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    content_tokens INTEGER,
    embedding VECTOR(1024),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- HNSW index (15x faster than IVFFlat)
-- ef_construction = 128: better recall on larger datasets (default 64 undershoots at scale).
-- m = 16 is left unchanged — higher m increases memory overhead without proportional recall gain.
-- To apply to existing deployment:
--   DROP INDEX IF EXISTS idx_chunks_embedding_hnsw;
--   Then re-run this CREATE INDEX statement.
--   This will trigger a full index rebuild (may take minutes for large datasets).
CREATE INDEX idx_chunks_embedding_hnsw ON rag.chunks
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 128);

-- Full-text search index for hybrid search
CREATE INDEX idx_chunks_content_fts ON rag.chunks 
    USING gin (to_tsvector('english', content));

-- Trigram index for fuzzy matching
CREATE INDEX idx_chunks_content_trgm ON rag.chunks 
    USING gin (content gin_trgm_ops);

CREATE INDEX idx_chunks_document_id ON rag.chunks(document_id);
CREATE INDEX idx_chunks_metadata ON rag.chunks USING gin(metadata);

-- -----------------------------------------------------------------------------
-- RAG Collections Table
-- -----------------------------------------------------------------------------
CREATE TABLE rag.collections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    -- NOT NULL: system-owned collections should use a dedicated system user UUID
    user_id UUID NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    is_public BOOLEAN DEFAULT FALSE,
    embedding_model TEXT DEFAULT 'bge-m3',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_rag_collections_user_id ON rag.collections(user_id);
CREATE INDEX idx_rag_collections_public ON rag.collections(is_public) WHERE is_public = true;

-- -----------------------------------------------------------------------------
-- Document-Collection Mapping
-- -----------------------------------------------------------------------------
CREATE TABLE rag.document_collections (
    document_id UUID REFERENCES rag.documents(id) ON DELETE CASCADE,
    collection_id UUID REFERENCES rag.collections(id) ON DELETE CASCADE,
    added_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (document_id, collection_id)
);

CREATE INDEX idx_doc_collections_collection ON rag.document_collections(collection_id);

-- -----------------------------------------------------------------------------
-- RAG Conversations Table
-- -----------------------------------------------------------------------------
CREATE TABLE rag.conversations (
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

CREATE INDEX idx_rag_conversations_user_id ON rag.conversations(user_id);
CREATE INDEX idx_rag_conversations_collection ON rag.conversations(collection_id);
CREATE INDEX idx_rag_conversations_created_at ON rag.conversations(created_at DESC);

-- -----------------------------------------------------------------------------
-- RAG Messages Table
-- -----------------------------------------------------------------------------
CREATE TABLE rag.messages (
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

CREATE INDEX idx_rag_messages_conversation ON rag.messages(conversation_id);
CREATE INDEX idx_rag_messages_created_at ON rag.messages(created_at);

-- Verify
SELECT tablename FROM pg_tables WHERE schemaname = 'rag' ORDER BY tablename;
