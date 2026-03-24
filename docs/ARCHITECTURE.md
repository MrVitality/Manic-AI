# Manic AI Architecture Reference

Source of truth: `docker-compose.yml`, `api/app.py`, `api/config.py`, `caddy/Caddyfile`, `monitoring/prometheus.yml`

---

## System Overview

```
                         ┌─────────────────────────────────────────┐
                         │              Internet / Clients          │
                         └──────────────────┬──────────────────────┘
                                            │ HTTPS :443 (HTTP/3 on UDP)
                         ┌──────────────────▼──────────────────────┐
                         │          Caddy (ai-caddy)               │
                         │  Auto-TLS via Let's Encrypt             │
                         │  Routes by path prefix                  │
                         └────────────┬──────────────┬─────────────┘
                                      │              │
                      ┌───────────────▼──┐   ┌───────▼─────────────┐
                      │   Frontend       │   │   FastAPI API        │
                      │   Next.js :3000  │   │   (manic-ai-api)     │
                      │   (SSR + React)  │   │   :8081              │
                      └──────────────────┘   └──────────┬──────────┘
                                                        │
              ┌──────────────────────────────┬──────────┼──────────────────┐
              │                              │          │                  │
   ┌──────────▼──────┐         ┌─────────────▼──┐  ┌───▼────────┐  ┌──────▼──────┐
   │  Supabase Stack  │         │  Ollama :11434  │  │  Qdrant    │  │   Redis     │
   │  Postgres :5433  │         │  LLM inference  │  │  :6333     │  │   :6380     │
   │  PostgREST       │         │  + Embeddings   │  │  Vector DB │  │   Cache +   │
   │  GoTrue (Auth)   │         └─────────────────┘  └────────────┘  │   Rate limit│
   │  Storage API     │                                               └─────────────┘
   │  Kong (gateway)  │
   └──────────────────┘
```

---

## Service Map

All services are defined in `docker-compose.yml` and run on a set of internal Docker networks.

### Core Application Services

| Container | Image | Internal Port | External Port | Purpose |
|-----------|-------|---------------|---------------|---------|
| `ai-caddy` | `caddy:2-alpine` | — | 80, 443, 443/udp | Reverse proxy, TLS termination, HTTP/3 |
| `manic-ai-api` | Built from `./api` | 8081 | `BIND_IP:8081` | FastAPI backend |
| `manic-ai-frontend` | Built from `./frontend` | 3000 | `BIND_IP:3000` | Next.js frontend |
| `manic-ai-mcp` | Built from `./api` | — | — | MCP server (`api.mcp_main`) |

### AI Inference

| Container | Image | External Port | Purpose |
|-----------|-------|---------------|---------|
| `ollama` | `ollama/ollama:0.6.2` | `BIND_IP:11434` | Local LLM inference + embeddings (BGE-M3, LLaMA, etc.) |
| `qdrant` | `qdrant/qdrant:v1.13.2` | `BIND_IP:6333`, `BIND_IP:6334` | Vector database (HTTP + gRPC) |

### Supabase Stack

| Container | Image | External Port | Purpose |
|-----------|-------|---------------|---------|
| `ai-supabase-db` | `supabase/postgres:15.1.1.78` | `BIND_IP:5433` | PostgreSQL 15 with pgvector |
| `ai-supabase-auth` | `supabase/gotrue:v2.143.0` | — | JWT auth service |
| `ai-supabase-rest` | `postgrest/postgrest:v12.0.1` | — | Auto-generated REST API over Postgres |
| `ai-supabase-meta` | `supabase/postgres-meta:v0.80.0` | — | DB schema introspection |
| `ai-supabase-storage` | `supabase/storage-api:v0.46.4` | — | File storage API |
| `ai-supabase-kong` | `kong:2.8.1` | `BIND_IP:8001`, `BIND_IP:8444` | API gateway for Supabase services |
| `ai-supabase-studio` | `supabase/studio` | — | Supabase Studio UI |
| `ai-studio-auth` | `nginx:alpine` | `BIND_IP:3005` | Basic-auth proxy for Studio |

### Infrastructure

| Container | Image | External Port | Purpose |
|-----------|-------|---------------|---------|
| `ai-redis` | `redis:7-alpine` | `BIND_IP:6380` | Cache, rate limiting, MFA token store |
| `ai-redis-exporter` | `oliver006/redis_exporter:v1.58.0` | `BIND_IP:9121` | Redis metrics for Prometheus |

### Tools & Integrations

| Container | Image | External Port | Purpose |
|-----------|-------|---------------|---------|
| `ai-open-webui` | `ghcr.io/open-webui/open-webui:v0.8.3` | `BIND_IP:3006` | Chat UI connected directly to Ollama |
| `ai-searxng` | `searxng/searxng:2024.11.17` | `BIND_IP:8889` | Self-hosted federated search |
| `ai-n8n` | `n8nio/n8n:1.81.4` | `BIND_IP:5679` | Workflow automation |
| `ai-flowise` | `flowiseai/flowise:2.2.7` | `BIND_IP:3008` | Visual LLM flow builder |
| `ai-langfuse` | `langfuse/langfuse:2` | `BIND_IP:3007` | LLM tracing and observability |
| `ai-langfuse-db` | `postgres:15-alpine` | — | Dedicated DB for Langfuse |
| `paddy-agent` | Built from `./obsidian-agent` | `BIND_IP:8123` | Obsidian vault AI agent |
| `paddy-rag-pipeline` | Built from `./obsidian-agent/backend_rag_pipeline` | — | Continuous RAG ingestion from vault |

### Monitoring Stack (optional profile)

| Container | Purpose |
|-----------|---------|
| `ai-prometheus` | Metrics collection (scrapes every 15s) |
| `ai-grafana` | Dashboard UI |
| `ai-alertmanager` | Alert routing |
| `ai-loki` | Log aggregation |
| `ai-promtail` | Log shipper |
| `cadvisor` | Container resource metrics |
| `node-exporter` | Host OS metrics |
| `ai-blackbox-exporter` | Endpoint availability probing |
| `ai-jaeger` | Distributed tracing (OTLP receiver) |

---

## Network Topology

Docker Compose defines three internal networks to restrict lateral movement:

| Network | Connected services |
|---------|-------------------|
| `app-network` | caddy, api, frontend, supabase-auth, supabase-rest, supabase-storage, supabase-kong, open-webui, paddy-agent |
| `db-network` | api, supabase-db, supabase-auth, supabase-rest, supabase-meta, supabase-storage, supabase-kong, redis, redis-exporter, langfuse, langfuse-db |
| `tools-network` | api, n8n, open-webui, searxng, flowise |
| `monitoring-network` | prometheus, grafana, alertmanager, cadvisor, node-exporter, redis-exporter |

The API container bridges `app-network`, `db-network`, and `tools-network` because it needs to reach all service tiers.

---

## Caddy Routing

Configured in `caddy/Caddyfile`. Routes by path prefix to either the frontend or the API:

| Path prefix | Upstream |
|-------------|---------|
| `/v1/*` | `api:8081` |
| `/health*` | `api:8081` |
| `/metrics` | `api:8081` |
| `/ws/*` | `api:8081` |
| `/services/*` | `api:8081` |
| `/auth/*` | `api:8081` |
| `/chat*`, `/dashboard*`, `/settings*`, `/admin*`, etc. | `frontend:3000` |
| `/_next/*` | `frontend:3000` |
| everything else | `frontend:3000` |

Security headers applied by Caddy: `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy`, server header removed.

---

## Data Flow

### Chat Request Path (with RAG)

```
Client
  │ POST /v1/chat { messages, use_rag: true }
  ▼
Caddy (TLS termination)
  │ forward to api:8081
  ▼
API Middleware stack (in order):
  GZip → RequestSizeLimit → RequestId → SecurityHeaders
  → Guardrails (prompt injection scan) → Prometheus → Metrics → Audit
  │
  ▼
require_api_key (auth dependency)
  │ single mode: compare X-API-Key to API_SECRET_KEY
  │ multi_user: look up key in users table, set request.state.user
  ▼
chat.router → services/chat.py → services/rag.py
  │
  ├─ generate_embedding(last user message) → Ollama BGE-M3
  │
  ├─ unified_search(query_embedding, query_text, backend=supabase)
  │     ├─ pgvector cosine similarity search (Supabase DB)
  │     ├─ BM25 keyword search (Supabase DB)
  │     └─ optional: cross-encoder reranking
  │
  ├─ Build context string from top-K chunks
  │
  └─ model_router.chat_completion(messages + context, model)
        ├─ Ollama (default)
        ├─ vLLM (if VLLM_URL set)
        ├─ OpenAI (if OPENAI_API_KEY set)
        └─ Anthropic (if ANTHROPIC_API_KEY set)
             │ fallback chain: MODEL_FALLBACK_CHAIN env var
             ▼
           LLM response → Langfuse trace
  │
  ▼
JSON response with citations
```

### Document Ingestion Pipeline

```
POST /v1/ingest (async)
  │
  ▼
Background task:
  1. Extract text (preprocessor handles .docx, .pdf, .html, etc.)
  2. Chunk document (simple fixed-size or semantic sentence-aware)
  3. Optional: LLM context enrichment per chunk (enrich_context=true)
  4. Batch generate embeddings → Ollama BGE-M3
     (up to EMBEDDING_CONCURRENCY=8 concurrent requests)
  5. Embedding results cached in Redis (24h TTL)
  6. Store chunks + vectors:
     - Supabase: INSERT into document_chunks with vector column
     - Qdrant: upsert points into collection
  7. Update ingest job status → "completed" or "failed"
```

---

## Auth Flow

### Single-User Mode (`AUTH_MODE=single`)

```
Client → X-API-Key: <API_SECRET_KEY>
API → hmac.compare_digest(key, API_SECRET_KEY)
    → pass (request.state.user = None)
```

### Multi-User Mode (`AUTH_MODE=multi_user`)

```
1. Registration: POST /auth/register → creates user row, generates manic_<token> API key
2. Login: POST /auth/login → validate bcrypt hash → return API key (or mfa_token)
3. Subsequent requests:
   Client → X-API-Key: manic_<token>
   API → SELECT from users WHERE api_key = $1 AND is_active = TRUE
       → set request.state.user = { id, email, is_admin, rate_limit_override, ... }
```

### MFA Flow

```
1. POST /auth/mfa/setup → generate pyotp TOTP secret, store in users.totp_secret
2. POST /auth/mfa/verify → validate TOTP code, set users.mfa_enabled = TRUE
3. At login:
   POST /auth/login → mfa_required: true, mfa_token stored in Redis (TTL 5 min)
   POST /auth/mfa/validate → validate TOTP, consume mfa_token from Redis, return API key
```

---

## Middleware Stack

Middlewares are applied in the following order (outermost on request, innermost on response):

| Middleware | Purpose |
|-----------|---------|
| `GZipMiddleware` | Compress responses ≥ 500 bytes |
| `RequestSizeLimitMiddleware` | Reject oversized request bodies |
| `RequestIdMiddleware` | Add `X-Request-ID` to every request/response |
| `SecurityHeadersMiddleware` | Add HSTS, CSP, X-Frame-Options, etc. |
| `GuardrailsMiddleware` | Scan chat/search/agent request bodies for prompt injection patterns |
| `PrometheusMiddleware` | Increment Prometheus counters per route |
| `MetricsMiddleware` | Track request duration and write to internal metrics store |
| `AuditMiddleware` | Log every mutation (POST/PUT/PATCH/DELETE) to audit log |
| `CORSMiddleware` | CORS with configurable origins from `CORS_ORIGINS` env var |
| `SlowAPI (Limiter)` | Per-user (or per-IP) rate limiting backed by Redis |

---

## Observability Stack

### Prometheus Scrape Targets

| Job | Target | Metrics |
|-----|--------|---------|
| `manic-ai-api` | `api:8081/metrics` | FastAPI request counts, latencies, error rates |
| `cadvisor` | `cadvisor:8080` | Container CPU/memory/network/disk |
| `node-exporter` | `node-exporter:9100` | Host OS metrics |
| `qdrant` | `qdrant:6333/metrics` | Qdrant collection stats |
| `redis` | `ai-redis-exporter:9121` | Redis memory, ops/sec, keyspace |
| `blackbox-http` | Frontend + API health endpoints | HTTP response time, availability |

### Distributed Tracing

OpenTelemetry tracing is enabled when `OTEL_ENABLED=true`. The API sends OTLP traces to Jaeger at `OTEL_EXPORTER_OTLP_ENDPOINT`. In the default Docker Compose setup, the API container has `OTEL_ENABLED=true` and sends to `http://ai-jaeger:4317`.

### Langfuse LLM Tracing

When `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set, every LLM call (chat, embedding, agent) is traced in Langfuse, including token counts, model name, latency, and prompt/completion content.

---

## Database Schema Overview

The primary database is PostgreSQL 15 with the `pgvector` extension. Schema is initialized by `supabase/init.sql` and managed by Alembic migrations in `api/alembic/`.

**Key tables:**

| Table | Description |
|-------|-------------|
| `public.users` | User accounts: id, email, api_key, totp_secret, mfa_enabled, is_admin, is_active, rate_limit_override |
| `public.documents` | Ingested document metadata: id, filename, content_type, status, chunks_created, user_id, collection_id, content_hash |
| `public.document_chunks` | Individual text chunks with `vector(1024)` column for pgvector similarity search |
| `public.collections` | Named groups for organizing documents |
| `public.conversations` | Chat sessions: id, title, system_prompt, metadata JSONB (contains user_id) |
| `public.messages` | Individual messages: id, conversation_id, role, content, model, tokens_used |
| `public.ingest_jobs` | Async ingestion job tracker: document_id, status, chunks_created, error |
| `public.feedback` | User ratings on chat responses |
| `public.search_logs` | Logged search queries for analytics |
| `public.service_health_logs` | Historical service availability snapshots |
| `public.audit_logs` | Mutation audit trail |

Qdrant stores vector embeddings separately as collections of points, with each point carrying a payload referencing the `document_id` and chunk metadata.

---

## Configuration Reference

All configuration is loaded from environment variables (and optionally a `.env` file) via `api/config.py` using Pydantic Settings.

### Required Variables

| Variable | Description |
|----------|-------------|
| `SUPABASE_DB_URL` | PostgreSQL connection string: `postgresql://user:pass@host:5432/db` |
| `API_SECRET_KEY` | Shared API key (single mode) or signing key (multi_user mode) |
| `QDRANT_API_KEY` | Qdrant authentication key |
| `SEARXNG_SECRET_KEY` | SearXNG instance secret |

### Key Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_URL` | `http://ollama:11434` | Ollama endpoint |
| `REDIS_URL` | `redis://ai-redis:6379` | Redis connection |
| `QDRANT_URL` | `http://qdrant:6333` | Qdrant endpoint |
| `SEARXNG_URL` | `http://ai-searxng:8080` | SearXNG endpoint |
| `CHAT_MODEL` | `llama3.2:3b` | Default LLM |
| `EMBEDDING_MODEL` | `bge-m3` | Embedding model (1024-dim) |
| `VECTOR_DIMENSION` | `1024` | Must match the embedding model |
| `INFERENCE_BACKEND` | `ollama` | `ollama`, `vllm`, `openai`, `anthropic` |
| `AUTH_MODE` | `single` | `single` or `multi_user` |
| `RAG_TOP_K` | `5` | Default retrieval count |
| `RAG_THRESHOLD` | `0.7` | Minimum similarity score |
| `LANGFUSE_PUBLIC_KEY` | — | Enable Langfuse tracing |
| `LANGFUSE_SECRET_KEY` | — | Enable Langfuse tracing |
| `CORS_ORIGINS` | — | Comma-separated allowed origins |
| `OTEL_ENABLED` | `false` | Enable OpenTelemetry |
| `SENTRY_DSN` | — | Enable Sentry error tracking |
| `LOG_LEVEL` | `INFO` | Python log level |
