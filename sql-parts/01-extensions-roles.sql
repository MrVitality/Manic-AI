-- =============================================================================
-- PART 1: EXTENSIONS AND ROLES
-- Run this first
-- =============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "vector";

-- Note: These extensions may already exist or require special permissions
-- Safe to ignore errors on these:
DO $$ BEGIN CREATE EXTENSION IF NOT EXISTS "pgjwt"; EXCEPTION WHEN OTHERS THEN NULL; END $$;
DO $$ BEGIN CREATE EXTENSION IF NOT EXISTS "pg_stat_statements"; EXCEPTION WHEN OTHERS THEN NULL; END $$;

-- Create schemas
CREATE SCHEMA IF NOT EXISTS rag;

-- Grant schema permissions
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
GRANT USAGE ON SCHEMA rag TO anon, authenticated, service_role;

-- Verify
SELECT extname FROM pg_extension WHERE extname IN ('vector', 'uuid-ossp', 'pg_trgm');
