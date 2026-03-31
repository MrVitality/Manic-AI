-- Migration: Switch hybrid_search from weighted RRF to pure (equal-weight) RRF.
-- The keyword_weight parameter is kept in the function signature for backward
-- compatibility but is no longer used in the scoring formula.
-- Pure RRF is more robust across query types and eliminates a tuning parameter.
-- Reference: "Reciprocal Rank Fusion outperforms Condorcet and individual
-- Rank Learning Methods" (Cormack et al., SIGIR 2009), rrf_k=60.

CREATE OR REPLACE FUNCTION rag.hybrid_search(
    query_text TEXT,
    query_embedding VECTOR(1024),
    match_count INT DEFAULT 10,
    keyword_weight FLOAT DEFAULT 0.3,  -- kept for backward compat, now ignored
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
            -- Pure RRF: equal weights for vector and keyword ranks.
            (1.0 / (rrf_k + v.v_rank)) +
            (1.0 / (rrf_k + COALESCE(k.k_rank, match_count * 2 + 1))) AS rrf_score
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
