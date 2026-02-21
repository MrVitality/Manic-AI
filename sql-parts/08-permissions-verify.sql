-- =============================================================================
-- PART 8: PERMISSIONS AND VERIFICATION
-- Run after Part 7 (FINAL PART)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Public Schema Permissions
-- -----------------------------------------------------------------------------
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO service_role;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA public TO service_role;

GRANT SELECT, INSERT, UPDATE ON public.user_profiles TO authenticated;
GRANT SELECT, INSERT ON public.requests TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.agent_conversations TO authenticated;
GRANT SELECT, INSERT ON public.agent_messages TO authenticated;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO authenticated;

-- -----------------------------------------------------------------------------
-- RAG Schema Permissions
-- -----------------------------------------------------------------------------
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
-- VERIFICATION
-- =============================================================================

DO $$
DECLARE
    ext_count INTEGER;
    public_table_count INTEGER;
    rag_table_count INTEGER;
    func_count INTEGER;
    idx_count INTEGER;
    policy_count INTEGER;
BEGIN
    -- Check extensions
    SELECT COUNT(*) INTO ext_count 
    FROM pg_extension 
    WHERE extname IN ('vector', 'uuid-ossp', 'pg_trgm');
    
    IF ext_count < 3 THEN
        RAISE WARNING 'Some required extensions may be missing (found %/3)', ext_count;
    END IF;
    
    -- Check pgvector specifically
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        RAISE EXCEPTION 'CRITICAL: pgvector extension not installed!';
    END IF;
    
    -- Count public tables
    SELECT COUNT(*) INTO public_table_count
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_type = 'BASE TABLE';
    
    -- Count rag tables
    SELECT COUNT(*) INTO rag_table_count
    FROM information_schema.tables 
    WHERE table_schema = 'rag' 
    AND table_type = 'BASE TABLE';
    
    -- Count functions
    SELECT COUNT(*) INTO func_count
    FROM pg_proc p
    JOIN pg_namespace n ON p.pronamespace = n.oid
    WHERE n.nspname IN ('public', 'rag');
    
    -- Check HNSW indexes
    SELECT COUNT(*) INTO idx_count
    FROM pg_indexes 
    WHERE indexdef LIKE '%hnsw%';
    
    -- Count policies
    SELECT COUNT(*) INTO policy_count
    FROM pg_policies
    WHERE schemaname IN ('public', 'rag');
    
    RAISE NOTICE '';
    RAISE NOTICE '╔══════════════════════════════════════════════════════════════╗';
    RAISE NOTICE '║         SUPABASE INITIALIZATION COMPLETE!                    ║';
    RAISE NOTICE '╠══════════════════════════════════════════════════════════════╣';
    RAISE NOTICE '║  Public schema tables: %                                     ', public_table_count;
    RAISE NOTICE '║  RAG schema tables:    %                                     ', rag_table_count;
    RAISE NOTICE '║  Functions created:    %                                     ', func_count;
    RAISE NOTICE '║  HNSW indexes:         %                                     ', idx_count;
    RAISE NOTICE '║  RLS policies:         %                                     ', policy_count;
    RAISE NOTICE '╠══════════════════════════════════════════════════════════════╣';
    RAISE NOTICE '║  Vector dimension:     768 (nomic-embed-text)                ║';
    RAISE NOTICE '║  Index type:           HNSW (m=16, ef_construction=64)       ║';
    RAISE NOTICE '║  Hybrid search:        Enabled (vector + BM25)               ║';
    RAISE NOTICE '╚══════════════════════════════════════════════════════════════╝';
    
    IF idx_count < 2 THEN
        RAISE WARNING 'Expected 2+ HNSW indexes, found %. Vector search may be slow.', idx_count;
    END IF;
    
    IF policy_count < 20 THEN
        RAISE WARNING 'Expected 20+ RLS policies, found %. Security may be incomplete.', policy_count;
    END IF;
END
$$;

-- =============================================================================
-- QUICK REFERENCE QUERIES
-- =============================================================================

-- List all tables
SELECT 
    table_schema,
    table_name,
    (SELECT COUNT(*) FROM information_schema.columns c WHERE c.table_schema = t.table_schema AND c.table_name = t.table_name) as column_count
FROM information_schema.tables t
WHERE table_schema IN ('public', 'rag')
AND table_type = 'BASE TABLE'
ORDER BY table_schema, table_name;

-- List HNSW indexes
SELECT indexname, tablename 
FROM pg_indexes 
WHERE indexdef LIKE '%hnsw%';

-- List search functions
SELECT routine_schema, routine_name 
FROM information_schema.routines 
WHERE routine_name LIKE '%search%' OR routine_name LIKE '%match%'
ORDER BY routine_schema, routine_name;
