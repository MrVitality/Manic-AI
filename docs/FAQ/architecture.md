# Manic AI - Architecture Map (Whiteboard Reference)

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
