# Manic AI API Reference

**Version:** 2.0.0
**Base URL:** `http://localhost:8081`
**Versioned prefix:** `/v1` (all authenticated endpoints)

---

## Table of Contents

1. [Authentication](#authentication)
2. [Response Envelope](#response-envelope)
3. [Rate Limits](#rate-limits)
4. [Quick Reference Table](#quick-reference-table)
5. [Auth Endpoints](#auth-endpoints)
6. [Chat Endpoints](#chat-endpoints)
7. [Search Endpoints](#search-endpoints)
8. [Ingest Endpoints](#ingest-endpoints)
9. [Documents Endpoints](#documents-endpoints)
10. [Collections Endpoints](#collections-endpoints)
11. [Conversations Endpoints](#conversations-endpoints)
12. [Admin Endpoints](#admin-endpoints)
13. [Health Endpoints](#health-endpoints)
14. [Analytics Endpoints](#analytics-endpoints)
15. [Qdrant Endpoints](#qdrant-endpoints)
16. [System Endpoints](#system-endpoints)
17. [Models Endpoints](#models-endpoints)
18. [Agent Endpoints](#agent-endpoints)
19. [Eval Endpoints](#eval-endpoints)
20. [Feedback Endpoints](#feedback-endpoints)
21. [Plugins Endpoints](#plugins-endpoints)
22. [OpenAI-Compatible Endpoints](#openai-compatible-endpoints)
23. [Error Reference](#error-reference)

---

## Authentication

All endpoints under `/v1/` require authentication via the `X-API-Key` header. Auth endpoints (`/auth/*`) and health endpoints are public.

```
X-API-Key: manic_<your-api-key>
```

**Auth modes:**

| Mode | Description |
|------|-------------|
| `single` | One shared `API_SECRET_KEY` for all requests (default) |
| `multi_user` | Per-user API keys issued via login; `X-API-Key` is resolved to a specific user |

Admin endpoints additionally require the authenticated user to have `is_admin = true`.

---

## Response Envelope

Every endpoint returns a consistent JSON envelope:

```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "meta": null
}
```

On error:

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable description",
    "details": [
      { "field": "query", "message": "field required", "code": "missing" }
    ]
  },
  "meta": null
}
```

Paginated responses include a `meta` object:

```json
{
  "meta": { "total": 142, "limit": 50, "offset": 0 }
}
```

---

## Rate Limits

Rate limits are applied per IP address via slowapi. Default values from `config.py`:

| Limit class | Default |
|-------------|---------|
| General (`RATE_LIMIT_PER_MINUTE`) | 60 req/min |
| Ingest (`RATE_LIMIT_INGEST_PER_MINUTE`) | 10 req/min |
| Mutations (`RATE_LIMIT_MUTATIONS_PER_MINUTE`) | 30 req/min |
| Agent (`RATE_LIMIT_AGENT_PER_MINUTE`) | 20 req/min |
| Auth login | 5 req/min (hardcoded) |
| Auth register | 3 req/min (hardcoded) |
| Auth MFA setup/verify | 5 req/min (hardcoded) |
| Auth MFA validate | 10 req/min (hardcoded) |
| Auth rotate-key | 3 req/min (hardcoded) |

When a rate limit is exceeded the API returns HTTP 429.

---

## Quick Reference Table

| Method | Path | Auth | Section |
|--------|------|------|---------|
| POST | `/auth/login` | None | Auth |
| POST | `/auth/register` | None | Auth |
| POST | `/auth/logout` | API Key | Auth |
| POST | `/auth/rotate-key` | API Key | Auth |
| POST | `/auth/mfa/setup` | API Key | Auth |
| POST | `/auth/mfa/verify` | API Key | Auth |
| POST | `/auth/mfa/validate` | None | Auth |
| POST | `/v1/chat` | API Key | Chat |
| POST | `/v1/chat/stream` | API Key | Chat |
| POST | `/v1/search` | API Key | Search |
| POST | `/v1/search/explain` | API Key | Search |
| POST | `/v1/embed` | API Key | Ingest |
| POST | `/v1/ingest` | API Key | Ingest |
| POST | `/v1/ingest/upload` | API Key | Ingest |
| GET | `/v1/ingest/{document_id}/status` | API Key | Ingest |
| POST | `/v1/ingest/pii-scan` | API Key | Ingest |
| POST | `/v1/ingest/preview-chunks` | API Key | Ingest |
| GET | `/v1/documents` | API Key | Documents |
| DELETE | `/v1/documents/{document_id}` | API Key | Documents |
| GET | `/v1/documents/{document_id}/chunks` | API Key | Documents |
| GET | `/v1/collections` | API Key | Collections |
| POST | `/v1/collections` | API Key | Collections |
| DELETE | `/v1/collections/{collection_id}` | API Key | Collections |
| GET | `/v1/conversations` | API Key | Conversations |
| POST | `/v1/conversations` | API Key | Conversations |
| GET | `/v1/conversations/{conversation_id}` | API Key | Conversations |
| PATCH | `/v1/conversations/{conversation_id}` | API Key | Conversations |
| DELETE | `/v1/conversations/{conversation_id}` | API Key | Conversations |
| POST | `/v1/conversations/{conversation_id}/messages` | API Key | Conversations |
| GET | `/v1/admin/users` | Admin | Admin |
| POST | `/v1/admin/users` | Admin | Admin |
| GET | `/v1/admin/users/{user_id}` | Admin | Admin |
| PATCH | `/v1/admin/users/{user_id}` | Admin | Admin |
| DELETE | `/v1/admin/users/{user_id}` | Admin | Admin |
| GET | `/v1/admin/stats` | Admin | Admin |
| GET | `/health` | None | Health |
| GET | `/health/ready` | None | Health |
| GET | `/services/status` | API Key | Health |
| GET | `/services/status/stream` | API Key | Health |
| WS | `/ws/status` | Token (optional) | Health |
| GET | `/v1/analytics/usage` | API Key | Analytics |
| GET | `/v1/analytics/models` | API Key | Analytics |
| GET | `/v1/analytics/rag` | API Key | Analytics |
| GET | `/v1/analytics/services/history` | API Key | Analytics |
| GET | `/v1/qdrant/collections` | API Key | Qdrant |
| POST | `/v1/qdrant/collections/{collection_name}` | API Key | Qdrant |
| GET | `/v1/qdrant/collections/{collection_name}` | API Key | Qdrant |
| DELETE | `/v1/qdrant/collections/{collection_name}` | API Key | Qdrant |
| POST | `/v1/qdrant/search/{collection_name}` | API Key | Qdrant |
| GET | `/v1/system/info` | API Key | System |
| POST | `/v1/system/cache/clear` | API Key | System |
| GET | `/v1/rag/stats` | API Key | System |
| GET | `/v1/models` | API Key | Models |
| GET | `/v1/api/tags` | API Key | Models |
| POST | `/v1/models/pull` | API Key | Models |
| DELETE | `/v1/models/{name}` | API Key | Models |
| POST | `/v1/agent/run` | API Key | Agent |
| GET | `/v1/agent/{run_id}/status` | API Key | Agent |
| POST | `/v1/agent/stream` | API Key | Agent |
| POST | `/v1/eval/run` | API Key | Eval |
| POST | `/v1/eval/batch` | API Key | Eval |
| GET | `/v1/eval/search-history` | API Key | Eval |
| POST | `/v1/feedback` | API Key | Feedback |
| GET | `/v1/feedback/stats` | API Key | Feedback |
| GET | `/v1/plugins` | API Key | Plugins |
| POST | `/v1/plugins/{tool_name}/run` | API Key | Plugins |
| POST | `/v1/chat/completions` | API Key | OpenAI-Compat |
| GET | `/v1/models` | API Key | OpenAI-Compat |

---

## Auth Endpoints

Auth routes are mounted at the root (no `/v1/` prefix) so clients can obtain an API key without needing one first.

---

### POST /auth/login

Authenticate with email and password to obtain an API key.

**Auth required:** None
**Rate limit:** 5 req/min

**Request body:**

```json
{
  "email": "user@example.com",
  "password": "s3cr3t"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `email` | string (email) | Yes | Registered email address |
| `password` | string | Yes | Account password |

**Response (200 — standard login):**

```json
{
  "success": true,
  "data": {
    "api_key": "manic_abc123...",
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "user@example.com"
  },
  "error": null,
  "meta": null
}
```

**Response (200 — MFA required):**

```json
{
  "success": true,
  "data": {
    "mfa_required": true,
    "mfa_token": "tok_xyz...",
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "user@example.com"
  },
  "error": null,
  "meta": null
}
```

When `mfa_required` is `true`, exchange the `mfa_token` at `POST /auth/mfa/validate`.

**Error responses:**

| Status | Description |
|--------|-------------|
| 401 | Invalid email or password |
| 429 | Rate limit exceeded |

---

### POST /auth/register

Create a new user account. Only available when `AUTH_MODE=multi_user`.

**Auth required:** None
**Rate limit:** 3 req/min

**Request body:**

```json
{
  "email": "newuser@example.com",
  "password": "str0ngP@ss",
  "display_name": "Alice"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `email` | string (email) | Yes | New account email |
| `password` | string | Yes | Account password |
| `display_name` | string | No | Optional display name |

**Response (201):**

```json
{
  "success": true,
  "data": {
    "message": "Account created",
    "api_key": "manic_abc123..."
  },
  "error": null,
  "meta": null
}
```

**Error responses:**

| Status | Description |
|--------|-------------|
| 400 | Invalid email format or password validation failed |
| 404 | Endpoint not available (AUTH_MODE is not multi_user) |
| 409 | Email address already registered |

---

### POST /auth/logout

Invalidate the current API key. The key is replaced with a new random value that is not returned to the caller.

**Auth required:** API Key
**Rate limit:** None

**Request body:** None

**Response (200):**

```json
{
  "success": true,
  "data": { "message": "Logged out. Previous API key is now invalid." },
  "error": null,
  "meta": null
}
```

**Error responses:**

| Status | Description |
|--------|-------------|
| 401 | Missing or invalid API key |

---

### POST /auth/rotate-key

Generate a new API key that expires in 90 days, immediately invalidating the old one.

**Auth required:** API Key
**Rate limit:** 3 req/min

**Request body:** None

**Response (200):**

```json
{
  "success": true,
  "data": {
    "api_key": "manic_new_key...",
    "expires_at": "2026-06-21T12:00:00"
  },
  "error": null,
  "meta": null
}
```

---

### POST /auth/mfa/setup

Generate a TOTP secret and provisioning URI for the authenticated user. MFA is not activated until the user verifies a code via `POST /auth/mfa/verify`.

**Auth required:** API Key
**Rate limit:** 5 req/min

**Request body:** None

**Response (200):**

```json
{
  "success": true,
  "data": {
    "totp_secret": "BASE32SECRET",
    "provisioning_uri": "otpauth://totp/Manic%20AI:user@example.com?secret=BASE32SECRET&issuer=Manic%20AI"
  },
  "error": null,
  "meta": null
}
```

---

### POST /auth/mfa/verify

Verify a TOTP code and activate MFA on the account. Requires a prior call to `/auth/mfa/setup`.

**Auth required:** API Key
**Rate limit:** 5 req/min

**Request body:**

```json
{ "code": "123456" }
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `code` | string | Yes | 6-digit TOTP code from authenticator app |

**Response (200):**

```json
{
  "success": true,
  "data": { "message": "MFA enabled successfully" },
  "error": null,
  "meta": null
}
```

**Error responses:**

| Status | Description |
|--------|-------------|
| 400 | No TOTP secret found — call `/auth/mfa/setup` first |
| 400 | Invalid TOTP code |

---

### POST /auth/mfa/validate

Complete the login flow when MFA is required. Supply the `mfa_token` from the login response and a current TOTP code to receive the API key.

**Auth required:** None
**Rate limit:** 10 req/min

**Request body:**

```json
{
  "mfa_token": "tok_xyz...",
  "code": "123456"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `mfa_token` | string | Yes | Token from `POST /auth/login` when MFA is required |
| `code` | string | Yes | Current TOTP code from authenticator app |

**Response (200):**

```json
{
  "success": true,
  "data": {
    "api_key": "manic_abc123...",
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "user@example.com"
  },
  "error": null,
  "meta": null
}
```

**Error responses:**

| Status | Description |
|--------|-------------|
| 401 | MFA token invalid or expired |
| 401 | Invalid TOTP code |
| 503 | Redis unavailable (required for MFA token storage) |

---

## Chat Endpoints

---

### POST /v1/chat

Send a chat completion request. Supports optional RAG context retrieval.

**Auth required:** API Key
**Rate limit:** 60 req/min (general)

**Request body:**

```json
{
  "messages": [
    { "role": "user", "content": "Explain RAG in one paragraph." }
  ],
  "model": "llama3.2:3b",
  "temperature": 0.7,
  "max_tokens": 2048,
  "stream": false,
  "use_rag": true,
  "collection_id": "550e8400-e29b-41d4-a716-446655440000",
  "rerank": false
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `messages` | array | Yes | — | Conversation history; max 200 items |
| `messages[].role` | string | Yes | — | One of `system`, `user`, `assistant` |
| `messages[].content` | string | Yes | — | Message text; max 100 000 chars |
| `model` | string | No | `settings.CHAT_MODEL` | LLM model name |
| `temperature` | float | No | `0.7` | Sampling temperature (0–2) |
| `max_tokens` | int | No | `2048` | Maximum tokens in the response |
| `stream` | bool | No | `false` | Use `/v1/chat/stream` instead for streaming |
| `use_rag` | bool | No | `false` | Retrieve context from the vector store before generating |
| `collection_id` | string (UUID) | No | `null` | Scope RAG retrieval to a specific collection |
| `user_id` | string | No | `null` | In single-key mode, optionally associate with a user |
| `rerank` | bool | No | `false` | Apply cross-encoder reranking on RAG results |
| `context_window` | int | No | `null` | Override default context window size |

**Response (200):**

```json
{
  "success": true,
  "data": {
    "id": "chatcmpl-abc123",
    "model": "llama3.2:3b",
    "message": {
      "role": "assistant",
      "content": "RAG (Retrieval-Augmented Generation) combines..."
    },
    "sources": [
      {
        "id": "chunk-uuid",
        "document_id": "doc-uuid",
        "content": "...",
        "score": 0.87
      }
    ],
    "citations": [
      {
        "source_id": "chunk-uuid",
        "document_id": "doc-uuid",
        "chunk_index": 3,
        "content_preview": "First 200 chars of the chunk...",
        "score": 0.87
      }
    ],
    "usage": {
      "prompt_tokens": 120,
      "completion_tokens": 85,
      "total_tokens": 205
    }
  },
  "error": null,
  "meta": null
}
```

**Error responses:**

| Status | Description |
|--------|-------------|
| 500 | Internal server error |
| 502 | Chat/inference service unavailable |

---

### POST /v1/chat/stream

Same as `POST /v1/chat` but returns a server-sent event (SSE) stream.

**Auth required:** API Key
**Rate limit:** 60 req/min (general)

**Request body:** Identical to `POST /v1/chat`

**Response:** `Content-Type: text/event-stream`

Each event is a line in the format `data: <json>\n\n`. The content delta arrives as individual tokens. The stream ends when the connection is closed by the server.

```
data: {"type": "content", "delta": "RAG"}
data: {"type": "content", "delta": " combines"}
data: {"type": "done"}
```

---

## Search Endpoints

---

### POST /v1/search

Hybrid document search combining vector similarity and BM25 keyword matching. Uses POST to support complex query parameters.

**Auth required:** API Key
**Rate limit:** 60 req/min (general)

**Request body:**

```json
{
  "query": "What is retrieval augmented generation?",
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

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `query` | string | Yes | — | Search query text |
| `top_k` | int | No | `5` | Maximum number of results to return |
| `threshold` | float | No | `0.7` | Minimum similarity score (0.0–1.0) |
| `use_hybrid` | bool | No | `true` | Combine vector search with BM25 keyword matching |
| `backend` | string | No | `"supabase"` | One of `supabase`, `qdrant`, `both` |
| `collection_id` | string (UUID) | No | `null` | Restrict results to a specific collection |
| `user_id` | string | No | `null` | Restrict results to a specific user (overridden by auth token in multi_user mode) |
| `rerank` | bool | No | `false` | Apply cross-encoder reranking on results |
| `use_mmr` | bool | No | `false` | Use Maximal Marginal Relevance for diversity |
| `mmr_lambda` | float | No | `0.7` | MMR lambda — trade-off between relevance and diversity (0.0–1.0) |

**Response (200):**

```json
{
  "success": true,
  "data": [
    {
      "id": "chunk-uuid",
      "document_id": "doc-uuid",
      "content": "RAG combines a retrieval component...",
      "metadata": { "filename": "intro.pdf", "page": 2 },
      "score": 0.92
    }
  ],
  "error": null,
  "meta": null
}
```

**Error responses:**

| Status | Description |
|--------|-------------|
| 500 | Search failed (logged internally) |

---

### POST /v1/search/explain

Search with detailed per-result scoring breakdown for debugging and relevance tuning.

**Auth required:** API Key
**Rate limit:** None (no rate limit decorator applied)

**Request body:**

```json
{
  "query": "What is retrieval augmented generation?",
  "top_k": 5,
  "threshold": 0.5,
  "use_hybrid": true,
  "backend": "supabase",
  "collection_id": null,
  "include_vectors": false
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `query` | string | Yes | — | Search query text |
| `top_k` | int | No | `5` | Maximum results |
| `threshold` | float | No | `0.5` | Minimum similarity score |
| `use_hybrid` | bool | No | `true` | Enable BM25 hybrid |
| `backend` | string | No | `"supabase"` | One of `supabase`, `qdrant`, `both` |
| `collection_id` | string (UUID) | No | `null` | Scope to collection |
| `include_vectors` | bool | No | `false` | Include raw embedding vectors in the response |

**Response (200):**

The `data` object contains full scoring detail per result including vector scores, keyword scores, and reranking scores where applicable.

```json
{
  "success": true,
  "data": {
    "results": [
      {
        "id": "chunk-uuid",
        "content": "...",
        "score": 0.92,
        "vector_score": 0.88,
        "keyword_score": 0.74,
        "hybrid_score": 0.92
      }
    ]
  },
  "error": null,
  "meta": null
}
```

---

## Ingest Endpoints

---

### POST /v1/embed

Generate an embedding vector for a text string using the configured embedding model.

**Auth required:** API Key
**Rate limit:** None

**Request body:**

```json
{
  "text": "The quick brown fox jumps over the lazy dog.",
  "model": "bge-m3"
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `text` | string | Yes | — | Text to embed; max 50 000 chars |
| `model` | string | No | `settings.EMBEDDING_MODEL` | Ollama embedding model name |

**Response (200):**

```json
{
  "success": true,
  "data": {
    "embedding": [0.023, -0.014, "..."],
    "model": "bge-m3",
    "dimensions": 1024
  },
  "error": null,
  "meta": null
}
```

**Error responses:**

| Status | Description |
|--------|-------------|
| 502 | Embedding service (Ollama) unavailable |

---

### POST /v1/ingest

Accept a document for asynchronous ingestion. Returns immediately with a `document_id`. Poll `GET /v1/ingest/{document_id}/status` for completion.

For PDFs with `multimodal: true`, the ColPali-style pipeline is used: pages are converted to images, described by a vision LLM, and then embedded.

**Auth required:** API Key
**Rate limit:** 10 req/min (ingest)

**Request body:**

```json
{
  "content": "This document describes the architecture of the RAG pipeline...",
  "filename": "architecture.txt",
  "content_type": "text/plain",
  "user_id": null,
  "collection_id": "550e8400-e29b-41d4-a716-446655440000",
  "metadata": { "source": "internal-wiki" },
  "chunk_size": 500,
  "chunk_overlap": 50,
  "backend": "both",
  "chunking_strategy": "simple",
  "enrich_context": false,
  "multimodal": false
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `content` | string | Yes | — | Document text (or base64-encoded PDF bytes when `multimodal: true`); max 10 000 000 chars |
| `filename` | string | Yes | — | Filename; max 255 chars, no path separators |
| `content_type` | string | No | `"text/plain"` | MIME type of the content |
| `user_id` | string | No | `null` | Document owner (overridden by auth token in multi_user mode) |
| `collection_id` | string (UUID) | No | `null` | Associate with a collection |
| `metadata` | object | No | `null` | Arbitrary key/value metadata stored alongside chunks |
| `chunk_size` | int | No | `500` | Character count per chunk (1–10 000) |
| `chunk_overlap` | int | No | `50` | Overlap between consecutive chunks (0–`chunk_size - 1`) |
| `backend` | string | No | `"both"` | Storage backend: `supabase`, `qdrant`, or `both` |
| `chunking_strategy` | string | No | `"simple"` | `simple` (character splitting) or `semantic` (token-aware) |
| `enrich_context` | bool | No | `false` | Enrich each chunk with an LLM-generated contextual summary before embedding |
| `multimodal` | bool | No | `false` | Use vision-LLM pipeline for PDF pages (requires `content_type: application/pdf`) |

**Response (200):**

```json
{
  "success": true,
  "data": {
    "document_id": "550e8400-e29b-41d4-a716-446655440001",
    "status": "processing"
  },
  "error": null,
  "meta": null
}
```

**Error responses:**

| Status | Description |
|--------|-------------|
| 400 | Invalid base64 content for multimodal PDF |
| 422 | Validation error (e.g. chunk_overlap >= chunk_size) |

---

### POST /v1/ingest/upload

Accept a multipart/form-data file upload and ingest it asynchronously. Duplicate files are detected via SHA-256 and return `status: duplicate` without re-processing.

**Auth required:** API Key
**Rate limit:** None (no rate limit decorator applied to this endpoint)

**Content-Type:** `multipart/form-data`

**Form fields:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `file` | file | Yes | — | File to upload; allowed extensions: `.txt`, `.md`, `.html`, `.htm`, `.docx`, `.pdf` |
| `collection_id` | string | No | `null` | Associate with a collection |
| `backend` | string | No | `"supabase"` | Storage backend: `supabase`, `qdrant`, or `both` |
| `user_id` | string | No | `null` | Document owner (overridden by auth token in multi_user mode) |

**Response (202 Accepted):**

```json
{
  "success": true,
  "data": {
    "document_id": "550e8400-e29b-41d4-a716-446655440001",
    "status": "processing"
  },
  "error": null,
  "meta": null
}
```

**Response (200 — duplicate detected):**

```json
{
  "success": true,
  "data": {
    "document_id": "550e8400-e29b-41d4-a716-446655440001",
    "filename": "architecture.txt",
    "chunks_created": 0,
    "status": "duplicate"
  },
  "error": null,
  "meta": null
}
```

**Error responses:**

| Status | Description |
|--------|-------------|
| 400 | Invalid backend value or empty file |
| 415 | Unsupported file extension |
| 422 | File content is not valid UTF-8 (for non-PDF/DOCX files) |

---

### GET /v1/ingest/{document_id}/status

Poll the status of an asynchronous ingestion job. Falls back to the in-memory job tracker if the database is unavailable.

**Auth required:** API Key
**Rate limit:** None

**Path parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `document_id` | string (UUID) | ID returned by `POST /v1/ingest` or `POST /v1/ingest/upload` |

**Response (200):**

```json
{
  "success": true,
  "data": {
    "document_id": "550e8400-e29b-41d4-a716-446655440001",
    "status": "completed",
    "filename": "architecture.txt",
    "chunks_created": 14,
    "error": null,
    "created_at": "2026-03-23T10:00:00+00:00",
    "updated_at": "2026-03-23T10:00:05+00:00"
  },
  "error": null,
  "meta": null
}
```

The `status` field follows this lifecycle:

| Status | Description |
|--------|-------------|
| `pending` | Job accepted but not yet started |
| `processing` | Chunking and embedding in progress |
| `completed` | All chunks stored successfully |
| `failed` | Processing failed; see `error` field |

**Error responses:**

| Status | Description |
|--------|-------------|
| 404 | No ingestion job found for this document_id |

---

### POST /v1/ingest/pii-scan

Scan text for personally identifiable information (PII) without storing anything. Returns entity types and character offsets; raw PII values are intentionally omitted.

**Auth required:** API Key
**Rate limit:** None

**Request body:**

```json
{
  "content": "Please contact John Doe at john.doe@example.com or call 555-123-4567."
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `content` | string | Yes | Text to scan; min 1, max 500 000 chars |

**Response (200):**

```json
{
  "success": true,
  "data": {
    "entities": [
      { "entity_type": "EMAIL", "start": 30, "end": 52 },
      { "entity_type": "PHONE", "start": 63, "end": 75 }
    ],
    "total_found": 2
  },
  "error": null,
  "meta": null
}
```

---

### POST /v1/ingest/preview-chunks

Preview how a document would be chunked without storing anything. Use this to compare strategies and tune parameters before committing an ingestion.

**Auth required:** API Key
**Rate limit:** None

**Request body:**

```json
{
  "content": "This is the full text of the document to preview...",
  "strategy": "simple",
  "chunk_size": 500,
  "overlap": 50
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `content` | string | Yes | — | Text to chunk; min 1, max 1 000 000 chars |
| `strategy` | string | No | `"simple"` | `simple` or `semantic` |
| `chunk_size` | int | No | `500` | Character count per chunk (50–10 000) |
| `overlap` | int | No | `50` | Overlap between chunks (0–2 000) |

**Response (200):**

```json
{
  "success": true,
  "data": {
    "strategy": "simple",
    "chunk_count": 3,
    "chunks": [
      { "index": 0, "content": "This is the full text...", "start": 0, "end": 500 },
      { "index": 1, "content": "...", "start": 450, "end": 950 }
    ]
  },
  "error": null,
  "meta": null
}
```

---

## Documents Endpoints

---

### GET /v1/documents

List all ingested documents with optional filters and pagination.

**Auth required:** API Key
**Rate limit:** None

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `user_id` | string | `null` | Filter by owner user ID |
| `collection_id` | string | `null` | Filter by collection ID |
| `status` | string | `null` | Filter by ingestion status |
| `limit` | int | `50` | Page size (1–500) |
| `offset` | int | `0` | Pagination offset |

**Response (200):**

```json
{
  "success": true,
  "data": [
    {
      "id": "doc-uuid",
      "filename": "architecture.txt",
      "content_type": "text/plain",
      "status": "completed",
      "chunks_created": 14,
      "user_id": "user-uuid",
      "collection_id": "coll-uuid",
      "created_at": "2026-03-23T10:00:00+00:00"
    }
  ],
  "error": null,
  "meta": { "total": 142, "limit": 50, "offset": 0 }
}
```

---

### DELETE /v1/documents/{document_id}

Delete a document and all its chunks from both Supabase and Qdrant. Returns 404 for non-existent documents and for documents owned by other users (IDOR prevention).

**Auth required:** API Key
**Rate limit:** 30 req/min (mutations)

**Path parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `document_id` | string (UUID) | Document to delete |

**Response (200):**

```json
{
  "success": true,
  "data": { "status": "deleted", "document_id": "doc-uuid" },
  "error": null,
  "meta": null
}
```

**Error responses:**

| Status | Description |
|--------|-------------|
| 404 | Document not found or owned by a different user |

---

### GET /v1/documents/{document_id}/chunks

Retrieve the individual chunks that were created during ingestion for a specific document.

**Auth required:** API Key
**Rate limit:** None

**Path parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `document_id` | string (UUID) | Document whose chunks to retrieve |

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | `50` | Page size (1–200) |
| `offset` | int | `0` | Pagination offset |

**Response (200):**

```json
{
  "success": true,
  "data": {
    "total": 14,
    "chunks": [
      {
        "id": "chunk-uuid",
        "document_id": "doc-uuid",
        "chunk_index": 0,
        "content": "This is the first chunk...",
        "metadata": {}
      }
    ]
  },
  "error": null,
  "meta": { "total": 14, "limit": 50, "offset": 0 }
}
```

---

## Collections Endpoints

---

### GET /v1/collections

List all collections with pagination.

**Auth required:** API Key
**Rate limit:** None

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `user_id` | string | `null` | Filter by owner (overridden by auth token in multi_user mode) |
| `limit` | int | `50` | Page size (1–500) |
| `offset` | int | `0` | Pagination offset |

**Response (200):**

```json
{
  "success": true,
  "data": [
    {
      "id": "coll-uuid",
      "name": "Product Documentation",
      "description": "Internal product docs",
      "user_id": "user-uuid",
      "is_public": false,
      "created_at": "2026-03-01T00:00:00+00:00"
    }
  ],
  "error": null,
  "meta": { "total": 5, "limit": 50, "offset": 0 }
}
```

---

### POST /v1/collections

Create a new collection.

**Auth required:** API Key
**Rate limit:** 30 req/min (mutations)

**Request body:**

```json
{
  "name": "Product Documentation",
  "description": "Internal product docs",
  "is_public": false
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | Yes | — | Collection name; 1–200 chars |
| `description` | string | No | `null` | Optional description; max 1 000 chars |
| `user_id` | string | No | `null` | Owner (overridden by auth token in multi_user mode) |
| `is_public` | bool | No | `false` | Whether the collection is visible to all users |

**Response (200):**

```json
{
  "success": true,
  "data": {
    "id": "coll-uuid",
    "name": "Product Documentation",
    "status": "created"
  },
  "error": null,
  "meta": null
}
```

---

### DELETE /v1/collections/{collection_id}

Delete a collection by ID.

**Auth required:** API Key
**Rate limit:** 30 req/min (mutations)

**Path parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `collection_id` | string (UUID) | Collection to delete |

**Response (200):**

```json
{
  "success": true,
  "data": { "status": "deleted", "collection_id": "coll-uuid" },
  "error": null,
  "meta": null
}
```

**Error responses:**

| Status | Description |
|--------|-------------|
| 404 | Collection not found |

---

## Conversations Endpoints

All conversation endpoints are prefixed with `/v1/conversations`. User ownership is stored inside the `metadata` JSONB field. Requests for conversations owned by another user return 404 (not 403) to prevent IDOR enumeration.

---

### GET /v1/conversations

List conversations with optional user filter and pagination.

**Auth required:** API Key
**Rate limit:** None

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `user_id` | string | `null` | Filter by user (overridden by auth token in multi_user mode) |
| `limit` | int | `50` | Page size (1–200) |
| `offset` | int | `0` | Pagination offset |

**Response (200):**

```json
{
  "success": true,
  "data": [
    {
      "id": "conv-uuid",
      "title": "RAG Architecture Discussion",
      "system_prompt": "You are a helpful assistant.",
      "metadata": { "user_id": "user-uuid" },
      "created_at": "2026-03-23T09:00:00+00:00",
      "updated_at": "2026-03-23T09:15:00+00:00"
    }
  ],
  "error": null,
  "meta": { "total": 12, "limit": 50, "offset": 0 }
}
```

---

### POST /v1/conversations

Create a new conversation.

**Auth required:** API Key
**Rate limit:** None

**Request body:**

```json
{
  "title": "RAG Architecture Discussion",
  "system_prompt": "You are a helpful assistant.",
  "user_id": null
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `title` | string | No | `"New Conversation"` | Conversation title; max 255 chars |
| `system_prompt` | string | No | `null` | Optional system prompt |
| `user_id` | string | No | `null` | Owner (overridden by auth token in multi_user mode) |

**Response (200):**

```json
{
  "success": true,
  "data": {
    "id": "conv-uuid",
    "title": "RAG Architecture Discussion",
    "system_prompt": "You are a helpful assistant.",
    "metadata": {},
    "created_at": "2026-03-23T09:00:00+00:00",
    "updated_at": "2026-03-23T09:00:00+00:00"
  },
  "error": null,
  "meta": null
}
```

---

### GET /v1/conversations/{conversation_id}

Return a conversation and all its messages ordered by creation time.

**Auth required:** API Key
**Rate limit:** None

**Path parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `conversation_id` | string (UUID) | Conversation ID |

**Response (200):**

```json
{
  "success": true,
  "data": {
    "id": "conv-uuid",
    "title": "RAG Architecture Discussion",
    "system_prompt": null,
    "metadata": {},
    "created_at": "2026-03-23T09:00:00+00:00",
    "updated_at": "2026-03-23T09:15:00+00:00",
    "messages": [
      {
        "id": "msg-uuid",
        "conversation_id": "conv-uuid",
        "role": "user",
        "content": "Explain RAG in one paragraph.",
        "model": null,
        "tokens_used": null,
        "created_at": "2026-03-23T09:00:01+00:00"
      },
      {
        "id": "msg-uuid-2",
        "conversation_id": "conv-uuid",
        "role": "assistant",
        "content": "RAG combines a retrieval step...",
        "model": "llama3.2:3b",
        "tokens_used": 85,
        "created_at": "2026-03-23T09:00:03+00:00"
      }
    ]
  },
  "error": null,
  "meta": null
}
```

**Error responses:**

| Status | Description |
|--------|-------------|
| 404 | Conversation not found or owned by another user |

---

### PATCH /v1/conversations/{conversation_id}

Update the `title` and/or `system_prompt` of an existing conversation. At least one field must be provided.

**Auth required:** API Key
**Rate limit:** None

**Path parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `conversation_id` | string (UUID) | Conversation to update |

**Request body:**

```json
{
  "title": "Updated Title",
  "system_prompt": "You are a concise assistant."
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | string | No | New title; max 255 chars |
| `system_prompt` | string | No | New system prompt |

**Response (200):** Returns the updated conversation object (same shape as `GET /v1/conversations/{id}`).

**Error responses:**

| Status | Description |
|--------|-------------|
| 400 | Neither `title` nor `system_prompt` was provided |
| 404 | Conversation not found or owned by another user |

---

### DELETE /v1/conversations/{conversation_id}

Delete a conversation and all its messages (messages are cascade-deleted by the database foreign key).

**Auth required:** API Key
**Rate limit:** None

**Path parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `conversation_id` | string (UUID) | Conversation to delete |

**Response (200):**

```json
{
  "success": true,
  "data": { "deleted": true, "conversation_id": "conv-uuid" },
  "error": null,
  "meta": null
}
```

**Error responses:**

| Status | Description |
|--------|-------------|
| 404 | Conversation not found or owned by another user |

---

### POST /v1/conversations/{conversation_id}/messages

Append a message to a conversation. Also updates the conversation's `updated_at` timestamp.

**Auth required:** API Key
**Rate limit:** None

**Path parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `conversation_id` | string (UUID) | Target conversation |

**Request body:**

```json
{
  "role": "user",
  "content": "What are the key benefits of RAG?"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `role` | string | Yes | One of `user`, `assistant`, `system` |
| `content` | string | Yes | Message content; minimum 1 char |

**Response (200):**

```json
{
  "success": true,
  "data": {
    "id": "msg-uuid",
    "conversation_id": "conv-uuid",
    "role": "user",
    "content": "What are the key benefits of RAG?",
    "model": null,
    "tokens_used": null,
    "created_at": "2026-03-23T09:05:00+00:00"
  },
  "error": null,
  "meta": null
}
```

**Error responses:**

| Status | Description |
|--------|-------------|
| 404 | Conversation not found or owned by another user |

---

## Admin Endpoints

All admin endpoints require a valid API key that belongs to a user with `is_admin = true`. The API key is read from the `X-API-Key` header.

---

### GET /v1/admin/users

List all users with pagination. API keys in the response are masked.

**Auth required:** Admin
**Rate limit:** None

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | `50` | Page size (1–200) |
| `offset` | int | `0` | Pagination offset |

**Response (200):**

```json
{
  "success": true,
  "data": {
    "total": 42,
    "users": [
      {
        "id": "user-uuid",
        "email": "user@example.com",
        "username": "alice",
        "is_active": true,
        "is_admin": false,
        "api_key": "manic_abc...***",
        "created_at": "2026-01-01T00:00:00+00:00"
      }
    ]
  },
  "error": null,
  "meta": { "limit": 50, "offset": 0, "total": 42 }
}
```

---

### GET /v1/admin/users/{user_id}

Fetch a single user by UUID.

**Auth required:** Admin
**Rate limit:** None

**Path parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `user_id` | string (UUID) | User to retrieve |

**Response (200):** Returns a single user object (same shape as the list items above).

**Error responses:**

| Status | Description |
|--------|-------------|
| 404 | User not found |

---

### POST /v1/admin/users

Create a new user account. An API key is generated automatically.

**Auth required:** Admin
**Rate limit:** None

**Request body:**

```json
{
  "email": "newuser@example.com",
  "password": "Str0ngP@ss",
  "username": "bob",
  "is_admin": false
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `email` | string (email) | Yes | — | New account email |
| `password` | string | Yes | — | Minimum 8 characters |
| `username` | string | No | `null` | Display name; max 64 chars |
| `is_admin` | bool | No | `false` | Grant admin privileges immediately |

**Response (200):** Returns the created user object including the generated `api_key`.

**Error responses:**

| Status | Description |
|--------|-------------|
| 409 | A user with that email or username already exists |

---

### PATCH /v1/admin/users/{user_id}

Partially update a user. Only fields included in the body are modified.

**Auth required:** Admin
**Rate limit:** None

**Path parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `user_id` | string (UUID) | User to update |

**Request body:**

```json
{
  "is_active": true,
  "is_admin": false,
  "rate_limit_override": 120,
  "username": "alice-updated"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `is_active` | bool | No | Enable or disable the account |
| `is_admin` | bool | No | Grant or revoke admin access |
| `rate_limit_override` | int | No | Per-user rate limit override (1–10 000 req/min) |
| `username` | string | No | New display name; max 64 chars |

**Response (200):** Returns the updated user object.

**Error responses:**

| Status | Description |
|--------|-------------|
| 404 | User not found |

---

### DELETE /v1/admin/users/{user_id}

Soft-delete a user by setting `is_active = false`. The account and all data are retained; the user cannot authenticate until re-activated via PATCH.

**Auth required:** Admin
**Rate limit:** None

**Path parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `user_id` | string (UUID) | User to deactivate |

**Response (200):**

```json
{
  "success": true,
  "data": { "user_id": "user-uuid", "deactivated": true },
  "error": null,
  "meta": null
}
```

**Error responses:**

| Status | Description |
|--------|-------------|
| 404 | User not found |

---

### GET /v1/admin/stats

Return system-wide aggregate statistics covering total/active users, admin count, chat sessions, searches, and feedback entries.

**Auth required:** Admin
**Rate limit:** None

**Response (200):**

```json
{
  "success": true,
  "data": {
    "total_users": 42,
    "active_users": 38,
    "admin_users": 2,
    "total_chats": 1840,
    "total_searches": 5320,
    "total_feedback": 312
  },
  "error": null,
  "meta": null
}
```

---

## Health Endpoints

Health endpoints are mounted at the root (no `/v1/` prefix) for load-balancer compatibility.

---

### GET /health

Basic liveness probe. Cached for 5 seconds to prevent hammering downstream services.

**Auth required:** None
**Rate limit:** None

**Response (200):**

```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "timestamp": "2026-03-23T10:00:00+00:00"
  },
  "error": null,
  "meta": null
}
```

---

### GET /health/ready

Readiness probe. Returns 200 only when the database and Redis are reachable. Intended for Kubernetes/load-balancer traffic gating.

**Auth required:** None
**Rate limit:** None

**Response (200):**

```json
{ "status": "ready" }
```

**Response (503):**

```json
{ "status": "not ready", "failed": ["database"] }
```

---

### GET /services/status

Return the current status and latency of all downstream services: Ollama, PostgreSQL, Qdrant, SearXNG, and Langfuse.

**Auth required:** API Key
**Rate limit:** None

**Response (200):**

```json
{
  "success": true,
  "data": {
    "timestamp": "2026-03-23T10:00:00+00:00",
    "services": {
      "ollama":   { "name": "Ollama",     "url": "http://ollama:11434",   "status": "healthy", "latency_ms": 12.3 },
      "database": { "name": "PostgreSQL", "url": "supabase-db:5432",      "status": "healthy", "latency_ms": 2.1  },
      "qdrant":   { "name": "Qdrant",     "url": "http://qdrant:6333",    "status": "healthy", "latency_ms": 5.8  },
      "searxng":  { "name": "SearXNG",    "url": "http://ai-searxng:8080","status": "healthy", "latency_ms": 18.7 },
      "langfuse": { "name": "Langfuse",   "url": "http://langfuse:3000",  "status": "offline", "latency_ms": null }
    }
  },
  "error": null,
  "meta": null
}
```

---

### GET /services/status/stream

Server-sent event stream of service status snapshots. Pushes a new status payload every 10 seconds.

**Auth required:** API Key
**Rate limit:** None

**Response:** `Content-Type: text/event-stream`

```
data: {"timestamp": "...", "services": { ... }}

data: {"timestamp": "...", "services": { ... }}
```

---

### WS /ws/status

WebSocket endpoint for real-time service status updates. Sends a full status snapshot every 10 seconds. Responds to `"ping"` messages with `{"type": "pong"}`.

**Auth required:** Optional token query parameter when `API_SECRET_KEY` is configured

**Query parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `token` | string | Must match `API_SECRET_KEY` when set; connection is rejected with code 1008 on mismatch |

**Messages received from server:** Same JSON shape as `GET /services/status` data.

**Messages sent by client:**

```
ping
```

**Messages received from server (in response to ping):**

```json
{ "type": "pong" }
```

---

### GET /metrics

Prometheus metrics scrape endpoint in the standard text exposition format.

**Auth required:** None (excluded from OpenAPI schema)
**Rate limit:** None

**Response:** `Content-Type: text/plain; version=0.0.4`

---

## Analytics Endpoints

Analytics responses are cached in Redis (60-second TTL for usage/models/RAG; 30-second TTL for service history).

---

### GET /v1/analytics/usage

Aggregate chat usage statistics for a given time period, optionally filtered by model.

**Auth required:** API Key
**Rate limit:** None

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `period` | string | `"day"` | One of `hour`, `day`, `week`, `month` |
| `model` | string | `null` | Filter by specific model name; max 200 chars |

**Response (200):**

```json
{
  "success": true,
  "data": {
    "period": "day",
    "total_requests": 240,
    "total_tokens": 48320,
    "avg_tokens_per_request": 201,
    "requests_by_hour": [
      { "hour": "2026-03-23T09:00:00", "count": 12 }
    ]
  },
  "error": null,
  "meta": null
}
```

---

### GET /v1/analytics/models

Return model-level analytics: usage counts, token totals, and availability fetched from Ollama.

**Auth required:** API Key
**Rate limit:** None

**Response (200):**

```json
{
  "success": true,
  "data": {
    "models": [
      {
        "name": "llama3.2:3b",
        "request_count": 180,
        "total_tokens": 36000,
        "available": true
      }
    ]
  },
  "error": null,
  "meta": null
}
```

---

### GET /v1/analytics/rag

Return RAG pipeline analytics: total documents, chunks, collections, and recent ingestion activity.

**Auth required:** API Key
**Rate limit:** None

**Response (200):**

```json
{
  "success": true,
  "data": {
    "total_documents": 142,
    "total_chunks": 2840,
    "total_collections": 5,
    "storage_bytes": 5242880,
    "avg_chunk_tokens": 128,
    "embedding_model": "bge-m3",
    "vector_dimension": 1024,
    "index_type": "pgvector (ivfflat)",
    "documents_by_type": { "text/plain": 80, "application/pdf": 62 },
    "recent_ingestions": []
  },
  "error": null,
  "meta": null
}
```

---

### GET /v1/analytics/services/history

Return historical service health metrics for a rolling window of up to 168 hours (7 days).

**Auth required:** API Key
**Rate limit:** None

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `service` | string | `null` | Filter by service name (alphanumeric, hyphens, underscores; max 100 chars) |
| `hours` | int | `24` | Lookback window in hours (1–168) |

**Response (200):**

```json
{
  "success": true,
  "data": {
    "service": "ollama",
    "hours": 24,
    "records": [
      {
        "timestamp": "2026-03-23T09:00:00+00:00",
        "status": "healthy",
        "latency_ms": 11.2
      }
    ]
  },
  "error": null,
  "meta": null
}
```

---

## Qdrant Endpoints

Direct Qdrant vector database management. All endpoints require API Key. Collection names must match `^[a-zA-Z0-9_\-]{1,64}$`.

---

### GET /v1/qdrant/collections

List all Qdrant collections.

**Auth required:** API Key
**Rate limit:** None

**Response (200):**

```json
{
  "success": true,
  "data": {
    "collections": [
      { "name": "documents", "vectors_count": 2840 }
    ]
  },
  "error": null,
  "meta": null
}
```

**Error responses:**

| Status | Description |
|--------|-------------|
| 502 | Qdrant service unavailable |

---

### POST /v1/qdrant/collections/{collection_name}

Create a new Qdrant collection with the specified vector size.

**Auth required:** API Key
**Rate limit:** None

**Path parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `collection_name` | string | Collection name; regex `^[a-zA-Z0-9_\-]{1,64}$` |

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `vector_size` | int | `settings.VECTOR_DIMENSION` (1024) | Dimensionality of vectors to store |

**Response (200):**

```json
{
  "success": true,
  "data": { "result": true, "status": "ok" },
  "error": null,
  "meta": null
}
```

**Error responses:**

| Status | Description |
|--------|-------------|
| 400 | Invalid collection name |
| 502 | Qdrant service unavailable |

---

### GET /v1/qdrant/collections/{collection_name}

Get metadata and statistics for a Qdrant collection.

**Auth required:** API Key
**Rate limit:** None

**Path parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `collection_name` | string | Collection name |

**Response (200):**

```json
{
  "success": true,
  "data": {
    "result": {
      "status": "green",
      "vectors_count": 2840,
      "config": { "params": { "vectors": { "size": 1024, "distance": "Cosine" } } }
    }
  },
  "error": null,
  "meta": null
}
```

**Error responses:**

| Status | Description |
|--------|-------------|
| 400 | Invalid collection name |
| 502 | Qdrant service unavailable |

---

### DELETE /v1/qdrant/collections/{collection_name}

Delete a Qdrant collection and all its vectors.

**Auth required:** API Key
**Rate limit:** None

**Path parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `collection_name` | string | Collection name |

**Response (200):**

```json
{
  "success": true,
  "data": { "result": true },
  "error": null,
  "meta": null
}
```

**Error responses:**

| Status | Description |
|--------|-------------|
| 400 | Invalid collection name |
| 502 | Qdrant service unavailable |

---

### POST /v1/qdrant/search/{collection_name}

Perform vector similarity search within a named Qdrant collection. The query text is embedded on the server side.

**Auth required:** API Key
**Rate limit:** None

**Path parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `collection_name` | string | Collection to search |

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | string | — | Search query text (required) |
| `top_k` | int | `5` | Maximum results |
| `threshold` | float | `0.7` | Minimum similarity score |

**Response (200):**

```json
{
  "success": true,
  "data": {
    "results": [
      { "id": "chunk-uuid", "score": 0.91, "payload": { "content": "..." } }
    ],
    "count": 1
  },
  "error": null,
  "meta": null
}
```

**Error responses:**

| Status | Description |
|--------|-------------|
| 400 | Invalid collection name |
| 500 | Search failed |

---

## System Endpoints

---

### GET /v1/system/info

Return runtime information including version, uptime, active configuration, and database pool status.

**Auth required:** API Key
**Rate limit:** None

**Response (200):**

```json
{
  "success": true,
  "data": {
    "version": "2.0.0",
    "uptime_seconds": 3600.0,
    "start_time": "2026-03-23T06:00:00+00:00",
    "config": {
      "chat_model": "llama3.2:3b",
      "embedding_model": "bge-m3",
      "vector_dimension": 1024,
      "rag_top_k": 5,
      "rag_threshold": 0.7
    },
    "database": { "pool_size": 10, "pool_free": 8 }
  },
  "error": null,
  "meta": null
}
```

---

### POST /v1/system/cache/clear

Clear all Redis cache keys matching the `manic:*` namespace prefix.

**Auth required:** API Key
**Rate limit:** 30 req/min (mutations)

**Request body:** None

**Response (200):**

```json
{
  "success": true,
  "data": { "cleared": true, "keys_removed": 42 },
  "error": null,
  "meta": null
}
```

When Redis is unavailable:

```json
{
  "success": true,
  "data": { "cleared": false, "keys_removed": 0, "error": "Redis not available" },
  "error": null,
  "meta": null
}
```

---

### GET /v1/rag/stats

Return RAG pipeline aggregate statistics directly from the database including document counts, chunk counts, storage usage, and recent ingestions.

**Auth required:** API Key
**Rate limit:** None

**Response (200):** Same shape as `GET /v1/analytics/rag`.

---

## Models Endpoints

---

### GET /v1/models

List all locally available Ollama models.

**Auth required:** API Key
**Rate limit:** None

**Response (200):**

```json
{
  "success": true,
  "data": {
    "models": [
      {
        "name": "llama3.2:3b",
        "size": 2048000000,
        "modified_at": "2026-03-01T00:00:00Z",
        "digest": "sha256:abc..."
      }
    ]
  },
  "error": null,
  "meta": null
}
```

**Error responses:**

| Status | Description |
|--------|-------------|
| 502 | Failed to list models (Ollama unavailable) |

---

### GET /v1/api/tags

Compatibility alias for `GET /v1/models`. Returns the same response.

**Auth required:** API Key
**Rate limit:** None

---

### POST /v1/models/pull

Pull (download) an Ollama model by name. Returns a server-sent event stream of progress updates.

**Auth required:** API Key
**Rate limit:** 30 req/min (mutations)

**Request body:**

```json
{ "name": "llama3.2:3b" }
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Ollama model name; max 200 chars |

**Response:** `Content-Type: text/event-stream`

Progress events are streamed until the pull completes or fails.

```
data: {"status": "pulling manifest"}
data: {"status": "pulling layer", "completed": 102400, "total": 2048000000}
data: {"status": "success"}
```

---

### DELETE /v1/models/{name}

Delete a local Ollama model.

**Auth required:** API Key
**Rate limit:** 30 req/min (mutations)

**Path parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | string | Ollama model name (URL-encode colons: `llama3.2%3A3b`) |

**Response (200):**

```json
{
  "success": true,
  "data": { "deleted": true, "name": "llama3.2:3b" },
  "error": null,
  "meta": null
}
```

**Error responses:**

| Status | Description |
|--------|-------------|
| 400 | Invalid model name |
| 502 | Failed to delete model (Ollama unavailable) |

---

## Agent Endpoints

---

### POST /v1/agent/run

Execute the Generator-Critic reasoning agent loop synchronously and return a structured result.

**Auth required:** API Key
**Rate limit:** 20 req/min (agent)

**Request body:**

```json
{
  "query": "What are the trade-offs between BM25 and vector search for RAG?",
  "model": null
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `query` | string | Yes | — | The question or task; 1–10 000 chars |
| `model` | string | No | `null` | Override the default chat model |

**Response (200):**

```json
{
  "success": true,
  "data": {
    "run_id": "run-uuid",
    "query": "What are the trade-offs...",
    "answer": "BM25 excels at exact keyword matching...",
    "steps": [
      { "type": "generate", "content": "Initial draft..." },
      { "type": "critique", "content": "Missing discussion of latency..." },
      { "type": "revise", "content": "Revised answer..." }
    ],
    "status": "completed"
  },
  "error": null,
  "meta": null
}
```

**Error responses:**

| Status | Description |
|--------|-------------|
| 500 | Agent run failed |
| 502 | Inference backend unavailable |

---

### GET /v1/agent/{run_id}/status

Check the status of a previously started agent run by its ID.

**Auth required:** API Key
**Rate limit:** None

**Path parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `run_id` | string | Run ID returned by `POST /v1/agent/run` or `POST /v1/agent/stream` |

**Response (200):** Returns the full agent state object.

**Error responses:**

| Status | Description |
|--------|-------------|
| 404 | No agent run found for run_id |

---

### POST /v1/agent/stream

Stream agent reasoning steps in real-time via SSE.

**Auth required:** API Key
**Rate limit:** 20 req/min (agent)

**Request body:** Identical to `POST /v1/agent/run`

**Response:** `Content-Type: text/event-stream`

Each event carries a reasoning step as it is produced:

```
data: {"type": "generate", "content": "Initial draft..."}
data: {"type": "critique", "content": "Missing discussion..."}
data: {"type": "revise", "content": "Revised answer..."}
data: {"type": "done", "run_id": "run-uuid"}
```

---

## Eval Endpoints

---

### POST /v1/eval/run

Run a single RAG evaluation: execute a search, compare the retrieved chunk IDs against ground-truth relevant IDs, and compute retrieval metrics.

**Auth required:** API Key
**Rate limit:** None

**Request body:**

```json
{
  "query": "What is RAG?",
  "relevant_chunk_ids": ["chunk-uuid-1", "chunk-uuid-2"],
  "top_k": 5,
  "backend": "supabase",
  "use_hybrid": true,
  "rerank": false
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `query` | string | Yes | — | Search query |
| `relevant_chunk_ids` | array of strings | Yes | — | Ground-truth relevant chunk UUIDs (minimum 1) |
| `top_k` | int | No | `5` | Retrieval depth (1–50) |
| `backend` | string | No | `"supabase"` | Search backend |
| `use_hybrid` | bool | No | `true` | Enable hybrid search |
| `rerank` | bool | No | `false` | Apply reranking |

**Response (200):**

```json
{
  "success": true,
  "data": {
    "query": "What is RAG?",
    "precision_at_k": 0.6,
    "recall_at_k": 0.75,
    "f1_at_k": 0.667,
    "mrr": 0.5,
    "ndcg": 0.72,
    "retrieved_ids": ["chunk-uuid-1", "chunk-uuid-3", "chunk-uuid-4"],
    "score_distribution": { "min": 0.62, "max": 0.94, "mean": 0.81, "std": 0.11 }
  },
  "error": null,
  "meta": null
}
```

---

### POST /v1/eval/batch

Run batch RAG evaluation over multiple test cases (max 50). Returns per-query metrics and aggregate averages across all queries.

**Auth required:** API Key
**Rate limit:** None

**Request body:**

```json
{
  "test_cases": [
    {
      "query": "What is RAG?",
      "relevant_chunk_ids": ["chunk-uuid-1"],
      "top_k": 5,
      "backend": "supabase",
      "use_hybrid": true,
      "rerank": false
    }
  ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `test_cases` | array | Yes | List of eval cases (same schema as `POST /v1/eval/run`); max 50 items |

**Response (200):**

```json
{
  "success": true,
  "data": {
    "test_cases": 2,
    "results": [ { "query": "...", "precision_at_k": 0.6 } ],
    "aggregate": {
      "precision_at_k": 0.65,
      "recall_at_k": 0.72,
      "f1_at_k": 0.683
    }
  },
  "error": null,
  "meta": null
}
```

---

### GET /v1/eval/search-history

Retrieve recent search events logged by the search pipeline for analysis.

**Auth required:** API Key
**Rate limit:** None

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | `50` | Page size (1–500) |
| `offset` | int | `0` | Pagination offset |

**Response (200):**

```json
{
  "success": true,
  "data": {
    "history": [
      {
        "id": "event-uuid",
        "query": "What is RAG?",
        "results_count": 5,
        "backend": "supabase",
        "created_at": "2026-03-23T09:00:00+00:00"
      }
    ]
  },
  "error": null,
  "meta": null
}
```

---

## Feedback Endpoints

---

### POST /v1/feedback

Submit user feedback (thumbs up / neutral / thumbs down) on a chat response.

**Auth required:** API Key
**Rate limit:** None

**Request body:**

```json
{
  "rating": 1,
  "comment": "Accurate and concise answer",
  "conversation_id": "conv-abc123",
  "message_id": "msg-xyz789",
  "query_text": "Explain RAG",
  "response_text": "RAG combines retrieval and generation...",
  "had_rag": true
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `rating` | int | Yes | — | `-1` (thumbs down), `0` (neutral), or `1` (thumbs up) |
| `comment` | string | No | `null` | Optional free-text comment; max 2 000 chars |
| `conversation_id` | string | No | `null` | Conversation session identifier |
| `message_id` | string | No | `null` | Specific message identifier |
| `query_text` | string | No | `null` | The user query that prompted the response |
| `response_text` | string | No | `null` | The assistant response being rated |
| `had_rag` | bool | No | `false` | Whether RAG context was used to generate the response |

**Response (200):**

```json
{
  "success": true,
  "data": { "id": "feedback-uuid", "rating": 1 },
  "error": null,
  "meta": null
}
```

**Error responses:**

| Status | Description |
|--------|-------------|
| 422 | `rating` must be -1, 0, or 1 |

---

### GET /v1/feedback/stats

Return aggregated feedback statistics for a rolling lookback window.

**Auth required:** API Key
**Rate limit:** None

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | int | `30` | Lookback window in days (1–365) |

**Response (200):**

```json
{
  "success": true,
  "data": {
    "days": 30,
    "total": 312,
    "positive": 240,
    "neutral": 48,
    "negative": 24,
    "positive_rate": 0.769,
    "average_rating": 0.692,
    "rag_positive_rate": 0.84,
    "non_rag_positive_rate": 0.71
  },
  "error": null,
  "meta": null
}
```

---

## Plugins Endpoints

---

### GET /v1/plugins

List all installed plugins and their registered tools.

**Auth required:** API Key
**Rate limit:** None

**Response (200):**

```json
{
  "success": true,
  "data": {
    "tools": [
      { "name": "my_tool", "description": "Does something useful", "plugin": "my-plugin" }
    ],
    "count": 1
  },
  "error": null,
  "meta": null
}
```

---

### POST /v1/plugins/{tool_name}/run

Execute a named plugin tool with the provided arguments. Supports both synchronous and asynchronous tool implementations.

**Auth required:** API Key
**Rate limit:** None

**Path parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `tool_name` | string | Registered tool name (see `GET /v1/plugins`) |

**Request body:**

```json
{
  "arguments": {
    "input": "Hello world",
    "language": "en"
  }
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `arguments` | object | No | `{}` | Key/value arguments passed to the tool function |

**Response (200):**

```json
{
  "success": true,
  "data": {
    "tool": "my_tool",
    "result": { "output": "Processed result" }
  },
  "error": null,
  "meta": null
}
```

**Error responses:**

| Status | Description |
|--------|-------------|
| 404 | Tool not found |
| 422 | Invalid arguments for the tool |
| 500 | Tool execution failed |

---

## OpenAI-Compatible Endpoints

These endpoints implement the OpenAI wire format so third-party OpenAI clients can point at Manic AI without modification. Set `base_url` in your OpenAI client to `http://localhost:8081/v1`.

---

### POST /v1/chat/completions

OpenAI-compatible chat completions. Routes inference through the existing model_router service, maintaining backend selection, fallback chains, and Langfuse tracing.

**Auth required:** API Key (via `X-API-Key` header)
**Rate limit:** None (inherits general rate limit via middleware)

**Request body:**

```json
{
  "model": "llama3.2:3b",
  "messages": [
    { "role": "user", "content": "Hello" }
  ],
  "stream": false,
  "temperature": 0.7,
  "max_tokens": 512
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `model` | string | Yes | — | Model name |
| `messages` | array | Yes | — | Conversation messages |
| `stream` | bool | No | `false` | Enable SSE streaming |
| `temperature` | float | No | `0.7` | Sampling temperature (0.0–2.0) |
| `max_tokens` | int | No | `null` | Maximum response tokens |

**Response (200, non-streaming):**

```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1711186800,
  "model": "llama3.2:3b",
  "choices": [
    {
      "index": 0,
      "message": { "role": "assistant", "content": "Hello! How can I help?" },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 8,
    "total_tokens": 18
  }
}
```

**Response (streaming):** `Content-Type: text/event-stream`

Follows OpenAI's streaming delta format. The first chunk carries the `role` delta. The stream ends with `data: [DONE]`.

```
data: {"id":"chatcmpl-abc","object":"chat.completion.chunk","created":1711186800,"model":"llama3.2:3b","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}

data: {"id":"chatcmpl-abc","object":"chat.completion.chunk","created":1711186800,"model":"llama3.2:3b","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}

data: [DONE]
```

Note: This endpoint does not use the standard Manic AI response envelope — it returns raw OpenAI-format JSON for client compatibility.

**Error responses:**

| Status | Description |
|--------|-------------|
| 502 | Upstream inference error |

---

### GET /v1/models (OpenAI-compatible alias)

Return available models in the OpenAI `GET /v1/models` response format. Sources models from Ollama.

**Auth required:** API Key
**Rate limit:** None

**Response (200):**

```json
{
  "object": "list",
  "data": [
    {
      "id": "llama3.2:3b",
      "object": "model",
      "created": 1711186800,
      "owned_by": "ollama"
    }
  ]
}
```

Note: This response does not use the standard Manic AI envelope — it matches the OpenAI format directly for client compatibility.

---

## Error Reference

### HTTP Status Codes

| Status | Meaning |
|--------|---------|
| 200 | Request succeeded |
| 201 | Resource created |
| 202 | Accepted for asynchronous processing |
| 400 | Bad request — invalid parameters or payload |
| 401 | Unauthorized — missing or invalid API key |
| 403 | Forbidden — insufficient permissions (admin required) |
| 404 | Resource not found (also used for IDOR prevention) |
| 409 | Conflict — resource already exists |
| 415 | Unsupported media type |
| 422 | Unprocessable entity — validation failed |
| 429 | Too many requests — rate limit exceeded |
| 500 | Internal server error |
| 502 | Bad gateway — upstream service unavailable |
| 503 | Service unavailable — required dependency offline |

### Common Error Patterns

**Missing API key:**
```json
{ "success": false, "data": null, "error": { "code": "UNAUTHORIZED", "message": "Missing API key" }, "meta": null }
```

**Rate limit exceeded:**
```json
{ "success": false, "data": null, "error": { "code": "RATE_LIMITED", "message": "Rate limit exceeded" }, "meta": null }
```

**Validation error:**
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
      { "field": "chunk_size", "message": "value must be greater than 0", "code": "greater_than" }
    ]
  },
  "meta": null
}
```

**Upstream service unavailable:**
```json
{ "success": false, "data": null, "error": { "code": "SERVICE_UNAVAILABLE", "message": "Embedding service unavailable" }, "meta": null }
```

### Retry Strategy

For `502` and `503` responses, use exponential backoff starting at 1 second with a maximum of 5 retries. `429` responses include a `Retry-After` header when available.

Do not retry `4xx` errors other than `429` — these indicate a problem with the request that will not resolve by retrying.

---

## Environment Variables Reference

Key settings that affect API behavior:

| Variable | Default | Description |
|----------|---------|-------------|
| `API_SECRET_KEY` | — | Required: shared API key or set `ALLOW_UNAUTHENTICATED=true` |
| `AUTH_MODE` | `single` | `single` or `multi_user` |
| `INFERENCE_BACKEND` | `ollama` | `ollama`, `vllm`, `openai`, or `anthropic` |
| `CHAT_MODEL` | `llama3.2:3b` | Default chat model |
| `EMBEDDING_MODEL` | `bge-m3` | Default embedding model (1024-dim) |
| `VECTOR_DIMENSION` | `1024` | Must match the embedding model's output dimension |
| `RAG_TOP_K` | `5` | Default number of RAG context chunks |
| `RAG_THRESHOLD` | `0.7` | Default minimum similarity score for RAG |
| `RATE_LIMIT_PER_MINUTE` | `60` | General rate limit |
| `RATE_LIMIT_INGEST_PER_MINUTE` | `10` | Ingest-specific rate limit |
| `RATE_LIMIT_MUTATIONS_PER_MINUTE` | `30` | Mutation (write) rate limit |
| `RATE_LIMIT_AGENT_PER_MINUTE` | `20` | Agent endpoint rate limit |
| `OLLAMA_URL` | `http://ollama:11434` | Ollama service URL |
| `QDRANT_URL` | `http://qdrant:6333` | Qdrant service URL |
| `SUPABASE_DB_URL` | — | Required: PostgreSQL connection string |
| `REDIS_URL` | `redis://ai-redis:6379` | Redis connection URL |
