# Manic AI — Architecture Reference

Last updated: 2026-03-23
Source of truth: `docker-compose.yml`, `api/app.py`, `api/config.py`, `supabase/init.sql`, `api/alembic/versions/`, `caddy/Caddyfile`, `monitoring/prometheus.yml`

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Service Map](#2-service-map)
3. [Network Topology](#3-network-topology)
4. [Data Flow — Chat Request](#4-data-flow--chat-request)
5. [RAG Pipeline — Document Ingest](#5-rag-pipeline--document-ingest)
6. [Authentication](#6-authentication)
7. [Middleware Stack](#7-middleware-stack)
8. [Observability](#8-observability)
9. [Database Schema](#9-database-schema)
10. [Technology Stack](#10-technology-stack)

---

## 1. System Overview

Manic AI is a self-hosted, full-stack AI platform. It combines a Next.js frontend, a FastAPI backend, local LLM inference via Ollama, hybrid vector search across Qdrant and Supabase/pgvector, and an observability stack built on Prometheus, Grafana, Loki, and Jaeger.

All traffic entering the public internet passes through Caddy, which terminates TLS (including HTTP/3) and routes requests to either the frontend or the API.

```
Internet
    |
    v
+----------+   HTTPS / HTTP3
|  Caddy   |  :80, :443
+----+-----+
     |
     +-----------------------------+
     |                             |
     v                             v
+----------+               +--------------+
| Frontend |               |     API      |
| Next.js  |               |   FastAPI    |
| :3000    |               |   :8081      |
+----------+               +------+-------+
                                  |
          +-----------+-----------+----------+----------+
          |           |           |          |          |
          v           v           v          v          v
      +-------+  +--------+  +--------+  +------+  +----------+
      |Ollama |  | Qdrant |  |  Redis |  |Supa  |  | SearXNG  |
      |:11434 |  |:6333   |  |:6379   |  |base  |  |:8080     |
      +-------+  +--------+  +--------+  | DB   |  +----------+
          |                              |:5432 |
          |                              +------+
          | (optional fallback)
          +------+----------+
          |      |          |
        vLLM  OpenAI  Anthropic
        :8000  (ext)   (ext)
```

Additional platform services (on separate Docker networks) handle workflow automation (n8n), LLM flow building (Flowise), LLM tracing (Langfuse), alternative chat UI (Open WebUI), and an Obsidian vault RAG sidecar (Paddy).

---

## 2. Service Map

All services are defined in `docker-compose.yml` under the project name `manic-ai`.

| Container | Image | Host Port | Internal Port | Network(s) | Purpose |
|---|---|---|---|---|---|
| ai-caddy | caddy:2-alpine | 80, 443 | 80, 443 | app-network | Edge reverse proxy, TLS termination, HTTP/3 |
| manic-ai-frontend | ./frontend (Dockerfile) | 3000 | 3000 | app-network | Next.js 14 UI |
| manic-ai-api | ./api (Dockerfile) | 8081 | 8081 | app-network, db-network, tools-network | FastAPI backend, all AI logic |
| manic-ai-mcp | ./api (Dockerfile) | — | — | app-network, db-network, tools-network | MCP (Model Context Protocol) server |
| ollama | ollama/ollama:0.6.2 | BIND_IP:11434 | 11434 | app-network | Local LLM inference + embedding (GPU) |
| qdrant | qdrant/qdrant:v1.13.2 | BIND_IP:6333, 6334 | 6333, 6334 | app-network | Vector database (ANN search) |
| ai-redis | redis:7-alpine | BIND_IP:6380 | 6379 | db-network | Embedding cache, search cache, rate limit store, MFA tokens |
| ai-redis-exporter | oliver006/redis_exporter:v1.58.0 | BIND_IP:9121 | 9121 | db-network, monitoring-network | Redis metrics for Prometheus |
| ai-supabase-db | supabase/postgres:15.1.1.78 | BIND_IP:5433 | 5432 | db-network | Postgres 15 + pgvector + BM25 (primary datastore) |
| ai-supabase-auth | supabase/gotrue:v2.143.0 | — | 9999 | db-network, app-network | Supabase JWT auth service |
| ai-supabase-rest | postgrest/postgrest:v12.0.1 | — | 3000 | db-network, app-network | Auto-generated REST API over Postgres |
| ai-supabase-meta | supabase/postgres-meta:v0.80.0 | — | 8080 | db-network | Postgres metadata API |
| ai-supabase-storage | supabase/storage-api:v0.46.4 | — | 5000 | db-network, app-network | Object storage (file uploads) |
| ai-supabase-kong | kong:2.8.1 | BIND_IP:8001, 8444 | 8000, 8443 | db-network, app-network | Supabase API gateway |
| ai-supabase-studio | supabase/studio:20240101-8e4a094 | — | 3000 | app-network | Supabase Studio UI |
| ai-studio-auth | nginx:alpine | BIND_IP:3005 | 80 | app-network | Basic-auth proxy in front of Studio |
| ai-n8n | n8nio/n8n:1.81.4 | BIND_IP:5679 | 5678 | tools-network | Workflow automation |
| ai-open-webui | ghcr.io/open-webui/open-webui:v0.8.3 | BIND_IP:3006 | 8080 | tools-network, app-network | Standalone chat UI backed by Ollama |
| ai-searxng | searxng/searxng:2024.11.17 | BIND_IP:8889 | 8080 | tools-network | Self-hosted meta-search engine |
| ai-langfuse | langfuse/langfuse:2 | BIND_IP:3007 | 3000 | db-network, tools-network | LLM observability / prompt tracing |
| ai-langfuse-db | postgres:15-alpine | — | 5432 | db-network | Dedicated Postgres for Langfuse |
| ai-flowise | flowiseai/flowise:2.2.7 | BIND_IP:3008 | 3000 | tools-network | Visual LLM chain builder |
| paddy-agent | ./obsidian-agent (Dockerfile) | BIND_IP:8123 | 8123 | db-network, app-network | Obsidian vault AI agent sidecar |
| paddy-rag-pipeline | ./obsidian-agent/backend_rag_pipeline | — | — | db-network, app-network | Continuous RAG ingestion for Obsidian vault |
| ai-vllm | vllm/vllm-openai:v0.7.3 | BIND_IP:8000 | 8000 | app-network | Production GPU inference (optional, profile: vllm) |
| ai-prometheus | prom/prometheus:v2.51.0 | BIND_IP:9090 | 9090 | monitoring-network, app-network | Metrics collection + alerting rules |
| ai-alertmanager | prom/alertmanager:v0.27.0 | BIND_IP:9093 | 9093 | monitoring-network | Alert routing and deduplication |
| ai-loki | grafana/loki:2.9.4 | BIND_IP:3100 | 3100 | monitoring-network | Log aggregation |
| ai-promtail | grafana/promtail:2.9.4 | — | — | monitoring-network | Log shipping (reads Docker container logs) |
| ai-grafana | grafana/grafana:10.4.0 | BIND_IP:3009 | 3000 | monitoring-network | Dashboards (API overview, host, RAG) |
| ai-cadvisor | gcr.io/cadvisor/cadvisor:v0.49.1 | — | 8080 | monitoring-network | Container resource metrics |
| ai-blackbox-exporter | prom/blackbox-exporter:v0.25.0 | — | 9115 | monitoring-network, app-network | HTTP endpoint probing |
| ai-node-exporter | prom/node-exporter:v1.7.0 | — | 9100 | monitoring-network | Host OS metrics |
| ai-jaeger | jaegertracing/all-in-one:1.54 | BIND_IP:16686, 4317 | 16686, 4317 | monitoring-network, app-network | Distributed tracing (optional, profile: monitoring) |
| ai-backup | python:3.11-slim | — | — | db-network, app-network | Nightly cron: pg_dump + Qdrant snapshot |

Ports exposed on `BIND_IP` (an environment variable) are not reachable from the public internet unless `BIND_IP=0.0.0.0`. In production this should be set to the Tailscale or loopback address.

---

## 3. Network Topology

Docker Compose defines four isolated bridge networks. A container can only communicate with another container if they share at least one network.

```
app-network (bridge)
  caddy, frontend, api, mcp-server, ollama, qdrant,
  supabase-auth, supabase-rest, supabase-storage, supabase-kong,
  supabase-studio, studio-auth, open-webui, prometheus,
  blackbox-exporter, jaeger, paddy-agent, paddy-rag-pipeline,
  backup, vllm

db-network (bridge)
  api, mcp-server, redis, redis-exporter,
  supabase-db, supabase-auth, supabase-rest, supabase-meta,
  supabase-storage, supabase-kong, langfuse-db, langfuse,
  paddy-agent, paddy-rag-pipeline, backup

tools-network (bridge)
  api, mcp-server, n8n, open-webui, searxng,
  langfuse, flowise

monitoring-network (bridge)
  prometheus, alertmanager, loki, promtail, grafana,
  cadvisor, blackbox-exporter, node-exporter, jaeger,
  redis-exporter
```

Key isolation boundaries:

- The database tier (`supabase-db`, `redis`) is not on `app-network`. External services reach them only through the API, which bridges `app-network` and `db-network`.
- Tool services (`n8n`, `flowise`, `searxng`) are not exposed to `db-network` directly; only the API bridges into `tools-network` to call SearXNG for web search.
- The monitoring stack is isolated on `monitoring-network`. Prometheus reaches the API and Qdrant via its secondary membership on `app-network`.
- Jaeger requires the `monitoring` Docker Compose profile to start.
- vLLM requires the `vllm` Docker Compose profile to start.

---

## 4. Data Flow — Chat Request

This traces a single RAG-enabled chat request from the browser through to the streamed response.

```
Browser
  |
  | HTTPS POST /v1/chat
  v
Caddy (TLS termination, security headers)
  |
  | HTTP POST /v1/chat  (plain, internal)
  v
FastAPI middleware pipeline (request path, outer to inner):
  GZip -> RequestSizeLimitMiddleware -> RequestIdMiddleware
  -> SecurityHeadersMiddleware -> GuardrailsMiddleware
  -> PrometheusMiddleware -> MetricsMiddleware -> AuditMiddleware
  |
  | require_api_key (auth dependency)
  v
chat router  ->  chat service
  |
  | 1. generate_embedding(query)
  |       -> Redis cache lookup (key: sha256(model+text))
  |       -> on miss: POST http://ollama:11434/api/embeddings
  |          (bge-m3, 1024-dim, up to 8 concurrent via semaphore)
  |       -> result cached in Redis for 24 h
  v
  | 2. hybrid_search(query_embedding, query_text)
  |       -> SupabaseVectorRepository.hybrid_search()
  |          combines:
  |            - pgvector cosine similarity (HNSW index on rag.chunks)
  |            - BM25 full-text search (GIN tsvector index on rag.chunks)
  |          weighted by RAG_KEYWORD_WEIGHT (default 0.3)
  |          filtered by RAG_THRESHOLD (default 0.7) and RAG_TOP_K (default 5)
  |       optional: QdrantVectorRepository.search() for Qdrant collections
  v
  | 3. rerank_chunks(query, chunks)
  |       -> cross-encoder re-scoring to improve chunk ordering
  v
  | 4. build_rag_prompt(query, context_chunks)
  |       -> injects retrieved content as [Source N] blocks
  |       -> token budget enforced by token_counter service
  |          (truncate_rag_context, truncate_messages_to_budget)
  v
  | 5. chat_completion / chat_completion_stream
  |       -> model_router selects backend from INFERENCE_BACKEND:
  |            "ollama"    -> POST http://ollama:11434/api/chat
  |            "vllm"      -> POST http://ai-vllm:8000/v1/chat/completions
  |            "openai"    -> POST https://api.openai.com/v1/chat/completions
  |            "anthropic" -> POST https://api.anthropic.com/v1/messages
  |          on connection/timeout error, tries MODEL_FALLBACK_CHAIN in order
  |          4xx errors are never retried
  v
  | 6. stream tokens back as SSE (text/event-stream)
  |       -> citations appended at end of stream
  |       -> chat_log row inserted into supabase-db (fire-and-forget)
  |       -> langfuse trace emitted if LANGFUSE_* keys are set
  |       -> OTEL span exported to Jaeger if OTEL_ENABLED=true
  v
FastAPI middleware pipeline (response path, inner to outer):
  AuditMiddleware -> api_key_usage_log insert (asyncio.create_task)
  MetricsMiddleware -> Prometheus counters updated
  PrometheusMiddleware -> /metrics scrape target updated
  SecurityHeadersMiddleware -> X-Frame-Options, CSP, HSTS added
  GZip -> response compressed if >= 500 bytes
  |
  v
Caddy (X-Frame-Options DENY, X-Content-Type-Options, Referrer-Policy)
  |
  v
Browser receives streamed response
```

---

## 5. RAG Pipeline — Document Ingest

This traces a document upload through to queryable vector storage.

```
Client
  |
  | POST /v1/ingest  (multipart file or JSON text/url)
  v
ingest router  ->  ingestion service
  |
  | 1. detect_and_extract (preprocessor service)
  |       Supported types: PDF, DOCX, XLSX, CSV, HTML, plain text, URL fetch
  |       Returns: normalized plain text + metadata
  v
  | 2. redact_pii (pii_detector service)
  |       Active only when PII_REDACTION_ENABLED=true
  |       Redacts: email, phone, SSN, credit card patterns
  v
  | 3. chunk_document (chunking service)
  |       Strategy "simple": character-based, sentence-boundary snapping
  |         chunk_size=500 chars, overlap=50 chars
  |       Strategy "semantic": recursive (markdown headers -> paragraphs -> sentences)
  |         with parent-child chunk pairs for retrieval context
  v
  | 4. enrich_chunks_batch (context_enricher service)
  |       Prepends document-level context to each chunk
  |       (improves embedding quality for short chunks)
  v
  | 5. For each chunk (max EMBEDDING_CONCURRENCY=8 concurrent):
  |       generate_embedding(chunk.content)
  |         -> Redis cache lookup first
  |         -> on miss: POST http://ollama:11434/api/embeddings (bge-m3)
  |         -> cached in Redis for 24 h (EMBEDDING_CACHE_TTL)
  v
  | 6. SupabaseDocumentRepository.create_document()
  |       INSERT INTO rag.documents (id, filename, status, ...)
  |
  | 7. SupabaseDocumentRepository.create_chunks()
  |       INSERT INTO rag.chunks (document_id, chunk_index, content,
  |                               content_tokens, embedding, metadata)
  |       HNSW index automatically updated
  |
  | 8. QdrantVectorRepository.upsert()
  |       Upsert points into Qdrant "documents" collection
  |       Payload includes: document_id, chunk_index, content, metadata
  v
  | 9. Document status updated to "completed" in rag.documents
  |       chunk_count and processing_time_ms recorded
  v
Response: { document_id, chunk_count, status: "completed" }
```

The folder watcher service (`services/folder_watcher.py`) monitors a configured directory and automatically triggers the same ingestion pipeline when new files appear.

The Paddy sidecar (`paddy-rag-pipeline`) runs the same pipeline continuously against a mounted Obsidian vault directory.

---

## 6. Authentication

### Modes

Two modes are selected by the `AUTH_MODE` environment variable.

**Single mode (default, AUTH_MODE=single)**

A single shared `API_SECRET_KEY` is required in every request as either:
- `Authorization: Bearer <key>` header
- `X-API-Key: <key>` header

No per-user tracking occurs in this mode.

**Multi-user mode (AUTH_MODE=multi_user)**

Per-user accounts with individual API keys. The `public.users` table (added by Alembic migration 004) is used.

### User Account Lifecycle

```
POST /auth/register
  -> validate email format
  -> bcrypt hash password (run_in_executor, non-blocking)
  -> generate api_key: "manic_" + secrets.token_urlsafe(32)
  -> store api_key_hash (SHA-256) + api_key_prefix (first 16 chars)
  -> INSERT INTO public.users
  -> key_expires_at = NOW() + 90 days (migration 005)
  -> return { api_key }   (only time the full key is returned)

POST /auth/login
  -> lookup user by email in public.users
  -> bcrypt verify password (run_in_executor)
  -> if mfa_enabled:
       generate mfa_token = secrets.token_urlsafe(32)
       SET Redis key "mfa_token:<mfa_token>" with 300s TTL
       return { mfa_required: true, mfa_token }
  -> if not mfa_enabled:
       return { api_key_prefix, user metadata }

POST /auth/verify-mfa
  -> GET Redis "mfa_token:<token>"
  -> on match: return full api_key for the user
  -> token is single-use (deleted from Redis on use)
```

### API Key Verification (every authenticated request)

```
require_api_key dependency
  -> read key from Authorization header or X-API-Key header
  -> if single mode: compare against API_SECRET_KEY constant
  -> if multi_user mode:
       hash the submitted key with SHA-256
       SELECT from public.users WHERE api_key_hash = $1 OR api_key = $2
         AND is_active = TRUE
         AND (key_expires_at IS NULL OR key_expires_at > NOW())
       attach user dict to request.state.user
  -> AuditMiddleware fires async INSERT into public.api_key_usage_log
```

### Token Expiry and Sessions

- API keys expire after 90 days by default (configurable via `key_expires_at`).
- The `public.user_sessions` table (migration 006) records active sessions with `last_active_at` for session management UIs.
- TOTP secret stored in `users.totp_secret` (migration 006); the current MFA flow uses Redis-backed short-lived tokens rather than TOTP codes — the `totp_secret` column is scaffolded for future TOTP implementation.

---

## 7. Middleware Stack

Middleware is registered in `api/app.py`. In Starlette, the last `add_middleware` call wraps all previous ones, so the outermost layer at runtime is the first to process requests and the last to process responses.

**Request processing order (outermost first):**

```
1. GZipMiddleware              minimum_size=500 bytes; decompresses request body
2. RequestSizeLimitMiddleware  rejects oversized request bodies early
3. RequestIdMiddleware         assigns X-Request-ID if absent; propagates to response
4. SecurityHeadersMiddleware   adds X-Content-Type-Options, X-Frame-Options,
                               Referrer-Policy, HSTS, Content-Security-Policy
5. GuardrailsMiddleware        content safety checks (active when GUARDRAILS_ENABLED=true)
6. PrometheusMiddleware        instruments request counts and latency for /metrics
7. MetricsMiddleware           additional internal metrics tracking
8. AuditMiddleware             fire-and-forget INSERT into api_key_usage_log
                               (runs on response path only, after route handler)
```

**Response processing order** is the reverse: AuditMiddleware fires first (on the way back out), then metrics, then security headers are stamped, then GZip compresses the body.

CORSMiddleware is added before this stack and handles preflight OPTIONS requests directly, before any of the above middleware runs.

Rate limiting is provided by `slowapi` (backed by Redis when available, in-memory fallback). It is applied per-endpoint using decorators in the routers rather than as a global middleware. The key function uses the authenticated user ID when present, otherwise the remote IP address.

---

## 8. Observability

### Prometheus

Scrape interval: 15 seconds. Retention: 30 days.

| Scrape job | Target | What it collects |
|---|---|---|
| manic-ai-api | api:8081/metrics | HTTP request counts, latency histograms, embedding cache hit/miss, ingest document/chunk counters, circuit breaker state |
| cadvisor | cadvisor:8080 | Container CPU, memory, network, disk I/O per container |
| node-exporter | node-exporter:9100 | Host CPU, memory, disk, filesystem, network |
| qdrant | qdrant:6333/metrics | Qdrant collection sizes, search latency, indexing stats |
| redis | ai-redis-exporter:9121 | Redis memory, hit rate, command stats, keyspace |
| blackbox-http | via blackbox-exporter:9115 | HTTP 2xx probe for frontend:3000, api:8081/health, api:8081/health/ready |

Alertmanager is configured at `monitoring/alertmanager.yml` and receives firing alerts from Prometheus rules in `monitoring/alerts/manic-ai.rules.yml`.

### Grafana

Port 3009. Three provisioned dashboards (auto-loaded from `monitoring/grafana/dashboards/`):

- `api-overview.json` — request rate, error rate, p50/p95/p99 latency, endpoint breakdown
- `rag-overview.json` — ingest rate, chunk counts, embedding cache hit rate, search latency
- `host-overview.json` — host CPU, memory, disk from node-exporter

Datasources provisioned automatically: Prometheus (primary), Loki (logs).

### Loki + Promtail

Promtail mounts `/var/lib/docker/containers` and `/var/run/docker.sock` to read container stdout/stderr logs. It ships them to Loki with container name and image labels. Loki stores logs locally at the `loki-data` volume. Log queries are available in Grafana via the Loki datasource.

The API writes structured JSON logs via `api/logging_config.py`. Log level is controlled by `LOG_LEVEL` (default `INFO`).

### Jaeger

Port 16686 (UI), 4317 (OTLP gRPC). Requires Docker Compose profile `monitoring`.

The API enables distributed tracing when `OTEL_ENABLED=true` and `OTEL_EXPORTER_OTLP_ENDPOINT=http://ai-jaeger:4317` (both set in `docker-compose.yml` by default). Spans cover the full request lifecycle including embedding generation, vector search, and LLM inference calls. Storage uses Badger (embedded key-value store) at the `jaeger-data` volume.

### Langfuse

Port 3007. LLM-specific observability: prompt versions, token costs, latency per model, trace/span view for each inference call. The API calls `init_langfuse()` at startup and emits traces when `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set.

### Sentry

Optional error tracking. Enabled by setting `SENTRY_DSN`. Captures unhandled exceptions with `SENTRY_TRACES_SAMPLE_RATE=0.1` (10% transaction sampling) and `send_default_pii=False`.

---

## 9. Database Schema

The database runs on `ai-supabase-db` (Postgres 15 with pgvector). The schema is defined in `supabase/init.sql` (canonical source) and `api/alembic/versions/` (incremental migrations applied by Alembic).

Extensions loaded: `uuid-ossp`, `pgcrypto`, `pg_trgm`, `vector` (pgvector), `pgjwt`, `pg_stat_statements`.

Schemas: `public` (application tables), `rag` (RAG pipeline tables), `auth` (Supabase auth), `storage` (Supabase storage).

### public schema — key tables

**public.users** (migration 004, 005, 006)
```
id               UUID PK
email            TEXT UNIQUE NOT NULL
username         TEXT UNIQUE
password_hash    TEXT NOT NULL
is_active        BOOLEAN DEFAULT TRUE
is_admin         BOOLEAN DEFAULT FALSE
api_key          TEXT UNIQUE          -- plaintext, legacy
api_key_hash     TEXT                 -- SHA-256 of api_key (migration 006)
api_key_prefix   VARCHAR(16)          -- first 16 chars for display (migration 006)
rate_limit_override INTEGER           -- per-user RPM override (NULL = use global)
key_expires_at   TIMESTAMPTZ          -- DEFAULT NOW() + 90 days (migration 005)
totp_secret      TEXT                 -- TOTP seed (migration 006, not yet active)
mfa_enabled      BOOLEAN DEFAULT FALSE
created_at       TIMESTAMPTZ
updated_at       TIMESTAMPTZ
```

**public.user_profiles** (init.sql)
```
id               UUID PK -> auth.users(id)
email            TEXT NOT NULL
full_name        TEXT
avatar_url       TEXT
is_admin         BOOLEAN DEFAULT FALSE
preferences      JSONB DEFAULT '{}'
created_at, updated_at TIMESTAMPTZ
```
Auto-created by trigger `on_auth_user_created` when a row is inserted into `auth.users`.

**public.conversations** (init.sql + migration 005)
```
id               UUID PK
title            TEXT DEFAULT 'New Conversation'
model            TEXT DEFAULT 'llama3.2:3b'
system_prompt    TEXT
user_id          UUID -> public.users(id)  (migration 005)
metadata         JSONB
created_at, updated_at TIMESTAMPTZ
```

**public.messages**
```
id               UUID PK
conversation_id  UUID -> public.conversations(id)
role             TEXT CHECK IN ('user', 'assistant', 'system')
content          TEXT NOT NULL
model            TEXT
tokens_used      INTEGER
latency_ms       INTEGER
metadata         JSONB
created_at       TIMESTAMPTZ
```

**public.agent_conversations**
```
session_id       VARCHAR PK  (format: "<user_uuid>~<session_suffix>")
user_id          UUID -> public.user_profiles(id)
title            VARCHAR
model            TEXT
system_prompt    TEXT
is_archived      BOOLEAN DEFAULT FALSE
last_message_at  TIMESTAMPTZ
```

**public.agent_messages**
```
id                        BIGINT (identity)
session_id                VARCHAR -> public.agent_conversations(session_id)
computed_session_user_id  UUID (generated, extracted from session_id)
role                      TEXT CHECK IN ('system', 'user', 'assistant', 'tool')
content                   TEXT
message_data              JSONB
tokens_used               INTEGER
latency_ms                INTEGER
model_used                TEXT
created_at                TIMESTAMPTZ
```

**public.chat_log** (analytics)
```
id               BIGSERIAL PK
model            TEXT NOT NULL
prompt_tokens    INT
completion_tokens INT
total_tokens     INT
latency_ms       FLOAT
has_rag          BOOLEAN
user_id          UUID -> public.users(id)  (migration 004)
created_at       TIMESTAMPTZ
```

**public.service_health_log** (analytics)
```
id               BIGSERIAL PK
service_name     TEXT NOT NULL
status           TEXT NOT NULL
latency_ms       FLOAT
checked_at       TIMESTAMPTZ
```

**public.api_key_usage_log** (migration 006)
```
id               UUID PK
user_id          UUID -> public.users(id)
api_key_prefix   VARCHAR(16)
endpoint         TEXT
method           VARCHAR(10)
ip_address       INET
user_agent       TEXT
created_at       TIMESTAMPTZ
```

**public.user_sessions** (migration 006)
```
id               UUID PK
user_id          UUID -> public.users(id)
api_key_prefix   VARCHAR(16)
ip_address       INET
user_agent       TEXT
last_active_at   TIMESTAMPTZ
created_at       TIMESTAMPTZ
is_active        BOOLEAN DEFAULT TRUE
```

**public.usage_logs**
```
id               UUID PK
conversation_id  UUID -> public.conversations(id)
model            TEXT NOT NULL
endpoint         TEXT DEFAULT 'chat'
input_tokens     INTEGER
output_tokens    INTEGER
total_tokens     INTEGER (generated: input + output)
latency_ms       INTEGER
created_at       TIMESTAMPTZ
```

**public.requests**
```
id               UUID PK
user_id          UUID -> public.user_profiles(id)
endpoint         TEXT
method           TEXT
user_query       TEXT NOT NULL
response_status  INTEGER
latency_ms       INTEGER
metadata         JSONB
created_at       TIMESTAMPTZ
```

**public.prompts** (prompt templates)
```
id               UUID PK
name             TEXT NOT NULL
description      TEXT
prompt_text      TEXT NOT NULL
category         TEXT DEFAULT 'general'
is_favorite      BOOLEAN DEFAULT FALSE
metadata         JSONB
created_at, updated_at TIMESTAMPTZ
```

**public.documents** (legacy, backward-compat)
```
id               BIGSERIAL PK
content          TEXT
metadata         JSONB
embedding        VECTOR(1024)
```
Retained for backward compatibility. New ingestion writes to `rag.documents` / `rag.chunks`.

### rag schema — key tables

**rag.documents**
```
id               UUID PK
user_id          UUID
filename         TEXT NOT NULL
content_type     TEXT
file_size        BIGINT
source_url       TEXT
status           TEXT CHECK IN ('pending','processing','completed','failed')
error_message    TEXT
chunk_count      INTEGER DEFAULT 0
processing_time_ms INTEGER
raw_content      TEXT        -- full original document text
metadata         JSONB
created_at, updated_at TIMESTAMPTZ
```

**rag.chunks** (primary vector storage)
```
id               UUID PK
document_id      UUID -> rag.documents(id)
chunk_index      INTEGER NOT NULL
content          TEXT NOT NULL
content_tokens   INTEGER
embedding        VECTOR(1024)    -- bge-m3 1024-dim vectors
metadata         JSONB
created_at       TIMESTAMPTZ
```
Indexes: HNSW cosine (m=16, ef_construction=64), GIN tsvector (English FTS), GIN trigram (pg_trgm), GIN on metadata.

**rag.collections**
```
id               UUID PK
user_id          UUID
name             TEXT NOT NULL
description      TEXT
is_public        BOOLEAN DEFAULT FALSE
embedding_model  TEXT DEFAULT 'nomic-embed-text'
metadata         JSONB
created_at, updated_at TIMESTAMPTZ
```

**rag.document_collections** (many-to-many join)
```
document_id      UUID -> rag.documents(id)  PK
collection_id    UUID -> rag.collections(id) PK
added_at         TIMESTAMPTZ
```

**rag.conversations**
```
id               UUID PK
user_id          UUID
collection_id    UUID -> rag.collections(id)
title            TEXT
model            TEXT DEFAULT 'llama3.2:3b'
system_prompt    TEXT
temperature      FLOAT DEFAULT 0.7
max_tokens       INTEGER DEFAULT 2048
metadata         JSONB
created_at, updated_at TIMESTAMPTZ
```

**rag.messages**
```
id               UUID PK
conversation_id  UUID -> rag.conversations(id)
role             TEXT CHECK IN ('system','user','assistant','tool')
content          TEXT NOT NULL
tokens_used      INTEGER
latency_ms       INTEGER
model_used       TEXT
citations        JSONB DEFAULT '[]'   -- structured Citation objects
metadata         JSONB
created_at       TIMESTAMPTZ
```

### Stored functions

| Function | Schema | Purpose |
|---|---|---|
| match_documents | public | Legacy cosine similarity search over public.documents |
| get_conversation_with_messages | public | Returns conversation + aggregated messages as JSON |
| get_usage_stats | public | Aggregate token/latency/model stats over N days |
| get_rag_stats | public | Count documents, chunks, collections |
| rag.search_similar_chunks | rag | Pure vector ANN search over rag.chunks |
| update_updated_at | public | Trigger function: sets updated_at = NOW() |
| handle_new_user | public | Trigger function: auto-creates user_profiles row on auth.users insert |
| is_admin | public | Returns TRUE if auth.uid() has is_admin flag |

---

## 10. Technology Stack

| Layer | Component | Version |
|---|---|---|
| Edge proxy | Caddy | 2-alpine |
| Frontend framework | Next.js | 14 |
| Frontend language | TypeScript | — |
| Frontend state management | Zustand | — |
| Frontend styling | Tailwind CSS | — |
| Backend framework | FastAPI | — |
| Backend language | Python | 3.11 |
| Backend server | Uvicorn | — |
| Rate limiting | slowapi | — |
| Database | PostgreSQL | 15.1.1.78 (Supabase image) |
| Vector extension | pgvector | bundled with Supabase Postgres |
| Vector database | Qdrant | v1.13.2 |
| Cache / rate-limit store | Redis | 7-alpine |
| Auth service | Supabase GoTrue | v2.143.0 |
| REST API generation | PostgREST | v12.0.1 |
| API gateway (Supabase) | Kong | 2.8.1 |
| Local LLM inference | Ollama | 0.6.2 |
| Default chat model | llama3.2:3b | configurable via CHAT_MODEL |
| Default embedding model | bge-m3 | 1024-dim; configurable via EMBEDDING_MODEL |
| Optional inference backend | vLLM | v0.7.3 (profile: vllm) |
| LLM tracing | Langfuse | v2 |
| Metrics | Prometheus | v2.51.0 |
| Alerting | Alertmanager | v0.27.0 |
| Dashboards | Grafana | 10.4.0 |
| Log aggregation | Loki | 2.9.4 |
| Log shipping | Promtail | 2.9.4 |
| Container metrics | cAdvisor | v0.49.1 |
| Host metrics | node-exporter | v1.7.0 |
| HTTP probing | blackbox-exporter | v0.25.0 |
| Redis metrics | redis-exporter | v1.58.0 |
| Distributed tracing | Jaeger (all-in-one) | 1.54 |
| Workflow automation | n8n | 1.81.4 |
| LLM chain builder | Flowise | 2.2.7 |
| Self-hosted search | SearXNG | 2024.11.17 |
| Alternative chat UI | Open WebUI | v0.8.3 |
| Password hashing | bcrypt | — |
| DB migrations | Alembic | — |
| Error tracking | Sentry SDK | optional, via SENTRY_DSN |
| MCP protocol | custom (api/mcp_main.py) | — |
| Obsidian agent | Paddy (custom) | — |

## Network Overview
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          TAILSCALE VPN                                       │
│                       IP: 100.111.244.124                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              VPS SERVER                                      │
│                         ~/Manic-AI (Docker)                                  │
│                        Network: ai-network                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Service Map (18 Containers)

### Layer 1: USER INTERFACES
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FRONTENDS & UIs                                    │
├─────────────────┬─────────────────┬─────────────────┬───────────────────────┤
│   Manic AI      │   Open WebUI    │    SearXNG      │   Supabase Studio     │
│   Frontend      │   (Chat UI)     │   (Search)      │   (DB Admin)          │
│   :3000         │   :3006         │   :8889         │   :3005               │
│   Next.js       │   Python        │   Python        │   via nginx auth      │
└────────┬────────┴────────┬────────┴────────┬────────┴──────────┬────────────┘
         │                 │                 │                   │
         ▼                 ▼                 ▼                   ▼
```

### Layer 2: API & AUTOMATION
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        APIs & WORKFLOW ENGINES                               │
├─────────────────┬─────────────────┬─────────────────┬───────────────────────┤
│   Manic AI      │      n8n        │    Flowise      │    Langfuse           │
│   API           │   (Workflows)   │   (LLM Flows)   │   (LLM Tracing)       │
│   :8081         │   :5679         │   :3008         │   :3007               │
│   FastAPI       │   Node.js       │   Node.js       │   Next.js             │
│                 │   AUTH: ✓       │   AUTH: ✓       │                       │
└────────┬────────┴────────┬────────┴────────┬────────┴──────────┬────────────┘
         │                 │                 │                   │
         ▼                 ▼                 ▼                   ▼
```

### Layer 3: AI & INFERENCE
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          AI INFERENCE                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                            OLLAMA                                            │
│                           :11434                                             │
│                         Memory: 8GB                                          │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  Models:                                                              │   │
│  │  • llama3.2:3b (default chat)                                        │   │
│  │  • nomic-embed-text (embeddings - 768 dim)                           │   │
│  │  • deepseek-coder:6.7b (coding) [pending]                            │   │
│  │  • llama3.1:8b (larger chat) [pending]                               │   │
│  │  • mistral:7b (general) [pending]                                    │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Layer 4: VECTOR DATABASES (Dual RAG)
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       VECTOR STORAGE (RAG)                                   │
├────────────────────────────────────┬────────────────────────────────────────┤
│           SUPABASE                 │              QDRANT                     │
│      (pgvector + BM25)             │        (Pure Vector)                    │
│           :5433                    │         :6333 / :6334                   │
├────────────────────────────────────┼────────────────────────────────────────┤
│  • Hybrid search (vector + text)   │  • High-performance vector search      │
│  • SQL queries                     │  • Filtering & payloads                │
│  • Full-text search                │  • Collections API                     │
│  • HNSW index                      │  • REST + gRPC                         │
└────────────────────────────────────┴────────────────────────────────────────┘
```

### Layer 5: DATABASES & CACHING
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DATA LAYER                                            │
├─────────────────┬─────────────────┬─────────────────────────────────────────┤
│  Supabase DB    │   Langfuse DB   │              Redis                       │
│  (PostgreSQL)   │   (PostgreSQL)  │            (Cache)                       │
│  :5433          │   (internal)    │             :6380                        │
│  2GB            │   512MB         │             256MB                        │
├─────────────────┴─────────────────┴─────────────────────────────────────────┤
│  Supabase DB Schemas:                                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  public.*                      │  rag.*                              │    │
│  │  • conversations               │  • documents                        │    │
│  │  • messages                    │  • chunks (768-dim vectors)         │    │
│  │  • prompts                     │  • collections                      │    │
│  │  • usage_logs                  │  • document_collections             │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│  RLS: ENABLED on all tables                                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Layer 6: SUPABASE INTERNAL SERVICES
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     SUPABASE STACK (Internal)                                │
├─────────────────┬─────────────────┬─────────────────┬───────────────────────┤
│   Kong          │   PostgREST     │   GoTrue        │   Storage API         │
│   (Gateway)     │   (REST API)    │   (Auth)        │   (Files)             │
│   :8001         │   (internal)    │   (internal)    │   (internal)          │
├─────────────────┴─────────────────┴─────────────────┼───────────────────────┤
│   Postgres-Meta (internal)                          │   Studio (internal)   │
│   Schema inspection                                 │   → nginx :3005       │
└─────────────────────────────────────────────────────┴───────────────────────┘
```

---

## Data Flow Diagrams

### 1. Chat Flow
```
User → Frontend(:3000) → API(:8081) → Ollama(:11434) → Response
                              │
                              ├─→ Supabase DB (save conversation)
                              └─→ Langfuse (trace/log)
```

### 2. RAG Flow (Document Ingestion)
```
Document → API(:8081) → Ollama (embed) ─┬─→ Supabase pgvector
                                        └─→ Qdrant (optional)
```

### 3. RAG Flow (Query)
```
Query → API(:8081) → Ollama (embed query)
                          │
            ┌─────────────┼─────────────┐
            ▼             ▼             ▼
        Supabase       Qdrant        Both
      (hybrid search) (vector)    (unified)
            │             │             │
            └─────────────┴─────────────┘
                          │
                          ▼
              Ollama (generate with context)
                          │
                          ▼
                      Response
```

### 4. Automation Flow
```
Trigger → n8n(:5679) ─┬─→ API(:8081)
                      ├─→ Ollama(:11434)
                      ├─→ Supabase(:8001)
                      └─→ External Services
```

---

## Port Reference (Quick Draw)

```
┌─────────────────────────────────────────────────────────────────┐
│                    100.111.244.124:PORT                          │
├──────────┬──────────────────────────────────────────────────────┤
│   3000   │  Manic AI Frontend (Next.js)                         │
│   3005   │  Supabase Studio (nginx auth)                        │
│   3006   │  Open WebUI (Chat)                                   │
│   3007   │  Langfuse (LLM Observability)                        │
│   3008   │  Flowise (Visual LLM Builder)                        │
│   5433   │  PostgreSQL (Supabase DB)                            │
│   5679   │  n8n (Workflow Automation)                           │
│   6333   │  Qdrant REST API                                     │
│   6334   │  Qdrant gRPC                                         │
│   6380   │  Redis                                               │
│   8001   │  Supabase Kong API Gateway                           │
│   8081   │  Manic AI API (FastAPI)                              │
│   8889   │  SearXNG (Search)                                    │
│  11434   │  Ollama (LLM Inference)                              │
└──────────┴──────────────────────────────────────────────────────┘
```

---

## Container Dependency Graph

```
                    ┌─────────────┐
                    │ supabase-db │ (healthcheck)
                    └──────┬──────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│ supabase-auth │  │ supabase-rest │  │supabase-storage│
└───────────────┘  └───────────────┘  └───────────────┘
                           │
                           ▼
                   ┌───────────────┐
                   │ supabase-meta │
                   └───────┬───────┘
                           │
                           ▼
                   ┌───────────────┐     ┌───────────────┐
                   │supabase-studio│────▶│  studio-auth  │
                   └───────────────┘     └───────────────┘

┌─────────┐                              ┌─────────────┐
│ ollama  │ (healthcheck)                │ langfuse-db │
└────┬────┘                              └──────┬──────┘
     │                                          │
     │    ┌──────────────────────────┐          ▼
     └───▶│         api              │   ┌─────────────┐
          │ (depends: db + ollama)   │   │   langfuse  │
          └────────────┬─────────────┘   └─────────────┘
                       │
                       ▼
               ┌───────────────┐
               │   frontend    │
               └───────────────┘

Standalone (no dependencies):
┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐
│ qdrant  │  │  redis  │  │   n8n   │  │ flowise │  │ searxng │
└─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘
            ┌───────────┐
            │ open-webui│ (uses ollama URL, not depends_on)
            └───────────┘
```

---

## Memory Allocation (Total: ~20GB recommended)

```
┌─────────────────────────────────────────────────────────────────┐
│  Service          │  Limit  │  Notes                            │
├───────────────────┼─────────┼───────────────────────────────────┤
│  Ollama           │   8 GB  │  LLM inference                    │
│  Supabase DB      │   2 GB  │  PostgreSQL + pgvector            │
│  Qdrant           │   2 GB  │  Vector database                  │
│  Open WebUI       │   2 GB  │  Chat interface                   │
│  API              │   1 GB  │  FastAPI                          │
│  n8n              │   1 GB  │  Workflows                        │
│  Langfuse         │   1 GB  │  Observability                    │
│  Flowise          │   1 GB  │  LLM builder                      │
│  Frontend         │ 512 MB  │  Next.js                          │
│  Redis            │ 512 MB  │  Cache (256MB data limit)         │
│  Langfuse DB      │ 512 MB  │  PostgreSQL                       │
│  SearXNG          │ 512 MB  │  Search                           │
├───────────────────┼─────────┼───────────────────────────────────┤
│  TOTAL            │ ~20 GB  │                                   │
└───────────────────┴─────────┴───────────────────────────────────┘
```

---

## Volume Persistence (10 volumes)

```
┌─────────────────────────────────────────────────────────────────┐
│  Volume Name              │  Container        │  Purpose         │
├───────────────────────────┼───────────────────┼──────────────────┤
│  ollama-data              │  ollama           │  LLM models      │
│  qdrant-data              │  qdrant           │  Vector data     │
│  redis-data               │  ai-redis         │  Cache           │
│  supabase-db-data         │  ai-supabase-db   │  PostgreSQL      │
│  supabase-storage-data    │  ai-supabase-stor │  File uploads    │
│  n8n-data                 │  ai-n8n           │  Workflows       │
│  open-webui-data          │  ai-open-webui    │  Chat history    │
│  langfuse-db-data         │  ai-langfuse-db   │  Traces          │
│  flowise-data             │  ai-flowise       │  Flows           │
└───────────────────────────┴───────────────────┴──────────────────┘
```

---

## Quick Reference Box (Draw This!)

```
╔══════════════════════════════════════════════════════════════════╗
║                    MANIC AI QUICK REFERENCE                       ║
╠══════════════════════════════════════════════════════════════════╣
║  Tailscale IP: 100.111.244.124                                   ║
║  Network: ai-network (Docker bridge)                             ║
║  Containers: 18                                                  ║
║  Volumes: 10                                                     ║
╠══════════════════════════════════════════════════════════════════╣
║  KEY URLS:                                                       ║
║  • Chat:      :3000 (frontend) or :3006 (Open WebUI)            ║
║  • API:       :8081                                              ║
║  • Database:  :3005 (Studio) or :5433 (direct)                  ║
║  • Workflows: :5679 (n8n)                                        ║
║  • LLM:       :11434 (Ollama)                                    ║
╠══════════════════════════════════════════════════════════════════╣
║  LOGINS:                                                         ║
║  • n8n: markvitale21@gmail.com / L0c4Linf0$                     ║
║  • Supabase Studio: check .htpasswd                              ║
║  • Flowise: admin / [see .env FLOWISE_PASSWORD]                  ║
╚══════════════════════════════════════════════════════════════════╝
```

---

## Whiteboard Drawing Tips

1. **Start with 3 horizontal layers:**
   - Top: User-facing UIs (green boxes)
   - Middle: APIs & Processing (blue boxes)
   - Bottom: Data stores (yellow boxes)

2. **Draw Ollama BIG** - it's the AI brain, center it

3. **Show the dual RAG** - two paths from API to Supabase and Qdrant

4. **Circle the Supabase stack** - 8 containers work together

5. **Add port numbers** - they're the "addresses"

6. **Draw arrows for data flow** - especially the chat and RAG flows
