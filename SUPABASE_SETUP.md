# Manic AI - Supabase Database Implementation Plan

Complete guide to setting up and managing the Supabase database stack for Manic AI.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Services Breakdown](#services-breakdown)
3. [Initial Setup](#initial-setup)
4. [Database Schema](#database-schema)
5. [Authentication Setup](#authentication-setup)
6. [API Access](#api-access)
7. [Studio Usage](#studio-usage)
8. [Maintenance](#maintenance)
9. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         SUPABASE STACK                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐            │
│  │   Studio     │     │    Kong      │     │   Storage    │            │
│  │   :3005      │     │   :8001      │     │   API        │            │
│  └──────┬───────┘     └──────┬───────┘     └──────┬───────┘            │
│         │                    │                    │                     │
│         │            ┌───────┴───────┐            │                     │
│         │            │               │            │                     │
│         ▼            ▼               ▼            ▼                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │  Postgres    │  │   PostgREST  │  │   GoTrue     │                  │
│  │    Meta      │  │   (REST)     │  │   (Auth)     │                  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                  │
│         │                 │                 │                           │
│         └─────────────────┼─────────────────┘                           │
│                           │                                             │
│                           ▼                                             │
│                  ┌──────────────────┐                                   │
│                  │   PostgreSQL     │                                   │
│                  │  + pgvector      │                                   │
│                  │     :5433        │                                   │
│                  └──────────────────┘                                   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Service Ports (Tailscale IP: 100.111.244.124)

| Service | Container | Port | URL |
|---------|-----------|------|-----|
| **PostgreSQL** | ai-supabase-db | 5433 | `postgresql://postgres:PASSWORD@100.111.244.124:5433/postgres` |
| **Kong API Gateway** | ai-supabase-kong | 8001 | http://100.111.244.124:8001 |
| **Studio UI** | ai-supabase-studio | 3005 | http://100.111.244.124:3005 |
| **Auth (GoTrue)** | ai-supabase-auth | internal | Via Kong at `/auth/v1/` |
| **REST (PostgREST)** | ai-supabase-rest | internal | Via Kong at `/rest/v1/` |
| **Storage API** | ai-supabase-storage | internal | Via Kong at `/storage/v1/` |
| **Postgres Meta** | ai-supabase-meta | internal | Used by Studio |

---

## Services Breakdown

### 1. PostgreSQL Database (`supabase-db`)

The core database running `supabase/postgres:15.1.1.78` which includes:

- **pgvector** - Vector similarity search (768-dim for nomic-embed-text)
- **pg_trgm** - Trigram text matching
- **uuid-ossp** - UUID generation
- **pgcrypto** - Encryption functions

**Configuration:**
```yaml
command:
  - postgres
  - -c wal_level=logical          # Enable logical replication
  - -c max_connections=200        # Connection pool
  - -c shared_buffers=256MB       # Memory for caching
  - -c effective_cache_size=768MB # Query planner hint
  - -c listen_addresses=*         # Accept all connections
```

### 2. Kong API Gateway (`supabase-kong`)

Routes external requests to internal services:

| Route | Destination |
|-------|-------------|
| `/auth/v1/*` | GoTrue (authentication) |
| `/rest/v1/*` | PostgREST (database API) |
| `/storage/v1/*` | Storage API |

Requires API key authentication (`apikey` header) with either:
- `ANON_KEY` - Public/anonymous access
- `SERVICE_ROLE_KEY` - Admin/service access

### 3. GoTrue Authentication (`supabase-auth`)

Handles user authentication:
- Email/password signup
- OAuth providers
- JWT token generation
- Password reset flows

### 4. PostgREST (`supabase-rest`)

Auto-generates REST API from PostgreSQL schema:
- `GET /rest/v1/table` - Select rows
- `POST /rest/v1/table` - Insert rows
- `PATCH /rest/v1/table?id=eq.1` - Update rows
- `DELETE /rest/v1/table?id=eq.1` - Delete rows

### 5. Studio (`supabase-studio`)

Web-based database management UI:
- Table editor
- SQL editor
- API documentation
- Database logs

---

## Initial Setup

### Step 1: Verify Services Are Running

```bash
docker compose ps
```

Expected output:
```
NAME                   STATUS
ai-supabase-db        healthy
ai-supabase-auth      running
ai-supabase-rest      running
ai-supabase-meta      running
ai-supabase-storage   running
ai-supabase-kong      running
ai-supabase-studio    running
```

### Step 2: Verify Database Initialization

The `init.sql` script runs automatically on first start. Verify it worked:

```bash
docker exec ai-supabase-db psql -U postgres -c "\dn"
```

Expected schemas:
```
   Name
-----------
 auth
 public
 rag
 storage
```

### Step 3: Verify Extensions

```bash
docker exec ai-supabase-db psql -U postgres -c "\dx"
```

Should show:
```
     Name     | Version
--------------+---------
 pgcrypto     | 1.3
 pg_trgm      | 1.6
 uuid-ossp    | 1.1
 vector       | 0.5.1
```

### Step 4: Access Studio

1. Open http://100.111.244.124:3005
2. You'll see the Supabase Studio dashboard
3. Navigate to **Table Editor** to view/edit data
4. Use **SQL Editor** to run queries

---

## Database Schema

### RAG Tables

The database includes a complete RAG (Retrieval-Augmented Generation) schema:

#### `rag.documents`
Stores uploaded document metadata:

```sql
CREATE TABLE rag.documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID,                    -- Optional owner
    filename TEXT NOT NULL,          -- Original filename
    content_type TEXT,               -- MIME type
    file_size BIGINT,                -- Size in bytes
    source_url TEXT,                 -- Optional source URL
    status TEXT DEFAULT 'pending',   -- pending|processing|completed|failed
    error_message TEXT,              -- Error details if failed
    chunk_count INTEGER DEFAULT 0,   -- Number of chunks created
    processing_time_ms INTEGER,      -- Processing duration
    metadata JSONB DEFAULT '{}',     -- Custom metadata
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
);
```

#### `rag.chunks`
Stores document chunks with embeddings:

```sql
CREATE TABLE rag.chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID REFERENCES rag.documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,      -- Position in document
    content TEXT NOT NULL,             -- Chunk text
    content_tokens INTEGER,            -- Token count
    embedding VECTOR(768),             -- nomic-embed-text vector
    metadata JSONB DEFAULT '{}',       -- Chunk metadata
    created_at TIMESTAMPTZ
);
```

#### `rag.collections`
Organize documents into groups:

```sql
CREATE TABLE rag.collections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID,
    name TEXT NOT NULL,
    description TEXT,
    is_public BOOLEAN DEFAULT FALSE,
    embedding_model TEXT DEFAULT 'nomic-embed-text',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
);
```

#### `rag.document_collections`
Many-to-many mapping:

```sql
CREATE TABLE rag.document_collections (
    document_id UUID REFERENCES rag.documents(id) ON DELETE CASCADE,
    collection_id UUID REFERENCES rag.collections(id) ON DELETE CASCADE,
    added_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (document_id, collection_id)
);
```

### Indexes

```sql
-- HNSW index for fast vector similarity search
CREATE INDEX idx_chunks_embedding_hnsw ON rag.chunks
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

-- Full-text search index
CREATE INDEX idx_chunks_content_fts ON rag.chunks
    USING gin (to_tsvector('english', content));

-- Trigram index for fuzzy text matching
CREATE INDEX idx_chunks_content_trgm ON rag.chunks
    USING gin (content gin_trgm_ops);
```

### Functions

#### Vector Search
```sql
-- Pure vector similarity search
SELECT * FROM rag.search_similar_chunks(
    query_embedding := '[0.1, 0.2, ...]'::vector(768),
    match_threshold := 0.7,
    match_count := 5,
    filter_collection_id := NULL,
    filter_user_id := NULL
);
```

#### Hybrid Search (Vector + Keyword)
```sql
-- Hybrid search with RRF fusion
SELECT * FROM rag.hybrid_search(
    query_text := 'your search query',
    query_embedding := '[0.1, 0.2, ...]'::vector(768),
    match_count := 10,
    keyword_weight := 0.3,
    filter_collection_id := NULL,
    filter_user_id := NULL
);
```

---

## Authentication Setup

### Current Configuration

Authentication is handled by GoTrue with these settings:

| Setting | Value |
|---------|-------|
| Signup enabled | Yes (`GOTRUE_DISABLE_SIGNUP=false`) |
| JWT expiry | 3600 seconds (1 hour) |
| Default role | `authenticated` |

### Using Authentication

#### 1. Sign Up a User

```bash
curl -X POST http://100.111.244.124:8001/auth/v1/signup \
  -H "apikey: YOUR_ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepassword123"
  }'
```

#### 2. Sign In

```bash
curl -X POST http://100.111.244.124:8001/auth/v1/token?grant_type=password \
  -H "apikey: YOUR_ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepassword123"
  }'
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600,
  "refresh_token": "..."
}
```

#### 3. Use Token in Requests

```bash
curl http://100.111.244.124:8001/rest/v1/rag.documents \
  -H "apikey: YOUR_ANON_KEY" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Your API Keys

From your `.env` file:

| Key | Value |
|-----|-------|
| **ANON_KEY** | `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoiYW5vbiIsImlzcyI6InN1cGFiYXNlIiwiaWF0IjoxNzY5MTQ0NDAwLCJleHAiOjE5MjY5MTA4MDB9.Uaa5wgZ5-5lBoQPsPhe7nzJITm1ikepeIWEgg8sf6oA` |
| **SERVICE_ROLE_KEY** | `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoic2VydmljZV9yb2xlIiwiaXNzIjoic3VwYWJhc2UiLCJpYXQiOjE3NjkxNDQ0MDAsImV4cCI6MTkyNjkxMDgwMH0.YUMWUKatT_kzdg4HkinJSSzbo1jtVT7SBd0tZ3wNGRg` |

> **Warning**: The `SERVICE_ROLE_KEY` bypasses Row Level Security. Only use in server-side code.

---

## API Access

### REST API (PostgREST)

Base URL: `http://100.111.244.124:8001/rest/v1/`

#### List Documents

```bash
curl "http://100.111.244.124:8001/rest/v1/documents" \
  -H "apikey: YOUR_ANON_KEY" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Query with Filters

```bash
# Documents with status = completed
curl "http://100.111.244.124:8001/rest/v1/documents?status=eq.completed" \
  -H "apikey: YOUR_ANON_KEY"

# Documents ordered by created_at
curl "http://100.111.244.124:8001/rest/v1/documents?order=created_at.desc" \
  -H "apikey: YOUR_ANON_KEY"

# Limit results
curl "http://100.111.244.124:8001/rest/v1/documents?limit=10" \
  -H "apikey: YOUR_ANON_KEY"
```

#### Insert Document

```bash
curl -X POST "http://100.111.244.124:8001/rest/v1/documents" \
  -H "apikey: YOUR_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -H "Prefer: return=representation" \
  -d '{
    "filename": "test.txt",
    "status": "pending"
  }'
```

#### RAG Schema Access

For RAG tables, use the schema prefix:

```bash
# Access rag.documents
curl "http://100.111.244.124:8001/rest/v1/rag.documents" \
  -H "apikey: YOUR_SERVICE_ROLE_KEY"

# Access rag.chunks
curl "http://100.111.244.124:8001/rest/v1/rag.chunks?document_id=eq.YOUR_DOC_ID" \
  -H "apikey: YOUR_SERVICE_ROLE_KEY"
```

### Direct PostgreSQL Access

Connect directly to the database:

```bash
# Using psql
psql postgresql://postgres:qajLZzJLXAgpjo4YTvGdRiRh@100.111.244.124:5433/postgres

# Using docker exec
docker exec -it ai-supabase-db psql -U postgres
```

---

## Studio Usage

### Accessing Studio

1. Navigate to http://100.111.244.124:3005
2. Studio connects to your local Supabase instance automatically

### Table Editor

1. Click **Table Editor** in the sidebar
2. Select schema (public, rag, auth, storage)
3. View, add, edit, or delete rows
4. Use filters and sorting

### SQL Editor

1. Click **SQL Editor** in the sidebar
2. Write and execute SQL queries
3. Save queries for later use

**Example Queries:**

```sql
-- Count documents by status
SELECT status, COUNT(*)
FROM rag.documents
GROUP BY status;

-- Find chunks for a document
SELECT id, chunk_index, LEFT(content, 100) as preview
FROM rag.chunks
WHERE document_id = 'your-uuid-here'
ORDER BY chunk_index;

-- Check vector dimensions
SELECT id, array_length(embedding::float[], 1) as dims
FROM rag.chunks
LIMIT 1;

-- Search similar chunks (requires embedding)
SELECT * FROM rag.search_similar_chunks(
    '[0.1, 0.2, ...]'::vector(768),
    0.7,
    5,
    NULL,
    NULL
);
```

### Logs

1. Click **Logs** in the sidebar
2. View database logs in real-time
3. Filter by log level

---

## Maintenance

### Backup Database

```bash
# Full backup
docker exec ai-supabase-db pg_dump -U postgres postgres > backup.sql

# Backup specific schema
docker exec ai-supabase-db pg_dump -U postgres -n rag postgres > rag_backup.sql

# Compressed backup
docker exec ai-supabase-db pg_dump -U postgres -Fc postgres > backup.dump
```

### Restore Database

```bash
# From SQL file
cat backup.sql | docker exec -i ai-supabase-db psql -U postgres

# From compressed dump
docker exec -i ai-supabase-db pg_restore -U postgres -d postgres < backup.dump
```

### Vacuum and Analyze

```bash
# Vacuum the database (reclaim space)
docker exec ai-supabase-db psql -U postgres -c "VACUUM ANALYZE;"

# Vacuum specific table
docker exec ai-supabase-db psql -U postgres -c "VACUUM ANALYZE rag.chunks;"
```

### Reindex Vectors

If search performance degrades:

```bash
docker exec ai-supabase-db psql -U postgres -c "REINDEX INDEX rag.idx_chunks_embedding_hnsw;"
```

### Check Database Size

```bash
docker exec ai-supabase-db psql -U postgres -c "
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE schemaname IN ('public', 'rag')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
"
```

### Clean Orphaned Chunks

```bash
docker exec ai-supabase-db psql -U postgres -c "SELECT rag.cleanup_orphaned_chunks();"
```

---

## Troubleshooting

### Issue: Supabase Auth Keeps Restarting

**Symptom**: `ai-supabase-auth` container restarts repeatedly

**Cause**: Password in `GOTRUE_DB_DATABASE_URL` contains special characters (`/`, `=`)

**Solution**: Use simple alphanumeric password:
```bash
# Bad
GOTRUE_DB_DATABASE_URL=postgresql://postgres:abc/def=@supabase-db:5432/postgres

# Good
GOTRUE_DB_DATABASE_URL=postgresql://postgres:qajLZzJLXAgpjo4YTvGdRiRh@supabase-db:5432/postgres?search_path=auth
```

### Issue: Studio Not Loading

**Symptom**: Studio shows blank page or connection errors

**Check**:
1. Verify `supabase-meta` is running: `docker ps | grep meta`
2. Check Studio logs: `docker logs ai-supabase-studio`
3. Ensure environment variables are set correctly

### Issue: REST API Returns 401

**Symptom**: `{"message":"No API key found in request"}`

**Solution**: Include the `apikey` header:
```bash
curl -H "apikey: YOUR_ANON_KEY" http://100.111.244.124:8001/rest/v1/table
```

### Issue: Database Connection Refused

**Symptom**: `connection refused` when connecting to PostgreSQL

**Check**:
1. Database is running: `docker ps | grep supabase-db`
2. Port is correct (5433 not 5432)
3. IP is accessible (use Tailscale IP)

### Issue: pgvector Extension Missing

**Symptom**: `ERROR: type "vector" does not exist`

**Solution**: The Supabase image includes pgvector. Verify:
```bash
docker exec ai-supabase-db psql -U postgres -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### Issue: Schema Not Found

**Symptom**: `ERROR: schema "rag" does not exist`

**Solution**: Run the init script manually:
```bash
docker exec -i ai-supabase-db psql -U postgres < supabase/init.sql
```

### View Container Logs

```bash
# All Supabase logs
docker compose logs -f supabase-db supabase-auth supabase-rest supabase-studio

# Specific service
docker logs -f ai-supabase-db
docker logs -f ai-supabase-auth
```

### Reset Database (DESTRUCTIVE)

```bash
# Stop services
docker compose down

# Remove database volume
docker volume rm manic-ai_supabase-db-data

# Restart (will reinitialize)
docker compose up -d
```

---

## Quick Reference

### Connection Strings

| Type | Connection String |
|------|-------------------|
| **Direct PostgreSQL** | `postgresql://postgres:qajLZzJLXAgpjo4YTvGdRiRh@100.111.244.124:5433/postgres` |
| **Internal (Docker)** | `postgresql://postgres:qajLZzJLXAgpjo4YTvGdRiRh@supabase-db:5432/postgres` |
| **REST API** | `http://100.111.244.124:8001/rest/v1/` |
| **Auth API** | `http://100.111.244.124:8001/auth/v1/` |

### Common Commands

```bash
# Check service status
docker compose ps

# View logs
docker logs -f ai-supabase-db

# Connect to database
docker exec -it ai-supabase-db psql -U postgres

# Run SQL file
docker exec -i ai-supabase-db psql -U postgres < script.sql

# Backup
docker exec ai-supabase-db pg_dump -U postgres postgres > backup.sql

# Restart specific service
docker compose restart supabase-db
```

---

*Generated for Manic AI v2.0.0*
*Tailscale IP: 100.111.244.124*
