# Manic-AI

> **READ FIRST**: [`docs/manic-ai-prd.md`](docs/manic-ai-prd.md) — Product Requirements Document. Covers vision, users, goals, non-goals, requirements by phase, current state, success metrics, and open questions. **Future Claude Code sessions should load this before planning any new work on the real estate hub pivot.**

## Project Overview

Manic-AI is being pivoted from a general AI platform into the **central operations hub for Mark Vitale's real estate business** (Vera Cohen Realty, Capital Region NY). Phases 1-2 shipped (lead intake + scoring + drip, content generation + Fair Housing gate). Phases 3-5 planned in the PRD.

Core stack under the pivot:

**Stack:**
- **Frontend**: Next.js (TypeScript) — `frontend/`
- **API**: FastAPI (Python) — `api/`
- **Vector DBs**: Supabase (pgvector + BM25), Qdrant
- **AI Inference**: Ollama (local LLMs)
- **Infrastructure**: Docker Compose, nginx, Tailscale VPN

## Dev Servers

Use the Claude Preview tool to start services:
- `Frontend (Next.js)` — port 3000
- `Backend API (FastAPI)` — port 8081

## Architecture

```
frontend/        Next.js UI (TypeScript)
api/             FastAPI backend (Python)
  routers/       HTTP route handlers
  services/      Business logic (RAG, embedding, chunking)
searxng/         Self-hosted search engine
supabase/        DB config and SQL migrations
sql-parts/       SQL schema fragments
scripts/         Setup utilities
docker-compose.yml  Full service orchestration
```

## Key Services (Docker)

| Service | Port | Purpose |
|---------|------|---------|
| Frontend | 3000 | Next.js UI |
| API | 8081 | FastAPI backend |
| Open WebUI | 3006 | Chat interface |
| SearXNG | 8889 | Search engine |
| n8n | 5679 | Workflow automation |
| Flowise | 3008 | LLM flow builder |
| Langfuse | 3007 | LLM tracing |
| Ollama | 11434 | Local LLM inference |
| Qdrant | 6333 | Vector database |
| Supabase | 5433 | Postgres + pgvector |

## Running Tests

```bash
# API (Python)
cd api && pytest

# Frontend (Next.js)
cd frontend && npm test
```

## Agents Available

This project has the full `everything-claude-code` agent suite in `.claude/agents/`:
- `planner` — implementation planning
- `architect` — system design
- `tdd-guide` — test-driven development
- `code-reviewer` — quality review
- `security-reviewer` — security analysis
- `build-error-resolver` — fix build errors
- `python-reviewer` — Python-specific review
- `e2e-runner` — end-to-end testing
- `refactor-cleaner` — dead code cleanup
- `doc-updater` — documentation updates

## Commands Available

Key slash commands (`.claude/commands/`):
- `/plan` — implementation planning
- `/tdd` — test-driven development workflow
- `/code-review` — quality review
- `/build-fix` — fix build errors
- `/python-review` — Python code review
- `/e2e` — E2E test generation
- `/learn` — extract patterns from sessions
- `/verify` — verification before completing

## Development Notes

- Python package manager: pip (with `.venv` or `venv`)
- Frontend package manager: npm
- API entry point: `api/main.py`
- Config: `api/config.py` (reads from environment)
- Database: `api/database.py` (asyncpg connection pool)
