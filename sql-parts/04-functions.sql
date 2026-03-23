-- =============================================================================
-- PART 4: FUNCTIONS
-- Run after Part 3
-- =============================================================================

-- Drop existing functions
DROP FUNCTION IF EXISTS public.handle_new_user() CASCADE;
DROP FUNCTION IF EXISTS public.is_admin() CASCADE;
DROP FUNCTION IF EXISTS public.match_documents(vector, int, jsonb) CASCADE;
DROP FUNCTION IF EXISTS public.execute_custom_sql(text) CASCADE;
DROP FUNCTION IF EXISTS public.update_updated_at() CASCADE;
DROP FUNCTION IF EXISTS rag.search_similar_chunks CASCADE;
DROP FUNCTION IF EXISTS rag.hybrid_search CASCADE;
DROP FUNCTION IF EXISTS rag.search_with_filters CASCADE;
DROP FUNCTION IF EXISTS rag.cleanup_orphaned_chunks() CASCADE;

-- -----------------------------------------------------------------------------
-- Common: Update timestamp trigger function
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- -----------------------------------------------------------------------------
-- User Management: Handle new user signup
-- -----------------------------------------------------------------------------
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

-- -----------------------------------------------------------------------------
-- User Management: Check if current user is admin
-- -----------------------------------------------------------------------------
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

-- -----------------------------------------------------------------------------
-- Legacy: Match documents (backward compatibility)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.match_documents(
    query_embedding VECTOR(768),
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

-- -----------------------------------------------------------------------------
-- Admin: Execute custom SQL
-- WARNING: THIS FUNCTION IS DISABLED FOR SECURITY REASONS.
-- The original LIKE 'SELECT%' prefix check is trivially bypassed via subqueries
-- that contain mutations (e.g. SELECT (DELETE FROM ...) or CTEs with DML).
-- Do not re-enable without a proper allowlist-based SQL parser.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.execute_custom_sql(sql_query TEXT)
RETURNS JSONB
LANGUAGE plpgsql SECURITY DEFINER
AS $$
BEGIN
    RAISE EXCEPTION 'execute_custom_sql is disabled for security';
END;
$$;

REVOKE EXECUTE ON FUNCTION public.execute_custom_sql(text) FROM PUBLIC, authenticated, anon;
GRANT EXECUTE ON FUNCTION public.execute_custom_sql(text) TO service_role;

-- -----------------------------------------------------------------------------
-- RAG: Pure vector similarity search
-- -----------------------------------------------------------------------------
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

-- -----------------------------------------------------------------------------
-- RAG: Hybrid search (vector + BM25 with RRF fusion)
-- -----------------------------------------------------------------------------
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

-- -----------------------------------------------------------------------------
-- RAG: Search with metadata filtering
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION rag.search_with_filters(
    query_embedding VECTOR(768),
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

-- -----------------------------------------------------------------------------
-- RAG: Cleanup orphaned chunks
-- -----------------------------------------------------------------------------
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

-- Verify
SELECT routine_schema, routine_name 
FROM information_schema.routines 
WHERE routine_schema IN ('public', 'rag') 
AND routine_type = 'FUNCTION'
ORDER BY routine_schema, routine_name;
