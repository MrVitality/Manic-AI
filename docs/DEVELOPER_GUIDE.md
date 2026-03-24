# Manic-AI Developer Guide

A practical reference for contributors joining the project. This guide covers
everything from cloning the repo to shipping a complete feature — backend route,
service layer, tests, and frontend page included.

---

## Table of Contents

1. [Quick Start](#1-quick-start)
2. [Prerequisites](#2-prerequisites)
3. [Project Structure](#3-project-structure)
4. [Local Development](#4-local-development)
5. [Backend Development](#5-backend-development)
6. [Frontend Development](#6-frontend-development)
7. [Testing](#7-testing)
8. [Code Style](#8-code-style)
9. [Git Workflow](#9-git-workflow)
10. [Adding a New Feature — End-to-End Walkthrough](#10-adding-a-new-feature--end-to-end-walkthrough)
11. [Database Migrations](#11-database-migrations)
12. [Environment Variables](#12-environment-variables)
13. [CI/CD](#13-cicd)
14. [Useful Commands](#14-useful-commands)

---

## 1. Quick Start

Three commands to go from zero to running dev servers:

```bash
git clone <repo-url> && cd Manic-AI
make setup          # install Python + Node deps, copy .env, install pre-commit hooks
make dev            # start all services with hot-reload
```

The UI will be available at `http://localhost:3000` and the API at
`http://localhost:8081`. After the first run, open `.env` and fill in the
required secrets before the API will fully start (see
[Environment Variables](#12-environment-variables)).

---

## 2. Prerequisites

| Tool | Minimum version | Purpose |
|------|----------------|---------|
| Python | 3.11 | FastAPI backend |
| Node.js | 20 (engines field requires >=18) | Next.js frontend |
| Docker + Docker Compose | v2 (compose v2 plugin) | All backing services |
| Ollama | latest | Local LLM inference |
| Git | any recent | Version control |

Optional but recommended:

- `ruff` installed globally (`pip install ruff`) for editor integration
- `pre-commit` (installed automatically by `make setup`)

**Verify your setup:**

```bash
make verify         # runs scripts/verify_setup.py
```

---

## 3. Project Structure

```
Manic-AI/
├── api/                    FastAPI backend (Python)
│   ├── alembic/            Database migration scripts
│   │   └── versions/       Individual migration files (001_, 002_, ...)
│   ├── middleware/         Request-level concerns (auth, rate-limit, audit, metrics)
│   ├── repositories/       Data-access layer (Supabase, Qdrant, Redis)
│   │   └── protocols.py    Protocol (interface) definitions — VectorStore, DocumentStore, CacheStore
│   ├── routers/            HTTP route handlers, one file per feature area
│   ├── schemas/            Pydantic request/response models + shared envelope
│   ├── services/           Business logic (RAG, chunking, embedding, agents, ...)
│   ├── tests/              pytest test suite
│   ├── app.py              FastAPI application factory + middleware registration
│   ├── config.py           Settings (pydantic-settings, reads from env)
│   ├── database.py         asyncpg connection pool
│   ├── main.py             Uvicorn entry point
│   └── requirements*.txt   Runtime and dev dependencies
│
├── frontend/               Next.js UI (TypeScript)
│   ├── app/                Next.js App Router pages
│   │   ├── chat/           Chat interface
│   │   ├── dashboard/      Service dashboard
│   │   ├── documents/      Document management
│   │   ├── models/         Model browser
│   │   ├── rag/            RAG pipeline center
│   │   ├── settings/       User settings
│   │   └── ...             (workbench, arena, tools, admin)
│   ├── components/         Reusable React components
│   ├── lib/                Utilities and state
│   │   ├── api.ts          Typed API client functions
│   │   ├── store.ts        Root Zustand store
│   │   └── stores/         Domain-scoped Zustand slices
│   ├── __tests__/          Jest unit tests
│   └── e2e/                Playwright E2E specs
│
├── supabase/               SQL schema and pgvector setup
├── sql-parts/              SQL schema fragments
├── scripts/                Setup, migration, SDK generation utilities
├── docs/                   Project documentation
├── docker-compose.yml      Full production service stack
├── docker-compose.dev.yml  Dev overrides (hot-reload, debug ports)
├── docker-compose.prod.yml Production tuning
├── Makefile                Developer shortcuts
└── .github/
    ├── workflows/ci.yml    GitHub Actions CI pipeline
    ├── CODEOWNERS          Auto-review assignments
    └── PULL_REQUEST_TEMPLATE.md
```

---

## 4. Local Development

### Starting services with hot-reload

The dev compose file mounts local source directories into the containers so
changes are picked up instantly without rebuilding images:

```bash
make dev
# equivalent to:
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

What the dev override adds on top of the base stack:

- **API**: uvicorn `--reload` flag; `LOG_LEVEL=debug`
- **Frontend**: `NODE_ENV=development` with `WATCHPACK_POLLING=true` for
  filesystem watches on Windows/WSL
- **Qdrant**: web UI ports `6333` and `6334` exposed on `$BIND_IP`
- **n8n**: debug log level

### Stopping and cleaning up

```bash
make down           # stop containers (volumes preserved)
make clean          # stop containers AND remove all volumes
```

### Tailing logs

```bash
make logs                              # all services
docker compose logs -f api frontend    # specific services
```

### Service status

```bash
make status         # docker compose ps
```

### Running services individually (outside Docker)

Useful when iterating quickly on the API or frontend without rebuilding containers:

```bash
# API — from repo root
cd api
pip install -r requirements-dev.txt
SUPABASE_DB_URL=postgresql://... REDIS_URL=redis://localhost:6379 \
  uvicorn api.main:app --reload --host 0.0.0.0 --port 8081

# Frontend — from repo root
cd frontend
npm ci --legacy-peer-deps
npm run dev
```

---

## 5. Backend Development

The API is a **FastAPI** application structured in three clear layers:

```
Router  ->  Service  ->  Repository
```

- **Routers** (`api/routers/`) handle HTTP concerns: path parameters, request
  validation, authentication dependencies, and response serialization. They
  delegate all logic to services.
- **Services** (`api/services/`) contain business logic. They call repositories
  for data access and other services for cross-cutting concerns.
- **Repositories** (`api/repositories/`) are the only layer that touches
  databases or external stores. They implement the protocols defined in
  `repositories/protocols.py`.

### Adding a new route

1. Create a new file in `api/routers/` (or add to an existing one if the
   domain fits):

```python
# api/routers/notes.py
from fastapi import APIRouter, Depends
from api.auth import require_api_key
from api.schemas.envelope import ok
from api.services.notes import NoteService

router = APIRouter(prefix="/notes", tags=["notes"])


@router.get("/")
async def list_notes(service: NoteService = Depends()):
    notes = await service.list()
    return ok(notes)
```

2. Register the router in `api/app.py`:

```python
from api.routers import notes as notes_router

v1.include_router(notes_router.router)
```

### Response envelope

All endpoints return a consistent JSON envelope via helpers from
`api/schemas/envelope.py`:

```python
from api.schemas.envelope import ok, fail

# Success
return ok({"id": "abc", "title": "Hello"})
# {"success": true, "data": {...}, "error": null, "meta": null}

# Error
return fail("NOT_FOUND", "Note not found")
# {"success": false, "data": null, "error": {"code": "NOT_FOUND", "message": "..."}, "meta": null}
```

### Adding a service

Services are plain Python classes. Inject dependencies through `__init__` so
they are testable with mocks:

```python
# api/services/notes.py
from typing import List, Dict, Any
from api.repositories.protocols import DocumentStore


class NoteService:
    def __init__(self, store: DocumentStore):
        self._store = store

    async def list(self) -> List[Dict[str, Any]]:
        return await self._store.list_documents()
```

### Repository pattern

Define the interface contract in `api/repositories/protocols.py` as a
`Protocol`. Concrete implementations (`SupabaseDocuments`, `QdrantVector`,
`RedisCache`) satisfy the protocol structurally — no inheritance needed.
Business logic depends only on the protocol, making storage backends
swappable and services trivially mockable in tests.

### Configuration

All settings are in `api/config.py` as a pydantic-settings `Settings` class.
Add a new setting:

```python
class Settings(BaseSettings):
    MY_NEW_SETTING: str = "default_value"
```

Access it anywhere via the singleton:

```python
from api.config import settings

value = settings.MY_NEW_SETTING
```

The value is read from the environment variable `MY_NEW_SETTING` at startup.

---

## 6. Frontend Development

The frontend is a **Next.js 15** application using the App Router. All
components that need interactivity use the `'use client'` directive. State is
managed with **Zustand** stores.

### Adding a new page

Pages live under `frontend/app/`. Each route segment is a directory containing
a `page.tsx` and optionally an `error.tsx`:

```
frontend/app/
  notes/
    page.tsx        # the page component
    error.tsx       # error boundary (copy from another route)
```

```typescript
// frontend/app/notes/page.tsx
'use client'

import { useEffect } from 'react'
import { useNotesStore } from '@/lib/stores/notesStore'

export default function NotesPage() {
  const { notes, fetchNotes } = useNotesStore()

  useEffect(() => { fetchNotes() }, [fetchNotes])

  return (
    <div className="glass-card p-6">
      {notes.map(n => <div key={n.id}>{n.title}</div>)}
    </div>
  )
}
```

Add a navigation link in the sidebar component to make the page discoverable.

### Adding a Zustand store

Domain-scoped stores live in `frontend/lib/stores/`. Each store is its own
file with its own state and actions:

```typescript
// frontend/lib/stores/notesStore.ts
import { create } from 'zustand'
import { apiGet } from '@/lib/api'

interface Note { id: string; title: string }
interface NotesState {
  notes: Note[]
  fetchNotes: () => Promise<void>
}

export const useNotesStore = create<NotesState>((set) => ({
  notes: [],
  fetchNotes: async () => {
    const data = await apiGet<Note[]>('/notes')
    set({ notes: data ?? [] })
  },
}))
```

The root store at `frontend/lib/store.ts` uses `persist` middleware with
`localStorage` key `manic-ai-storage` for fields that need to survive page
refreshes. Domain stores do not need to be registered there unless they
require persistence.

### API client

All backend calls go through the typed helpers in `frontend/lib/api.ts`. Do
not use `fetch` directly in components. The client handles the base URL,
authentication headers, and unwrapping the response envelope.

### CSS conventions

- CSS custom properties for theming: `--bg-primary`, `--accent-blue`,
  `--text-primary`, etc. — defined in `app/globals.css`
- Utility class `glass-card` for the glassmorphism card style
- Tailwind CSS for layout and spacing

### Generating the TypeScript SDK

After changing API schemas, regenerate the typed client:

```bash
make sdk
# runs scripts/generate_sdk.py -> reads OpenAPI spec -> writes frontend types
```

---

## 7. Testing

### API tests (pytest)

Tests live in `api/tests/`. The suite covers routers, services, repositories,
middleware, and pure-logic modules. The naming convention is:

| Pattern | What it covers |
|---------|---------------|
| `test_router_*.py` | HTTP endpoint tests via `TestClient` |
| `test_*_service.py` or `test_*.py` | Service and utility unit tests |
| `test_*_pure.py` | Side-effect-free logic with no mocking |
| `conftest.py` | Shared fixtures (app instance, mock DB, etc.) |

Run all API tests:

```bash
make test-api
# or with coverage:
make test-coverage
```

Run a specific test file:

```bash
cd api && python -m pytest tests/test_router_chat.py -v
```

Writing a new test — follow the existing `test_router_*.py` pattern:

```python
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from api.app import app

client = TestClient(app)

def test_list_notes_returns_200():
    with patch("api.routers.notes.NoteService.list", new_callable=AsyncMock) as mock:
        mock.return_value = [{"id": "1", "title": "Hello"}]
        response = client.get("/v1/notes/", headers={"X-API-Key": "test"})
    assert response.status_code == 200
    assert response.json()["success"] is True
```

CI runs tests against real Postgres (port 5432) and Redis (port 6379) service
containers. Locally, the Docker stack provides the same services.

### Frontend tests (Jest)

Tests live in `frontend/__tests__/` mirroring the source layout:

```
__tests__/
  components/     Component rendering tests (React Testing Library)
  hooks/          Custom hook tests
  lib/            Utility and API client tests
  stores/         Zustand store action tests
  smoke.test.ts   Basic import/smoke checks
```

Run all frontend tests:

```bash
make test-frontend
# or with coverage:
cd frontend && npm run test:coverage
```

Run in watch mode during development:

```bash
cd frontend && npm run test:watch
```

### E2E tests (Playwright)

Specs live in `frontend/e2e/` and cover critical user flows:

| Spec | What it tests |
|------|--------------|
| `navigation.spec.ts` | Route transitions, sidebar links |
| `sidebar.spec.ts` | Sidebar expand/collapse, active states |
| `dashboard.spec.ts` | Dashboard tabs, service status display |
| `settings.spec.ts` | Settings sections and form interactions |

Run against a running dev stack:

```bash
make test-e2e           # headless
make test-e2e-ui        # with Playwright UI for debugging
```

### Run everything

```bash
make test               # api + frontend (not E2E)
```

---

## 8. Code Style

### Python (ruff)

The project uses **ruff** for both linting and formatting. It is configured
via `.pre-commit-config.yaml` (ruff v0.8.6).

```bash
make lint-api           # check only
make lint-fix           # auto-fix then format
```

Key rules from `.editorconfig`:

- 4-space indentation
- 120-character line length
- LF line endings, UTF-8, trailing newline

### TypeScript / JavaScript (ESLint + tsc)

```bash
make lint-frontend      # eslint
cd frontend && npx tsc --noEmit   # type-check only
```

Key rules from `.editorconfig`:

- 2-space indentation for `.ts`, `.tsx`, `.js`, `.jsx`
- LF line endings

### Editor config

The `.editorconfig` at the repo root enforces consistent whitespace across
all file types. Install the EditorConfig plugin for VS Code, JetBrains, or
your editor of choice.

### Pre-commit hooks

`make setup` (or `make setup-hooks`) installs pre-commit hooks that run
automatically on `git commit`:

| Hook | What it does |
|------|-------------|
| `ruff` | Lint + auto-fix Python |
| `ruff-format` | Format Python |
| `trailing-whitespace` | Strip trailing spaces |
| `end-of-file-fixer` | Ensure files end with a newline |
| `check-yaml` / `check-json` | Syntax validation |
| `check-added-large-files` | Block files larger than 500 KB |
| `no-commit-to-branch` | Prevent direct commits to `main` |
| `detect-private-key` | Block accidental secret commits |

---

## 9. Git Workflow

### Branch naming

Work on feature branches off `Manic-AI-Prod`:

```
feat/short-description
fix/issue-description
refactor/area-name
docs/what-was-documented
```

### Commit messages

Follow **Conventional Commits**:

```
<type>: <short description>

<optional body — what and why, not how>
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `ci`

Examples:

```
feat: add notes router with list and create endpoints
fix: handle empty embedding vector in hybrid search
docs: add database migration section to developer guide
```

### Pull requests

1. Open a PR against `Manic-AI-Prod`.
2. Fill in the PR template (summary, type of change, testing checklist,
   security checklist).
3. The CI pipeline must be green before merging.
4. `@MrVitality` is auto-requested as reviewer via CODEOWNERS for all paths.
   Security-sensitive paths (`api/auth.py`, `api/middleware/`,
   `api/plugins/code_exec/`) require an explicit approval.

---

## 10. Adding a New Feature — End-to-End Walkthrough

This walkthrough adds a minimal "Notes" feature from scratch: a backend route,
a service, tests, and a frontend page.

### Step 1 — Create the Pydantic schema

```python
# api/schemas/notes.py
from pydantic import BaseModel

class NoteCreate(BaseModel):
    title: str
    body: str

class NoteRead(BaseModel):
    id: str
    title: str
    body: str
```

### Step 2 — Add the service

```python
# api/services/notes.py
import uuid
from typing import List
from api.schemas.notes import NoteCreate, NoteRead


class NoteService:
    """In-memory stand-in — replace with a repository call for persistence."""

    _store: dict[str, NoteRead] = {}

    async def list(self) -> List[NoteRead]:
        return list(self._store.values())

    async def create(self, payload: NoteCreate) -> NoteRead:
        note = NoteRead(id=str(uuid.uuid4()), **payload.model_dump())
        self._store[note.id] = note
        return note
```

### Step 3 — Add the router

```python
# api/routers/notes.py
from fastapi import APIRouter, Depends
from api.auth import require_api_key
from api.schemas.envelope import ok
from api.schemas.notes import NoteCreate
from api.services.notes import NoteService

router = APIRouter(prefix="/notes", tags=["notes"])


@router.get("/", dependencies=[Depends(require_api_key)])
async def list_notes(service: NoteService = Depends()):
    return ok(await service.list())


@router.post("/", dependencies=[Depends(require_api_key)], status_code=201)
async def create_note(payload: NoteCreate, service: NoteService = Depends()):
    return ok(await service.create(payload))
```

### Step 4 — Register the router in app.py

Open `api/app.py` and add alongside the existing router imports:

```python
from api.routers import notes as notes_router
# ...
v1.include_router(notes_router.router)
```

### Step 5 — Write the API test

```python
# api/tests/test_router_notes.py
from fastapi.testclient import TestClient
from api.app import app

client = TestClient(app)
HEADERS = {"X-API-Key": "test"}


def test_create_and_list_note():
    resp = client.post("/v1/notes/", json={"title": "Hi", "body": "World"}, headers=HEADERS)
    assert resp.status_code == 201
    note_id = resp.json()["data"]["id"]

    resp = client.get("/v1/notes/", headers=HEADERS)
    assert resp.status_code == 200
    ids = [n["id"] for n in resp.json()["data"]]
    assert note_id in ids
```

Run it:

```bash
cd api && python -m pytest tests/test_router_notes.py -v
```

### Step 6 — Add the frontend store

```typescript
// frontend/lib/stores/notesStore.ts
import { create } from 'zustand'
import { apiGet, apiPost } from '@/lib/api'

interface Note { id: string; title: string; body: string }
interface NotesState {
  notes: Note[]
  fetchNotes: () => Promise<void>
  createNote: (title: string, body: string) => Promise<void>
}

export const useNotesStore = create<NotesState>((set, get) => ({
  notes: [],
  fetchNotes: async () => {
    const data = await apiGet<Note[]>('/notes')
    set({ notes: data ?? [] })
  },
  createNote: async (title, body) => {
    await apiPost('/notes', { title, body })
    await get().fetchNotes()
  },
}))
```

### Step 7 — Add the frontend page

```typescript
// frontend/app/notes/page.tsx
'use client'

import { useEffect, useState } from 'react'
import { useNotesStore } from '@/lib/stores/notesStore'

export default function NotesPage() {
  const { notes, fetchNotes, createNote } = useNotesStore()
  const [title, setTitle] = useState('')

  useEffect(() => { fetchNotes() }, [fetchNotes])

  return (
    <div className="glass-card p-6 space-y-4">
      <h1 className="text-xl font-semibold">Notes</h1>
      <div className="flex gap-2">
        <input
          className="flex-1 bg-transparent border border-white/20 rounded px-3 py-1"
          value={title}
          onChange={e => setTitle(e.target.value)}
          placeholder="New note title"
        />
        <button
          onClick={() => { createNote(title, ''); setTitle('') }}
          className="px-4 py-1 rounded bg-blue-600 hover:bg-blue-500"
        >
          Add
        </button>
      </div>
      <ul className="space-y-2">
        {notes.map(n => <li key={n.id} className="text-sm">{n.title}</li>)}
      </ul>
    </div>
  )
}
```

### Step 8 — Add a frontend unit test

```typescript
// frontend/__tests__/stores/notesStore.test.ts
import { renderHook, act } from '@testing-library/react'
import { useNotesStore } from '@/lib/stores/notesStore'

jest.mock('@/lib/api', () => ({
  apiGet: jest.fn().mockResolvedValue([{ id: '1', title: 'Test', body: '' }]),
  apiPost: jest.fn().mockResolvedValue({ id: '2', title: 'New', body: '' }),
}))

it('fetchNotes populates the store', async () => {
  const { result } = renderHook(() => useNotesStore())
  await act(async () => { await result.current.fetchNotes() })
  expect(result.current.notes).toHaveLength(1)
  expect(result.current.notes[0].title).toBe('Test')
})
```

---

## 11. Database Migrations

The API uses **Alembic** for schema migrations. Migration files live in
`api/alembic/versions/` and are applied in sequence (currently 001 through 006).

### Creating a new migration

```bash
cd api
alembic revision --autogenerate -m "add_notes_table"
```

This generates a new file in `api/alembic/versions/`. Always review the
generated file before running it — autogenerate can miss complex changes
(custom types, partial indexes) or produce incorrect diffs.

### Applying migrations

```bash
cd api
alembic upgrade head          # apply all pending migrations
alembic upgrade +1            # apply exactly one migration
```

In CI, `alembic upgrade head` runs automatically before the test suite against
the Postgres service container.

### Rolling back

```bash
cd api
alembic downgrade -1          # roll back the most recent migration
alembic downgrade base        # roll back everything (destructive)
```

### Connection configuration

Alembic reads `SUPABASE_DB_URL` from the environment at runtime. The
`api/alembic.ini` file intentionally leaves `sqlalchemy.url` blank — `env.py`
injects the value from the environment variable so no credentials are ever
stored in config files.

### Useful inspection commands

```bash
alembic current        # show current revision applied to the DB
alembic history        # list all migrations in order
alembic show <rev>     # show details of a specific revision
```

---

## 12. Environment Variables

There is no committed `.env` file. `make setup` copies `.env.example` to `.env`
if it does not already exist. Edit `.env` before starting the stack.

The authoritative reference for every variable is `api/config.py`. Key groups:

| Group | Variables |
|-------|----------|
| Database | `SUPABASE_DB_URL` (required) |
| Cache | `REDIS_URL` |
| Vector DB | `QDRANT_URL`, `QDRANT_API_KEY` |
| Search | `SEARXNG_URL`, `SEARXNG_SECRET_KEY` |
| Inference | `OLLAMA_URL`, `INFERENCE_BACKEND`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` |
| Models | `CHAT_MODEL`, `EMBEDDING_MODEL`, `VECTOR_DIMENSION` |
| Auth | `API_SECRET_KEY`, `AUTH_MODE` |
| Observability | `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`, `SENTRY_DSN`, `OTEL_ENABLED`, `OTEL_EXPORTER_OTLP_ENDPOINT` |
| Rate limits | `RATE_LIMIT_PER_MINUTE`, `RATE_LIMIT_INGEST_PER_MINUTE` |
| Security | `GUARDRAILS_ENABLED`, `PII_REDACTION_ENABLED` |
| Infrastructure | `BIND_IP`, `PUBLIC_DOMAIN`, `POSTGRES_PASSWORD` |

`SUPABASE_DB_URL` and `API_SECRET_KEY` are validated at startup by
pydantic-settings and raise a clear error if missing. The only exception is
when `ALLOW_UNAUTHENTICATED=true` is set, which is reserved for CI test runs.

---

## 13. CI/CD

The pipeline is defined in `.github/workflows/ci.yml` and runs on every pull
request and push to `Manic-AI-Prod`, plus a nightly security scan at 03:00 UTC.
Jobs run concurrently where possible; CI is cancelled for a given ref if a
newer run starts (`concurrency: cancel-in-progress: true`).

### Pipeline overview

| Job | Trigger | What it checks |
|-----|---------|---------------|
| `api-lint` | all events | `ruff check api/` |
| `pre-commit` | all events | All pre-commit hooks |
| `api-test` | all events | pytest with coverage; Alembic migrations; real Postgres + Redis |
| `frontend-lint` | all events | `next lint` (ESLint) |
| `frontend-typecheck` | all events | `tsc --noEmit` |
| `frontend-test` | all events | Jest with coverage |
| `build-api` | after lint + test pass | Docker build; Trivy container scan; push to GHCR on merge |
| `build-frontend` | after lint + test pass | `next build`; Docker build; push to GHCR on merge |
| `docker-compose-check` | all events | `docker compose config` syntax validation |
| `security-scan` | all events + nightly | pip-audit, Bandit SAST, npm audit, Trivy FS scan, Gitleaks |
| `sql-check` | all events | SQL schema syntax validation against Postgres |
| `deploy` | push to `Manic-AI-Prod` only | SSH deploy to production; health check |

### Fixing a failing build

**`api-lint` fails** — run `make lint-fix` locally, commit the changes.

**`api-test` fails** — run `make test-api` locally to reproduce. The CI
environment sets `SUPABASE_DB_URL` and `REDIS_URL` — ensure your local test
run has equivalent environment variables, or start the dev stack first.

**`frontend-typecheck` fails** — run `cd frontend && npx tsc --noEmit`
locally. Fix all type errors; do not suppress with `// @ts-ignore` unless the
third-party type definition is genuinely wrong.

**`frontend-test` fails** — run `make test-frontend` locally. Do not disable
assertions or commit tests marked `.only`.

**`security-scan` flags a vulnerability** — these jobs have
`continue-on-error: true` so they do not block a merge, but SARIF reports are
uploaded to GitHub Security. Address CRITICAL and HIGH findings promptly.

**`deploy` fails** — check the Actions log for the SSH step. Common causes:
production host unreachable, `docker compose pull` timeout, or a migration
failure. Roll back with `alembic downgrade -1` on the server if needed.

### Container registry

On merge to `Manic-AI-Prod`, images are pushed to GHCR:

```
ghcr.io/mrvitality/manic-ai-api:latest
ghcr.io/mrvitality/manic-ai-api:<git-sha>
ghcr.io/mrvitality/manic-ai-frontend:latest
ghcr.io/mrvitality/manic-ai-frontend:<git-sha>
```

---

## 14. Useful Commands

### Make targets

```bash
make help           # list all targets with descriptions

# Service lifecycle
make up             # start full stack (production mode)
make dev            # start with hot-reload dev overrides
make down           # stop all services
make clean          # stop + delete all volumes (destructive)
make logs           # tail all logs
make status         # show container states
make monitoring     # start Prometheus + Grafana profile

# Testing
make test           # api + frontend (not E2E)
make test-api       # pytest only
make test-frontend  # jest only
make test-coverage  # pytest with coverage report
make test-e2e       # playwright headless
make test-e2e-ui    # playwright with UI

# Linting
make lint           # api + frontend
make lint-api       # ruff check
make lint-frontend  # eslint
make lint-fix       # ruff --fix + ruff format

# Building
make build          # build both Docker images locally
make build-api      # api image only
make build-frontend # frontend image only

# Setup
make setup          # full first-time setup
make setup-deps     # install Python + Node deps only
make setup-hooks    # install pre-commit hooks only
make verify         # check environment is correctly configured
make sdk            # regenerate TypeScript SDK from OpenAPI spec
make backup         # pg_dump to backups/
```

### Common Docker Compose commands

```bash
# Restart a single service
docker compose restart api

# Rebuild and restart after Dockerfile changes
docker compose up -d --build api

# Open a shell inside a running container
docker compose exec api bash
docker compose exec frontend sh

# View environment variables inside a container
docker compose exec api env | sort

# Run a one-off command
docker compose run --rm api python scripts/verify_setup.py

# Scale a stateless service
docker compose up -d --scale api=2
```

### Alembic quick reference

```bash
cd api
alembic revision --autogenerate -m "describe_change"
alembic upgrade head
alembic downgrade -1
alembic current        # show current revision
alembic history        # show full migration history
```

### Python environment

```bash
# Install all deps (runtime + dev)
cd api && pip install -r requirements-dev.txt

# Run a single test with verbose output
cd api && python -m pytest tests/test_router_chat.py -v -s

# Check for import errors in the whole package
cd api && python -c "from api.app import app; print('OK')"
```

### Frontend quick reference

```bash
cd frontend

npm run dev           # dev server on :3000
npm run build         # production build
npm run lint          # eslint
npm test              # jest (single run)
npm run test:watch    # jest watch mode
npm run test:coverage # jest with coverage report
npx tsc --noEmit      # type-check only
npx playwright test   # E2E tests (requires running dev stack)
```
