-- =============================================================================
-- Migration 003: Add raw_content column to rag.documents
-- =============================================================================
-- Stores the full original document text during ingestion so it can be
-- retrieved later for re-chunking, citation display, or export.
-- =============================================================================

ALTER TABLE rag.documents
    ADD COLUMN IF NOT EXISTS raw_content TEXT;

COMMENT ON COLUMN rag.documents.raw_content IS 'Full original document text stored at ingestion time';
