# Manic AI - Complete Guide

**Version:** 2.0.0
**Last Updated:** February 2026

Welcome to the ultimate guide for deploying, configuring, and maintaining the Manic AI stack. This document synthesizes all system architectures, setup steps, RAG documentation, and security into one centralized reference.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Prerequisites & Configuration](#2-prerequisites--configuration)
3. [Installation & Launch](#3-installation--launch)
4. [Core Services Setup](#4-core-services-setup)
5. [RAG & API Usage](#5-rag--api-usage)
6. [Workflows & UIs](#6-workflows--uis)
7. [Maintenance & Troubleshooting](#7-maintenance--troubleshooting)
8. [Senior Developer Standards](#8-senior-developer-standards)

---

## 1. Architecture Overview

### Network & Container Map

Manic AI is deployed within a secure Tailscale VPN environment (`100.111.244.124` by default) across an `ai-network` Docker bridge with 18 containers.

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

#### Layered Services (Quick Reference Box)

╔══════════════════════════════════════════════════════════════════╗
║                    MANIC AI QUICK REFERENCE                       ║
╠══════════════════════════════════════════════════════════════════╣
║  KEY URLS (Append <http://100.111.244.124>):                       ║
║  • Chat Frontend: :3000 (Next.js) or :3006 (Open WebUI)         ║
║  • API / Docs:    :8081 | :8081/docs                             ║
║  • Database:      :3005 (Supabase Studio) or :5433 (direct PSQL)║
║  • Workflows:     :5679 (n8n)                                    ║
║  • LLM:           :11434 (Ollama)                                ║
║  • Flowise:       :3008 (Visual LLM Builder)                     ║
║  • Langfuse:      :3007 (Observability)                          ║
║  • SearXNG:       :8889 (Private Search)                         ║
║  • Supabase API:  :8001 (Gateway Auth/REST)                      ║
╚══════════════════════════════════════════════════════════════════╝

### Data Flow

**Chat Flow:** User → Frontend(:3000) → API(:8081) → Ollama(:11434) → Response (saved to DB, traced to Langfuse)
**RAG Flow (Query):** Query → API(:8081) → Ollama (embed query) → [Supabase or Qdrant] → Context → Ollama → Response

---

## 2. Prerequisites & Configuration

### Hardware Needs

| Resource | Minimum | Recommended (Total needed ~20GB) |
|----------|---------|-------------|
| RAM | 16 GB | 32 GB |
| CPU | 4 cores | 8+ cores |
| Disk | 40 GB free | 100 GB+ SSD |
| GPU | Optional | NVIDIA 6GB+ VRAM (for faster inference) |

### Software Needs

1. **Ubuntu 22.04 LTS** (or compatible Linux) or **Docker Desktop** (v4.25+) with WSL2
2. **Docker Engine 24.0+** & **Docker Compose v2.20+**
3. **Tailscale** for secure networking.

### Initial Configuration (`.env`)

You must configure the environment before launching. Critical settings:

```bash
# Network
BIND_IP=100.111.244.124  # Change this to your Tailscale IP, or 127.0.0.1 for local

# Required URL updates (Replace 100.111.244.124 with your IP)
SUPABASE_URL=http://100.111.244.124:8001
API_EXTERNAL_URL=http://100.111.244.124:8001
GOTRUE_SITE_URL=http://100.111.244.124:3006
SUPABASE_PUBLIC_URL=http://100.111.244.124:8001

# Database (Ensure simple alphanumeric password, no slashes or equals!)
POSTGRES_PASSWORD=<your-secure-password>
GOTRUE_DB_DATABASE_URL=postgresql://postgres:<your-secure-password>@supabase-db:5432/postgres?search_path=auth
```

---

## 3. Installation & Launch

### Step 1: Install Docker & Tailscale (Linux Setup)

```bash
sudo apt update && sudo apt upgrade -y
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER && newgrp docker
curl -fsSL https://tailscale.com/install.sh | sh && sudo tailscale up
```

### Step 2: Clone and Prep

```bash
git clone <repository-url> Manic-AI
cd Manic-AI
cp .env.example .env # (Edit .env as detailed in section 2)

# Generate Frontend Lock for Docker builder
cd frontend
npm install --legacy-peer-deps
cd ..
```

### Step 3: Launch Services

You can do a staged launch to catch issues or launch everything at once.

**Full Launch:**

```bash
sudo docker compose up -d --build
```

*(First launch pulls ~10GB of images and takes 5-15 mins.)*

### Step 4: Pull AI Models

Ollama starts empty. You must pull the inference and embedding models:

```bash
sudo docker exec ollama ollama pull llama3.2:3b         # Default chat
sudo docker exec ollama ollama pull nomic-embed-text    # RAG Embeddings (Required)
```

### Step 5: Verify the Stack

Check container statuses and ensure the API connects gracefully to databases:

```bash
sudo docker compose ps
curl http://100.111.244.124:8081/health
# Expect: {"status":"healthy","services":{"database":"connected","ollama":"healthy"}}
```

---

## 4. Core Services Setup

### Supabase Architecture & Schemas

Supabase runs 8 internal containers (DB, Auth, Meta, Data APIs, Studio).
Access **Supabase Studio** at `http://100.111.244.124:3005` (Username: admin, Password from `.htpasswd`).

**RAG Schema Overview:**

- `rag.documents`: Upload metadata
- `rag.chunks`: Chunked text + `nomic-embed-text` vectors (768-dim)
- **Functions included:** `rag.search_similar_chunks` (Vector only), `rag.hybrid_search` (Vector + Keyword)

**Using Auth:**
You can call the Kong API Gateway (`:8001`) with your `ANON_KEY` to sign-up users or acquire JWT tokens.

### Dual RAG Databases (Postgres pgvector vs Qdrant)

Manic AI supports simultaneous dual vector databases.

- **Supabase (pgvector):** Hybrid search (Vector + BM25 keyword), complex SQL row-level filtering.
- **Qdrant (:6333):** High-speed pure vector search for massive volume.

---

## 5. RAG & API Usage

Your unified API (`:8081`) exposes inference, DB, and RAG operations.

### Example: Ingesting a Document

```bash
curl -X POST http://100.111.244.124:8081/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Manic AI uses Ollama for local LLMs.",
    "filename": "about-manic.txt"
  }'
```

### Example: Searching Documents

```bash
curl -X POST http://100.111.244.124:8081/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What local LLM?", "top_k": 5, "use_hybrid": true
  }'
```

### Example: Chatting with RAG Context

```bash
curl -X POST http://100.111.244.124:8081/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "How do local LLMs work in Manic?"}],
    "use_rag": true
  }'
```

You can also stream responses using `/chat/stream` which returns Server-Sent Events (SSE).

---

## 6. Workflows & UIs

### Primary Frontend (Next.js - :3000)

Provides basic chat, document uploading, model selection, and dashboard metrics.

### Open WebUI (:3006)

A feature-rich "ChatGPT-like" alternative interface. Auto-connects to your local Ollama instance. Set up RAG via the settings.

### n8n (Workflow Automation - :5679)

Automate ingestion and actions without coding (e.g., Slack to API webhook, auto-backup DB). Default login: `markvitale21@gmail.com / L0c4Linf0$`.

### Flowise (Visual AI Flows - :3008)

Drag-and-drop LLM pipelines (e.g., loading docs into Qdrant, complex agents with web search). Credentials set in `.env` (FLOWISE_PASSWORD).

### Langfuse (Observability - :3007)

Trace interactions, monitor latency, calculate prompt token cost, and debug. Integrate Langfuse by passing keys to the API or adding a Langfuse node in Flowise.

### SearXNG (Private Web Search - :8889)

Allows the LLM to search the web without tracking. Accessible by `/chat` (with `use_web_search: true`) or Flowise nodes.

---

## 7. Maintenance & Troubleshooting

### Daily/Weekly Operations

```bash
# View specific container logs
sudo docker compose logs -f api
sudo docker compose logs -f ai-supabase-auth

# Restart individual services
sudo docker compose restart frontend

# Clean unused resources
docker system prune -a

# Backup DB
sudo docker exec ai-supabase-db pg_dump -U postgres postgres > backup_$(date).sql
```

### Common Issues

1. **Supabase Auth Keeps Crashing (`ai-supabase-auth`)**
   - **Cause:** `GOTRUE_DB_DATABASE_URL` password in `.env` contains special chars (`/` or `=`).
   - **Fix:** Update to alphanumeric.
2. **Ollama Dependency Unhealthy**
   - **Cause:** Ollama container starts slow or lacks `curl`.
   - **Fix:** Ensure healthcheck in docker compose uses `ollama list`.
3. **Frontend Cannot Connect to API**
   - **Cause:** `BIND_IP` mismatch.
   - **Fix:** Enter API URL exactly as `http://100.111.244.124:8081` in the frontend UI gear settings.
4. **Empty Search Results in RAG**
   - **Fix:** Lower the threshold (`0.5`) in search options, or ensure `nomic-embed-text` was pulled successfully.

---

## 8. Senior Developer Standards

When extending Manic AI, adhere closely to these technical standards (Derived from `SKILLS.md`):

- **Architecture Respect:** Frontend talks to API. Never directly to databases or Ollama.
- **Python (FastAPI):** Use Pydantic schemas. Write `async` handlers. Never hardcode secrets.
- **TypeScript (Next.js):** Use Server Components by default. Avoid `any` types. Handle all loading/empty states cleanly.
- **Data Layers:** Use migrations. Avoid ad-hoc SQL interpolation. Recognize if pgvector (hybrid+RLS) or Qdrant (high volume vectors) is the right tool for a specific addition.
- **Simplicity & Reversibility:** Prefer boring, proven code. Scope PRs tightly. Write self-documenting code with explicit error bounds.
