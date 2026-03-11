# Repo Cleanup & Production Packaging — Design Spec

**Date:** 2026-03-11
**Status:** Approved
**Approach:** Option A — Gitignore-in-place

---

## Goal

Clean up the Manic-AI repository for sharing/publishing by:
1. Removing junk files and empty ghost directories
2. Organizing all project documentation into `docs/FAQ/`
3. Fixing `.gitignore` to properly exclude AI tooling and build artifacts
4. Expanding `README.md` into a proper project overview

---

## What Is the User's Code

**Tracked (application code):**
- `api/` — FastAPI backend (routers, services, config, database)
- `frontend/` — Next.js frontend (components, hooks, lib, types, app)
- `docker-compose.yml` — 18-service Docker orchestration
- `scripts/setup_qdrant.py` — Qdrant collection setup utility
- `searxng/` — SearXNG search engine config
- `supabase/` — Supabase DB config
- `sql-parts/` — SQL schema fragments
- `CLAUDE.md` — Project instructions (stays at root; required by Claude Code)
- `LICENSE`

**Not the user's code (gitignored):**
- `.claude/` — Claude Code hooks, agents, commands, scripts, settings
- `.agent/` — Agent skills package (third-party)
- `.gemini/` — Gemini CLI config
- `everything-claude-code/` — Claude skills package
- `.vscode/` — Editor config
- `.playwright-mcp/` — Playwright MCP config
- `frontend/node_modules/`, `frontend/.next/` — build artifacts

---

## Repository Structure After Cleanup

```
Manic-AI/
├── api/
│   ├── routers/         (analytics, chat, collections, documents, health,
│   │                     ingest, models, qdrant, search, system)
│   ├── services/        (chunking, embedding, health_logger, langfuse, rag)
│   ├── app.py / config.py / database.py / http_client.py / main.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── app/ components/ hooks/ lib/ types/ public/
│   ├── package.json
│   └── Dockerfile
├── docs/
│   ├── FAQ/
│   │   ├── README.md            ← index / table of contents
│   │   ├── install.md           ← from INSTALL.md
│   │   ├── architecture.md      ← from ARCHITECTURE_MAP.md
│   │   ├── rag-guide.md         ← from RAG_GUIDE.md
│   │   ├── supabase-setup.md    ← from SUPABASE_SETUP.md
│   │   ├── services.md          ← from SERVICE_UTILIZATION_PLAN.md
│   │   ├── implementation.md    ← from IMPLEMENTATION.md
│   │   ├── complete-guide.md    ← from MANIC_AI_COMPLETE_GUIDE.md
│   │   └── skills.md            ← from SKILLS.md
│   └── assets/
│       ├── dashboard-overview.png
│       ├── dashboard-services.png
│       ├── rag-center.png
│       └── settings-view.png
├── scripts/
│   └── setup_qdrant.py
├── searxng/ / supabase/ / sql-parts/
├── docker-compose.yml
├── CLAUDE.md            ← stays at root (Claude Code convention)
├── README.md            ← expanded: overview, stack, quick-start, docs link
├── LICENSE
└── .gitignore           ← expanded (see below)
```

---

## Junk Removal

| Item | Action |
|------|--------|
| `manic@72.61.78.179` | **Deleted** |
| `frontend/{app,components,...}` (3 empty ghost dirs) | **Deleted** |
| Root PNG screenshots (4 files) | **Moved** to `docs/assets/` |

---

## .gitignore Additions

```
# AI Tooling (local dev only)
.claude/
.agent/
.gemini/
everything-claude-code/

# Editor
.vscode/
.playwright-mcp/

# Frontend build artifacts
frontend/node_modules/
frontend/.next/

# Python
__pycache__/
*.pyc
.venv/
venv/

# Environment & secrets
.env
.env.*
!.env.example

# OS
.DS_Store
Thumbs.db

# Logs
*.log
```

---

## README.md Structure

```
# Manic-AI
Full-stack AI platform with RAG capabilities.

## Tech Stack
Frontend: Next.js 14 + TypeScript + Tailwind
API: FastAPI (Python)
Vector DB: Supabase (pgvector + BM25) + Qdrant
LLM: Ollama (local inference)
Infrastructure: Docker Compose (18 services)

## Quick Start
1. cp .env.example .env  (fill in values)
2. docker compose up -d
3. Open http://localhost:3000

## Documentation
→ docs/FAQ/
```

---

## Commit Plan

1. `chore: delete junk files and empty ghost directories`
2. `chore: move screenshots to docs/assets/`
3. `docs: move project guides into docs/FAQ/ with index`
4. `chore: expand .gitignore for tooling, build artifacts, secrets`
5. `docs: expand README with project overview and quick-start`

---

## Out of Scope

- Docker hardening / production secrets management
- Changes to `api/` or `frontend/` application code
- Rewriting existing documentation content
