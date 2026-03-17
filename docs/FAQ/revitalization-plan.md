# Manic-AI Revitalization Plan

**Date**: 2026-03-17
**Status**: Proposed
**Scope**: Full-stack architecture overhaul across API, Frontend, Infrastructure, and AI/RAG pipeline

---

## Executive Summary

Manic-AI is a functionally complete RAG prototype (~1,200 lines API, ~4,000 lines frontend) with solid algorithmic choices (RRF hybrid search, HNSW indexes, Redis-cached embeddings). However, it has outgrown its prototype architecture. This plan proposes a phased revitalization across 4 tracks, prioritized by impact and dependency order.

**Critical blockers found:**
- API Dockerfile is broken (only copies `main.py`, missing entire application)
- Hardcoded secrets in docker-compose.yml and kong.yml
- No tests anywhere in the codebase
- No URL routing in frontend (single-page with state-based view switching)
- No context window management (LLM calls will silently fail on long conversations)
- No error boundaries (any render error crashes the entire app)

---

## Phase 0: Emergency Fixes (Day 1)

| # | Fix | File | Effort |
|---|-----|------|--------|
| 0.1 | Fix Dockerfile — `COPY main.py .` → `COPY . .`, add USER, add `redis` to requirements.txt | `api/Dockerfile`, `api/requirements.txt` | 15 min |
| 0.2 | Remove hardcoded secrets — default password `ManicAI2024!`, JWT keys in kong.yml, Tailscale IP | `docker-compose.yml`, `supabase/kong.yml`, `scripts/setup_qdrant.py` | 30 min |
| 0.3 | Create `.env.example` with all required env vars | Project root | 15 min |
| 0.4 | Consolidate 3 conflicting DB schema files into one canonical source | `supabase/` | 1 hr |

---

## Phase 1: Foundation (Weeks 1-2)

### Track A — API Architecture

**1A.1 Pydantic Settings** — Replace raw `os.getenv` in `config.py` with `BaseSettings` model. Type validation, `.env` support, startup-time validation.

**1A.2 Repository Layer** — Create `api/repositories/` with protocol abstractions (VectorStore, DocumentStore, CacheStore). All raw SQL and HTTP calls move behind interfaces. Enables provider swapping and testing.

**1A.3 Extract Business Logic** — Move orchestration from routers to services (`ingestion.py`, `search.py`, `chat.py`, `ollama.py`). Target: every router handler under 15 lines.

**1A.4 FastAPI DI** — Replace global mutable singletons with `app.state` + `Depends()`. Makes testing trivial via `dependency_overrides`.

**1A.5 Standardize Responses** — Response envelope pattern with `success`, `data`, `error`, `meta` fields. Add `response_model` and OpenAPI `tags` to every route.

**1A.6 API Versioning** — Prefix all routes with `/v1/`.

### Track B — Frontend Architecture

**1B.1 Real Next.js Routing** — Convert `activeView` state switching to App Router pages (`/chat`, `/dashboard`, `/rag`, `/documents`, `/models`, `/settings`). Gives browser history, bookmarks, and per-route code splitting.

**1B.2 Normalize State** — Remove redundant `currentConversation` (derive via selector). Split monolithic `useChatStore` into focused stores (conversations, models, documents, settings, UI). Per-feature error state.

**1B.3 SWR for Data Fetching** — Replace all `useEffect + fetch` with SWR. Gives caching, deduplication, retry, stale-while-revalidate.

**1B.4 Error Boundaries** — Wrap each route/view. Add global fallback.

**1B.5 Shared UI Components** — Extract duplicated icons (5+ files), toggle switches (4+ copies), modals, empty states, toast notifications.

### Track C — Infrastructure

**1C.1 Network Segmentation** — Split single flat Docker network into `db-network`, `app-network`, `tools-network`.

**1C.2 Health Checks** — Add to remaining 14/19 services without them.

**1C.3 Log Management** — Add `max-size: 10m, max-file: 3` to all services.

**1C.4 Dev Override** — Create `docker-compose.dev.yml` with hot-reload volumes and dev commands.

**1C.5 GPU Support** — Add nvidia device reservation for Ollama.

### Track D — Tests

**1D.1 API Tests** — `conftest.py`, fixtures, unit + integration tests. 80% coverage target.

**1D.2 Frontend Tests** — Jest + RTL. Stores, hooks, critical components. 80% coverage target.

---

## Phase 2: Quality & Performance (Weeks 3-4)

### RAG Pipeline Improvements

**2A.1 Context Window Management** — Token counter + budget allocation (system prompt, RAG context, history). Truncate oldest messages when exceeded.

**2A.2 Cross-Encoder Reranking** — Retrieve top-20, rerank to top-5. Estimated precision: 60-70% → 80-85%.

**2A.3 Semantic Chunking** — Recursive splitter (markdown headers → paragraphs → sentences). Parent-child chunks (200-token retrieval, 1000-token context).

**2A.4 Citation Tracking** — Populate existing `rag.messages.citations` column. Return source attribution to frontend.

**2A.5 Store Original Content** — Add `raw_content TEXT` to `rag.documents` for re-chunking.

### Frontend Performance

**2B.1 Code Splitting** — `next/dynamic` for Dashboard, RagCenter, AdvancedSettings, DocumentManager, ModelManager.

**2B.2 Message List** — `React.memo` on MessageItem + virtualization via `@tanstack/react-virtual`.

**2B.3 Bundle** — Tree-shake react-syntax-highlighter. Audit with `@next/bundle-analyzer`.

**2B.4 SSE/Polling** — Gate polling on `!isStreaming`.

### Accessibility

**2C.1 ARIA** — dialog, tablist, tab, navigation, switch roles throughout.

**2C.2 Focus** — Trap in modals, return to trigger on close.

**2C.3 Light Theme** — Create actual light-mode CSS variable values (currently identical to dark).

---

## Phase 3: Production Readiness (Weeks 5-8)

| # | Deliverable | Description |
|---|------------|-------------|
| 3.1 | Async Ingestion | POST returns document_id immediately. Background worker handles pipeline. Poll/SSE for status. |
| 3.2 | Document Preprocessing | File upload support: PDF (pymupdf), DOCX (python-docx), HTML (beautifulsoup4), Markdown |
| 3.3 | DB Migrations | Adopt Alembic. Consolidate schemas. Versioned, reproducible migrations. |
| 3.4 | Monitoring | Prometheus + Grafana + cAdvisor. FastAPI instrumentator. Alert rules. |
| 3.5 | Reverse Proxy | Traefik or nginx. Single entry point. TLS, rate limiting, access logs. |
| 3.6 | CI/CD | On PR: lint+test+build. On merge: deploy. Nightly: security scan. |
| 3.7 | RAG Evaluation | Golden test set (50-100 pairs). Precision@5, Recall@10, MRR, NDCG. LLM-as-judge. |
| 3.8 | Feedback Loop | Thumbs up/down on responses. Link to conversation + chunks. Refine retrieval. |

---

## Phase 4: Scale (Weeks 9-12+)

| # | Deliverable | Description |
|---|------------|-------------|
| 4.1 | Horizontal API | Stateless API behind load balancer. Session affinity for SSE. Shared Redis. |
| 4.2 | Embedding Migration | Multi-dimension collections. Background re-embedding. Vector quantization. |
| 4.3 | Vector DB Consolidation | Resolve pgvector vs Qdrant dual-write. Recommend pgvector primary. |
| 4.4 | Advanced RAG | Query expansion/HyDE, conversation-aware retrieval, MMR diversity, multi-language FTS. |

---

## Architecture: Current → Target

### Current
```
[Browser] → [Next.js SPA (all client)] → [FastAPI (logic in routers)]
                                              ├→ raw SQL to Supabase
                                              ├→ raw HTTP to Qdrant
                                              ├→ raw HTTP to Ollama
                                              └→ raw Redis calls
```

### Target
```
[Browser] → [Next.js App Router]     → [FastAPI thin routers]
             ├ /chat                      ├→ ChatService
             ├ /dashboard                 ├→ SearchService (+ reranker)
             ├ /rag                       ├→ IngestionService (async)
             ├ /documents                 ├→ OllamaClient
             ├ /models                    │
             └ /settings                  ├→ VectorStore protocol
                                          │   ├ SupabaseVector
                                          │   └ QdrantVector
                                          ├→ DocumentStore protocol
                                          │   └ SupabaseDocuments
                                          └→ CacheStore protocol
                                              └ RedisCache
```

---

## Decision Log

| Decision | Options | Chosen | Rationale |
|----------|---------|--------|-----------|
| Data fetching | SWR vs TanStack Query | SWR | Lighter, Vercel ecosystem |
| Migration tool | Alembic vs Supabase CLI | Alembic | Python-native, asyncpg compat |
| Task queue | Celery vs ARQ vs BackgroundTasks | ARQ | Lightweight, async-native, uses existing Redis |
| Vector DB primary | pgvector vs Qdrant | pgvector | Co-located, good hybrid search |
| Reranker hosting | Ollama vs in-process | Ollama | Consistent infra, no new deps |

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking API consumers during refactor | High | API versioning (/v1/) preserves old routes |
| Alembic conflicts with existing DDL | Medium | Run baseline migration from current schema |
| Reranker adds latency | Medium | Make optional via query param |
| Store refactor breaks UI | Medium | Incremental migration, one store at a time |
