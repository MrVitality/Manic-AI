# Manic AI API Reference

**Version:** 2.0.0
**Base URL:** `http://<host>:8081`
**Versioned prefix:** `/v1` (all authenticated endpoints)

---

## Authentication

All `/v1/` endpoints require `X-API-Key: <key>` in the request header.

Auth endpoints (`/auth/*`) and health endpoints (`/health`, `/health/ready`) are public — no key needed.

**Auth modes** (set via `AUTH_MODE` env var):

| Mode | Behaviour |
|------|-----------|
| `single` (default) | One shared `API_SECRET_KEY` accepted for all requests |
| `multi_user` | Per-user keys issued at login; key resolves to a specific user record |

---

## Response Envelope

All endpoints return a standard JSON envelope:

```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "meta": { "total": 100, "limit": 50, "offset": 0 }
}
```

On error:

```json
{
  "success": false,
  "data": null,
  "error": { "code": "VALIDATION_ERROR", "message": "...", "details": [...] },
  "meta": null
}
```

---

## Rate Limits (defaults, overridable per-user by admin)

| Endpoint group | Default limit |
|---------------|---------------|
| Chat / Search | 60 req/min |
| Ingest | 10 req/min |
| Mutations (delete, pull, etc.) | 30 req/min |
| Agent | 20 req/min |
| Auth | 3–5 req/min |

Rate limiting uses Redis as a shared store so limits apply consistently across multiple API instances. Falls back to in-memory if Redis is unavailable.

---

## Quick Reference

| Method | Path | Auth | Group |
|--------|------|------|-------|
| POST | `/auth/login` | No | Auth |
| POST | `/auth/register` | No | Auth |
| POST | `/auth/mfa/setup` | Key | Auth |
| POST | `/auth/mfa/verify` | Key | Auth |
| POST | `/auth/mfa/validate` | No | Auth |
| POST | `/auth/rotate-key` | Key | Auth |
| POST | `/auth/logout` | Key | Auth |
| POST | `/v1/chat` | Key | Chat |
| POST | `/v1/chat/stream` | Key | Chat |
| POST | `/v1/chat/completions` | Key | OpenAI-compat |
| GET | `/v1/models` (OpenAI format) | Key | OpenAI-compat |
| POST | `/v1/search` | Key | Search |
| POST | `/v1/search/explain` | Key | Search |
| POST | `/v1/embed` | Key | Ingest |
| POST | `/v1/ingest` | Key | Ingest |
| POST | `/v1/ingest/upload` | Key | Ingest |
| GET | `/v1/ingest/{id}/status` | Key | Ingest |
| POST | `/v1/ingest/pii-scan` | Key | Ingest |
| POST | `/v1/ingest/preview-chunks` | Key | Ingest |
| GET | `/v1/documents` | Key | Documents |
| DELETE | `/v1/documents/{id}` | Key | Documents |
| GET | `/v1/documents/{id}/chunks` | Key | Documents |
| GET | `/v1/collections` | Key | Collections |
| POST | `/v1/collections` | Key | Collections |
| DELETE | `/v1/collections/{id}` | Key | Collections |
| GET | `/v1/conversations` | Key | Conversations |
| POST | `/v1/conversations` | Key | Conversations |
| GET | `/v1/conversations/{id}` | Key | Conversations |
| PATCH | `/v1/conversations/{id}` | Key | Conversations |
| DELETE | `/v1/conversations/{id}` | Key | Conversations |
| POST | `/v1/conversations/{id}/messages` | Key | Conversations |
| POST | `/v1/agent/run` | Key | Agent |
| POST | `/v1/agent/stream` | Key | Agent |
| GET | `/v1/agent/{run_id}/status` | Key | Agent |
| POST | `/v1/eval/run` | Key | Eval |
| POST | `/v1/eval/batch` | Key | Eval |
| GET | `/v1/eval/search-history` | Key | Eval |
| POST | `/v1/feedback` | Key | Feedback |
| GET | `/v1/feedback/stats` | Key | Feedback |
| GET | `/v1/analytics/usage` | Key | Analytics |
| GET | `/v1/analytics/models` | Key | Analytics |
| GET | `/v1/analytics/rag` | Key | Analytics |
| GET | `/v1/analytics/services/history` | Key | Analytics |
| GET | `/v1/system/info` | Key | System |
| POST | `/v1/system/cache/clear` | Key | System |
| GET | `/v1/rag/stats` | Key | System |
| GET | `/v1/models` | Key | Models |
| GET | `/v1/api/tags` | Key | Models |
| POST | `/v1/models/pull` | Key | Models |
| DELETE | `/v1/models/{name}` | Key | Models |
| GET | `/v1/plugins` | Key | Plugins |
| POST | `/v1/plugins/{tool_name}/run` | Key | Plugins |
| GET | `/v1/qdrant/collections` | Key | Qdrant |
| POST | `/v1/qdrant/collections/{name}` | Key | Qdrant |
| GET | `/v1/qdrant/collections/{name}` | Key | Qdrant |
| GET | `/v1/admin/users` | Admin | Admin |
| GET | `/v1/admin/users/{id}` | Admin | Admin |
| POST | `/v1/admin/users` | Admin | Admin |
| PATCH | `/v1/admin/users/{id}` | Admin | Admin |
| DELETE | `/v1/admin/users/{id}` | Admin | Admin |
| GET | `/v1/admin/stats` | Admin | Admin |
| GET | `/health` | No | Health |
| GET | `/health/ready` | No | Health |
| GET | `/services/status` | Key | Health |
| GET | `/services/status/stream` | Key | Health |
| WS | `/ws/status` | Token | Health |
| GET | `/metrics` | No | Health |

---

## Auth Endpoints

All auth endpoints are mounted at the root (not under `/v1/`).

### POST /auth/login

Authenticate with email and password. Returns an API key on success.

If MFA is enabled on the account, returns `mfa_required: true` and an `mfa_token` instead. The client must complete the flow via `/auth/mfa/validate`.

Rate limited to **5/minute**.

**Request:**
```json
{ "email": "user@example.com", "password": "secret" }
```

**Response (no MFA):**
```json
{
  "success": true,
  "data": { "api_key": "manic_abc123...", "user_id": "uuid", "email": "user@example.com" }
}
```

**Response (MFA required):**
```json
{
  "success": true,
  "data": { "mfa_required": true, "mfa_token": "token", "user_id": "uuid", "email": "user@example.com" }
}
```

**Errors:** 401 Invalid credentials (constant-time response to prevent user enumeration)

---

### POST /auth/register

Create a new user account. Only available when `AUTH_MODE=multi_user`. Rate limited to **3/minute**.

**Request:**
```json
{ "email": "user@example.com", "password": "secret", "display_name": "Alice" }
```

**Response (201):**
```json
{ "success": true, "data": { "message": "Account created", "api_key": "manic_..." } }
```

**Errors:** 404 (not in multi_user mode), 409 (email already registered)

---

### POST /auth/mfa/setup

Generate a TOTP secret and QR-code provisioning URI. Requires an authenticated API key. Call this before `/auth/mfa/verify`.

Rate limited to **5/minute**.

**Response:**
```json
{
  "success": true,
  "data": { "totp_secret": "BASE32SECRET", "provisioning_uri": "otpauth://totp/..." }
}
```

---

### POST /auth/mfa/verify

Verify a TOTP code and activate MFA on the account. Must have called `/auth/mfa/setup` first.

**Request:**
```json
{ "code": "123456" }
```

---

### POST /auth/mfa/validate

Exchange an `mfa_token` (from `/auth/login`) and TOTP code for the actual API key. The token is single-use.

Rate limited to **10/minute**.

**Request:**
```json
{ "mfa_token": "token-from-login", "code": "123456" }
```

**Response:** Same as `/auth/login` success (api_key, user_id, email).

---

### POST /auth/rotate-key

Generate a new API key, immediately invalidating the old one. Rate limited to **3/minute**.

**Response:**
```json
{ "success": true, "data": { "api_key": "manic_new...", "expires_at": "2026-06-21T00:00:00" } }
```

---

### POST /auth/logout

Invalidate the current API key by replacing it with a random value that is not returned to the client.

**Response:**
```json
{ "success": true, "data": { "message": "Logged out. Previous API key is now invalid." } }
```

---

## Chat Endpoints

### POST /v1/chat

Synchronous chat completion with optional RAG context retrieval.

**Request:**
```json
{
  "messages": [{ "role": "user", "content": "Explain transformers" }],
  "model": "llama3.2:3b",
  "temperature": 0.7,
  "max_tokens": 2048,
  "use_rag": true,
  "collection_id": "uuid-optional",
  "rerank": false,
  "context_window": null
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `messages` | array | required | Up to 200 messages. Roles: `user`, `assistant`, `system`. Content max 100 000 chars each. |
| `model` | string | config `CHAT_MODEL` | Ollama model name |
| `temperature` | float | 0.7 | Sampling temperature |
| `max_tokens` | int | 2048 | Max tokens to generate |
| `use_rag` | bool | false | Retrieve context from vector store before generating |
| `collection_id` | string | null | Scope RAG retrieval to this collection |
| `rerank` | bool | false | Apply cross-encoder reranking to retrieved chunks |
| `context_window` | int | null | Override `RAG_CONTEXT_WINDOW` for this request |

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "chat-uuid",
    "model": "llama3.2:3b",
    "message": { "role": "assistant", "content": "Transformers are..." },
    "sources": [...],
    "citations": [
      {
        "source_id": "chunk-uuid",
        "document_id": "doc-uuid",
        "chunk_index": 3,
        "content_preview": "First 200 chars of chunk...",
        "score": 0.92
      }
    ],
    "usage": { "prompt_tokens": 120, "completion_tokens": 80 }
  }
}
```

---

### POST /v1/chat/stream

Same as `/v1/chat` but streams the response as `text/event-stream` SSE. Each event is a JSON delta.

---

## OpenAI-Compatible Endpoints

Drop-in replacements for OpenAI's API. Any client that works with OpenAI (LangChain, OpenAI SDK, etc.) connects without modification.

### POST /v1/chat/completions

**Request:**
```json
{
  "model": "llama3.2:3b",
  "messages": [{ "role": "user", "content": "Hello" }],
  "stream": false,
  "temperature": 0.7,
  "max_tokens": 512
}
```

**Response (non-streaming):**
```json
{
  "id": "chatcmpl-uuid",
  "object": "chat.completion",
  "created": 1700000000,
  "model": "llama3.2:3b",
  "choices": [{
    "index": 0,
    "message": { "role": "assistant", "content": "Hi there!" },
    "finish_reason": "stop"
  }],
  "usage": { "prompt_tokens": 5, "completion_tokens": 4, "total_tokens": 9 }
}
```

When `stream: true`, returns SSE with `chat.completion.chunk` objects terminated by `data: [DONE]`.

### GET /v1/models (OpenAI format)

Returns Ollama models in OpenAI list format:

```json
{ "object": "list", "data": [{ "id": "llama3.2:3b", "object": "model", "owned_by": "ollama" }] }
```

---

## Search Endpoints

### POST /v1/search

Unified hybrid search combining vector similarity (pgvector or Qdrant) and BM25 keyword matching.

In `multi_user` mode, the authenticated user's ID is enforced for tenant isolation regardless of what the client submits in the body.

**Request:**
```json
{
  "query": "machine learning fundamentals",
  "top_k": 5,
  "threshold": 0.7,
  "use_hybrid": true,
  "backend": "supabase",
  "collection_id": null,
  "rerank": false,
  "use_mmr": false,
  "mmr_lambda": 0.7
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `query` | string | required | Search query text |
| `top_k` | int | 5 | Number of results |
| `threshold` | float | 0.7 | Minimum similarity score (0–1) |
| `use_hybrid` | bool | true | Combine vector + BM25 scores |
| `backend` | string | `supabase` | `supabase`, `qdrant`, or `both` |
| `collection_id` | string | null | Scope to a specific collection |
| `rerank` | bool | false | Apply cross-encoder reranking |
| `use_mmr` | bool | false | Maximal Marginal Relevance for diversity |
| `mmr_lambda` | float | 0.7 | MMR tradeoff: 1.0 = pure similarity, 0.0 = pure diversity |

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": "chunk-uuid",
      "document_id": "doc-uuid",
      "content": "Relevant text chunk...",
      "metadata": { "filename": "guide.pdf", "chunk_index": 3 },
      "score": 0.89
    }
  ]
}
```

---

### POST /v1/search/explain

Same as `/v1/search` but returns a detailed scoring breakdown for debugging relevance. Accepts an additional `include_vectors: true` field to return raw embedding vectors alongside scores.

---

## Ingest Endpoints

### POST /v1/embed

Generate a vector embedding for a text string.

**Request:**
```json
{ "text": "Hello world", "model": "bge-m3" }
```

**Response:**
```json
{
  "success": true,
  "data": { "embedding": [0.012, -0.034, ...], "model": "bge-m3", "dimensions": 1024 }
}
```

---

### POST /v1/ingest

Submit a document for asynchronous ingestion. Returns immediately with a `document_id`. Poll `/v1/ingest/{id}/status` for completion.

When `multimodal: true` and `content_type: "application/pdf"`, the ColPali-style pipeline converts pages to images, describes them via a vision LLM, and embeds those descriptions.

Rate limited to **10/minute**.

**Request:**
```json
{
  "content": "Document text or base64-encoded PDF bytes",
  "filename": "report.pdf",
  "content_type": "application/pdf",
  "backend": "both",
  "chunk_size": 500,
  "chunk_overlap": 50,
  "chunking_strategy": "simple",
  "collection_id": null,
  "metadata": { "author": "Alice" },
  "enrich_context": false,
  "multimodal": false
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `content` | string | required | Document text (max 10 MB) or base64 PDF |
| `filename` | string | required | Original filename (max 255 chars) |
| `content_type` | string | `text/plain` | MIME type |
| `backend` | string | `both` | `supabase`, `qdrant`, or `both` |
| `chunk_size` | int | 500 | Characters per chunk (simple strategy) or token target (semantic) |
| `chunk_overlap` | int | 50 | Character overlap between chunks |
| `chunking_strategy` | string | `simple` | `simple` or `semantic` |
| `enrich_context` | bool | false | Add an LLM-generated context summary to each chunk before embedding |
| `multimodal` | bool | false | Use vision LLM pipeline for PDF pages |

**Response (202):**
```json
{ "success": true, "data": { "document_id": "uuid", "status": "processing" } }
```

---

### POST /v1/ingest/upload

Multipart file upload alternative to `/v1/ingest`. Supported types: `.txt`, `.md`, `.html`, `.htm`, `.docx`, `.pdf`. Detects duplicate files by SHA-256 hash and returns `status: duplicate` without reprocessing.

**Form fields:** `file` (required), `collection_id`, `backend` (default `supabase`), `user_id`

**Response (202):**
```json
{ "success": true, "data": { "document_id": "uuid", "status": "processing" } }
```

Duplicate detection response:
```json
{ "success": true, "data": { "document_id": "existing-uuid", "status": "duplicate", "chunks_created": 0 } }
```

---

### GET /v1/ingest/{document_id}/status

Poll the status of an async ingestion job. Checks the database first, falls back to an in-memory tracker.

**Response:**
```json
{
  "success": true,
  "data": {
    "document_id": "uuid",
    "status": "completed",
    "filename": "report.pdf",
    "chunks_created": 42,
    "error": null,
    "created_at": "2026-03-23T10:00:00Z",
    "updated_at": "2026-03-23T10:00:05Z"
  }
}
```

Status values: `pending`, `processing`, `completed`, `failed`

---

### POST /v1/ingest/pii-scan

Scan text for PII without storing anything. Returns entity types and character offsets. Raw PII values are not echoed back.

**Request:**
```json
{ "content": "My email is alice@example.com and SSN is 123-45-6789" }
```

**Response:**
```json
{
  "success": true,
  "data": {
    "entities": [
      { "entity_type": "EMAIL", "start": 12, "end": 29 },
      { "entity_type": "SSN", "start": 43, "end": 54 }
    ],
    "total_found": 2
  }
}
```

---

### POST /v1/ingest/preview-chunks

Preview how a document would be chunked without persisting anything. Use this to tune `chunk_size` and `overlap` before committing an ingestion.

**Request:**
```json
{ "content": "Long document text...", "strategy": "simple", "chunk_size": 500, "overlap": 50 }
```

**Response:**
```json
{
  "success": true,
  "data": { "strategy": "simple", "chunk_count": 8, "chunks": [{ "index": 0, "content": "..." }] }
}
```

---

## Documents Endpoints

### GET /v1/documents

List documents with optional filtering and pagination.

**Query parameters:**
- `user_id` — filter by owner
- `collection_id` — filter by collection
- `status` — filter by ingest status
- `limit` (default 50, max 500)
- `offset` (default 0)

**Response:**
```json
{ "success": true, "data": [...], "meta": { "total": 120, "limit": 50, "offset": 0 } }
```

---

### DELETE /v1/documents/{document_id}

Delete a document and its chunks from all backends (Supabase + Qdrant). Returns 404 for non-existent documents or documents owned by another user (prevents IDOR enumeration).

**Response:**
```json
{ "success": true, "data": { "status": "deleted", "document_id": "uuid" } }
```

---

### GET /v1/documents/{document_id}/chunks

Retrieve all stored chunks for a document with their metadata.

---

## Collections Endpoints

### GET /v1/collections

List collections. In `multi_user` mode, scoped to the authenticated user.

**Query parameters:** `user_id`, `limit` (max 500), `offset`

---

### POST /v1/collections

Create a collection for organizing documents.

**Request:**
```json
{ "name": "ML Papers", "description": "Machine learning research", "is_public": false }
```

**Response:**
```json
{ "success": true, "data": { "id": "uuid", "name": "ML Papers", "status": "created" } }
```

---

### DELETE /v1/collections/{collection_id}

Delete a collection. Returns 404 if not found.

---

## Conversations Endpoints

### GET /v1/conversations

List conversations, ordered by most-recently-updated. Scoped to the authenticated user in `multi_user` mode.

**Query parameters:** `user_id`, `limit` (max 200), `offset`

---

### POST /v1/conversations

Create a new conversation.

**Request:**
```json
{ "title": "Chat about RAG", "system_prompt": "You are a helpful assistant.", "user_id": null }
```

**Response:** Full conversation object (id, title, system_prompt, metadata, created_at, updated_at).

---

### GET /v1/conversations/{conversation_id}

Fetch a conversation with all its messages ordered by creation time. Enforces ownership in `multi_user` mode (returns 404 for other users' conversations).

---

### PATCH /v1/conversations/{conversation_id}

Update `title` and/or `system_prompt`. At least one field must be provided.

**Request:**
```json
{ "title": "Updated title" }
```

---

### DELETE /v1/conversations/{conversation_id}

Delete a conversation and all its messages (FK cascade in the database).

---

### POST /v1/conversations/{conversation_id}/messages

Append a message to a conversation. Also updates `conversation.updated_at` to keep the list ordering accurate.

**Request:**
```json
{ "role": "user", "content": "What is RAG?" }
```

Roles: `user`, `assistant`, `system`

**Response:** The created message object (id, conversation_id, role, content, model, tokens_used, created_at).

---

## Agent Endpoints

### POST /v1/agent/run

Execute a Generator-Critic reasoning loop. The agent generates an answer, critiques it internally, and refines over multiple iterations before returning.

Rate limited to **20/minute**.

**Request:**
```json
{ "query": "Explain the differences between BM25 and vector search", "model": null }
```

**Response:**
```json
{ "success": true, "data": { "run_id": "uuid", "answer": "...", "iterations": 3, "steps": [...] } }
```

---

### POST /v1/agent/stream

Same as `/v1/agent/run` but streams each reasoning step as SSE. Useful for showing the reasoning process in a UI.

---

### GET /v1/agent/{run_id}/status

Check the status of a previous agent run by ID. Returns the full run state.

---

## Eval Endpoints

### POST /v1/eval/run

Run a single RAG evaluation: search for a query and compare retrieved chunk IDs against a ground truth set. Returns precision, recall, F1, and score distribution.

**Request:**
```json
{
  "query": "What is HNSW?",
  "relevant_chunk_ids": ["chunk-uuid-1", "chunk-uuid-2"],
  "top_k": 5,
  "backend": "supabase",
  "use_hybrid": true,
  "rerank": false
}
```

---

### POST /v1/eval/batch

Run up to 50 test cases in parallel. Returns per-query metrics and aggregate scores.

---

### GET /v1/eval/search-history

Retrieve logged search queries with their result counts and latencies for analytics.

---

## Feedback Endpoints

### POST /v1/feedback

Submit user feedback on a chat response.

**Request:**
```json
{
  "rating": 1,
  "comment": "Accurate and concise",
  "conversation_id": "uuid",
  "message_id": "uuid",
  "query_text": "What is RAG?",
  "response_text": "RAG stands for...",
  "had_rag": true
}
```

`rating`: `-1` (thumbs down), `0` (neutral), `1` (thumbs up)

---

### GET /v1/feedback/stats

Return aggregate feedback statistics: rating distribution, average rating, percentage with RAG.

---

## Analytics Endpoints

All analytics endpoints are cached in Redis with a **60-second TTL** (services history: 30 seconds).

### GET /v1/analytics/usage

**Query parameters:** `period` (`hour`, `day`, `week`, `month`), `model`

Returns request counts, token usage, latency percentiles, and error rates for the selected period.

---

### GET /v1/analytics/models

Returns model usage breakdown: requests per model, average latency, total tokens.

---

### GET /v1/analytics/rag

Returns RAG pipeline metrics: retrieval hit rate, average similarity scores, chunk usage frequency.

---

### GET /v1/analytics/services/history

**Query parameters:** `service` (filter by service name), `hours` (1–168, default 24)

Returns service availability history for the monitoring dashboard.

---

## System Endpoints

### GET /v1/system/info

Returns API version, uptime in seconds, active configuration values, and database connection pool statistics.

**Response:**
```json
{
  "success": true,
  "data": {
    "version": "2.0.0",
    "uptime_seconds": 3600.0,
    "start_time": "2026-03-23T09:00:00Z",
    "config": {
      "chat_model": "llama3.2:3b",
      "embedding_model": "bge-m3",
      "vector_dimension": 1024,
      "rag_top_k": 5,
      "rag_threshold": 0.7
    },
    "database": { "pool_size": 10, "pool_free": 8 }
  }
}
```

---

### POST /v1/system/cache/clear

Flush all Redis cache keys matching the `manic:*` pattern.

**Response:**
```json
{ "success": true, "data": { "cleared": true, "keys_removed": 42 } }
```

---

### GET /v1/rag/stats

Returns document and chunk counts, storage bytes, embedding model info, index type, per-filetype document counts, and the 10 most recent ingestion events.

---

## Models Endpoints

### GET /v1/models

List models available on the Ollama instance with metadata (name, size, digest, modified date).

### GET /v1/api/tags

Compatibility alias for `/v1/models`.

### POST /v1/models/pull

Pull a model from the Ollama registry. Streams download progress as SSE. Rate limited to **30/minute**.

**Request:**
```json
{ "name": "llama3.2:3b" }
```

### DELETE /v1/models/{name}

Delete a model from Ollama. Rate limited to **30/minute**.

---

## Plugins Endpoints

### GET /v1/plugins

List all installed plugins and their registered tool names.

**Response:**
```json
{ "success": true, "data": { "tools": ["web_search", "calculator"], "count": 2 } }
```

### POST /v1/plugins/{tool_name}/run

Execute a plugin tool. Both sync and async tools are supported.

**Request:**
```json
{ "arguments": { "query": "latest AI news" } }
```

**Response:**
```json
{ "success": true, "data": { "tool": "web_search", "result": { ... } } }
```

**Errors:** 404 tool not found, 422 invalid arguments

---

## Qdrant Endpoints

Direct access to Qdrant vector database operations.

### GET /v1/qdrant/collections

List all collections in Qdrant.

### POST /v1/qdrant/collections/{collection_name}

Create a Qdrant collection. Collection name must match `^[a-zA-Z0-9_\-]{1,64}$`.

**Query parameters:** `vector_size` (default: `VECTOR_DIMENSION` config value)

### GET /v1/qdrant/collections/{collection_name}

Get details (point count, config) for a specific collection.

---

## Admin Endpoints

All admin endpoints require an API key belonging to a user with `is_admin = true`. Non-admin callers receive 403.

### GET /v1/admin/users

List all users (paginated). API keys are masked in the response.

**Query parameters:** `limit` (max 200), `offset`

---

### GET /v1/admin/users/{user_id}

Fetch a single user by UUID.

---

### POST /v1/admin/users

Create a new user account with an auto-generated API key.

**Request:**
```json
{ "email": "new@example.com", "password": "securepassword", "username": "alice", "is_admin": false }
```

**Errors:** 409 email/username already exists

---

### PATCH /v1/admin/users/{user_id}

Partially update a user. Only fields present in the body are modified.

**Request:**
```json
{ "is_active": true, "is_admin": false, "rate_limit_override": 120, "username": "alice2" }
```

---

### DELETE /v1/admin/users/{user_id}

Soft-delete a user by setting `is_active = false`. Account and data are retained; the user cannot authenticate until re-activated via PATCH.

---

### GET /v1/admin/stats

Return system-wide aggregate statistics: total/active users, admin count, chat request count, search count, feedback summary.

---

## Health Endpoints

Health endpoints are mounted at the root (not under `/v1/`).

### GET /health

Basic liveness check. Cached for 5 seconds.

**Response:**
```json
{ "success": true, "data": { "status": "healthy", "timestamp": "2026-03-23T10:00:00Z" } }
```

---

### GET /health/ready

Readiness probe. Returns 200 when PostgreSQL and Redis are reachable, 503 otherwise. Used by load balancers and orchestrators to gate traffic.

---

### GET /services/status

Check all downstream services and return latency per service. Requires authentication.

**Response:**
```json
{
  "success": true,
  "data": {
    "timestamp": "2026-03-23T10:00:00Z",
    "services": {
      "ollama": { "name": "Ollama", "status": "healthy", "latency_ms": 12.3 },
      "database": { "name": "PostgreSQL", "status": "healthy", "latency_ms": 1.5 },
      "qdrant": { "name": "Qdrant", "status": "healthy", "latency_ms": 5.0 },
      "searxng": { "name": "SearXNG", "status": "healthy", "latency_ms": 8.1 },
      "langfuse": { "name": "Langfuse", "status": "healthy", "latency_ms": 15.0 }
    }
  }
}
```

---

### GET /services/status/stream

Server-Sent Events stream of service status, polled every 10 seconds. Requires authentication.

---

### WS /ws/status

WebSocket for real-time service status. Sends a full snapshot every 10 seconds.

When `API_SECRET_KEY` is configured, pass `?token=<key>` in the query string; connection is rejected with code 1008 if the token is missing or invalid.

Client can send `"ping"` to receive `{"type": "pong"}`.

---

### GET /metrics

Prometheus metrics in text exposition format. Not included in the OpenAPI schema.

---

## Error Reference

| HTTP Status | Meaning |
|-------------|---------|
| 400 | Validation error or bad request |
| 401 | Missing or invalid API key |
| 403 | Admin access required |
| 404 | Resource not found (also used for IDOR prevention) |
| 409 | Conflict (duplicate email, username, etc.) |
| 415 | Unsupported media type (file upload) |
| 422 | Request body schema validation failed |
| 429 | Rate limit exceeded |
| 502 | Upstream service (Ollama, Qdrant, etc.) unavailable |
| 503 | Service not ready (readiness probe failure) |
