# Manic AI Developer Guide

A practical reference for contributors. Covers local setup, backend and frontend development, testing, code style, and the full workflow for adding a new feature.

---

## Quick Start (3 commands)

```bash
make setup    # Install Python + Node deps, copy .env.example → .env, install pre-commit hooks
make up       # Start all Docker services
make verify   # Verify the setup is correct
```

After `make setup`, edit `.env` with your secrets before running `make up`.

Then pull the required ML models:

```bash
docker exec ollama ollama pull bge-m3
docker exec ollama ollama pull llama3.2:3b
```

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.11+ | API backend |
| Node.js | 18+ | Frontend |
| npm | 9+ | Frontend package manager |
| Docker Engine | 24+ | All services |
| Docker Compose plugin | 2.20+ | Service orchestration |

---

## Project Structure

```
Manic-AI/
├── api/                    FastAPI backend (Python)
│   ├── app.py              App factory — middleware, router registration
│   ├── main.py             ASGI entry point
│   ├── config.py           Pydantic Settings (all env vars)
│   ├── auth.py             API key authentication dependency
│   ├── database.py         asyncpg connection pool init/close
│   ├── dependencies.py     FastAPI DI factories (get_db, get_http_client, etc.)
│   ├── routers/            HTTP route handlers (one file per resource group)
│   ├── services/           Business logic (RAG, embedding, chunking, agents, etc.)
│   ├── repositories/       Data access layer (Supabase, Qdrant, Redis)
│   ├── schemas/            Pydantic request/response models
│   ├── middleware/         Starlette middlewares (auth, rate limit, guardrails, etc.)
│   ├── plugins/            Plugin loading and tool registry
│   ├── alembic/            Database migration scripts
│   └── tests/              pytest test suite
│
├── frontend/               Next.js frontend (TypeScript)
│   ├── app/                Next.js 15 App Router pages
│   │   ├── chat/           Chat UI
│   │   ├── dashboard/      Dashboard with metrics
│   │   ├── documents/      Document management
│   │   ├── rag/            RAG center
│   │   ├── settings/       Advanced settings
│   │   ├── models/         Model management
│   │   ├── arena/          A/B testing arena
│   │   ├── workbench/      LLM workbench
│   │   └── tools/          Tools page
│   ├── components/         Shared React components
│   ├── lib/                Zustand stores, API client, utilities
│   │   ├── store.ts        Main Zustand store
│   │   └── stores/         Specialized stores
│   ├── hooks/              Custom React hooks
│   ├── types/              TypeScript type definitions
│   ├── __tests__/          Jest unit tests
│   └── e2e/                Playwright E2E tests
│
├── caddy/                  Caddyfile (reverse proxy + TLS)
├── monitoring/             Prometheus, Grafana, Alertmanager, Loki configs
├── supabase/               PostgreSQL init SQL, Kong config, Studio auth
├── searxng/                SearXNG configuration
├── scripts/                Setup and utility scripts
├── n8n-workflows/          Pre-built n8n automation workflows
├── obsidian-agent/         Paddy AI agent for Obsidian vaults
├── docker-compose.yml      All services
├── docker-compose.dev.yml  Development overrides
├── docker-compose.prod.yml Production overrides
├── Makefile                Developer shortcuts
└── .env.example            Environment variable template
```

---

## Local Development

### Start services with hot reload

```bash
make dev
# Equivalent to:
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

The dev overrides mount source code volumes so changes reflect without rebuilding images.

### View logs

```bash
make logs                          # All services
docker compose logs api -f         # API only
docker compose logs frontend -f    # Frontend only
```

### Service URLs (local)

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| API | http://localhost:8081 |
| API docs (Swagger) | http://localhost:8081/docs |
| API docs (ReDoc) | http://localhost:8081/redoc |
| Open WebUI | http://localhost:3006 |
| Langfuse | http://localhost:3007 |
| n8n | http://localhost:5679 |
| Flowise | http://localhost:3008 |
| SearXNG | http://localhost:8889 |
| Supabase Studio | http://localhost:3005 |
| Qdrant UI | http://localhost:6333/dashboard |
| Grafana | http://localhost:3001 |

---

## Backend Development

### Installing Python dependencies

```bash
cd api && pip install -r requirements.txt
# Development extras:
pip install -r requirements-dev.txt
```

### Running the API without Docker

For rapid iteration, run the API directly:

```bash
cd api
SUPABASE_DB_URL=postgresql://postgres:pass@localhost:5433/postgres \
REDIS_URL=redis://localhost:6380 \
API_SECRET_KEY=dev-secret \
ALLOW_UNAUTHENTICATED=true \
uvicorn api.main:app --reload --port 8081
```

### Adding a New Endpoint

1. **Create or update a router file** in `api/routers/`. Follow the existing pattern:
   - Define request/response Pydantic models (or add them to `api/schemas/`)
   - Use `from api.schemas.envelope import ok` for consistent response wrapping
   - Add `@limiter.limit(...)` decorator for rate limiting
   - Use `Depends(require_api_key)` for authentication (already applied at router level in `app.py`)

2. **Create a service function** in `api/services/` for any business logic that isn't trivial.

3. **Register the router** in `api/app.py`:
   ```python
   from api.routers import my_router
   v1_router.include_router(my_router.router, dependencies=auth_dep, tags=["my-tag"])
   ```

4. **Add to `_TAGS_METADATA`** in `api/app.py` for Swagger docs.

5. **Write tests** (see Testing section).

### Dependency Injection

The `api/dependencies.py` file exposes these FastAPI dependencies:

| Function | Returns | Description |
|----------|---------|-------------|
| `get_db` | `asyncpg.Pool` | DB connection pool (raises if unavailable) |
| `get_db_optional` | `Optional[asyncpg.Pool]` | DB pool or None |
| `get_http_client` | `httpx.AsyncClient` | Shared async HTTP client |
| `get_langfuse` | `Langfuse | None` | Langfuse tracing client |
| `get_redis` | `RedisCacheRepository | None` | Redis repository |
| `get_document_repo` | `SupabaseDocumentRepository` | Document data access |
| `get_qdrant_repo` | `QdrantVectorRepository` | Qdrant data access |

### Database Migrations (Alembic)

Create a new migration:

```bash
cd api
python -m alembic revision --autogenerate -m "add my_table"
```

Apply migrations:

```bash
python -m alembic upgrade head
```

Rollback one step:

```bash
python -m alembic downgrade -1
```

Migration scripts live in `api/alembic/versions/`. The connection URL is read from `SUPABASE_DB_URL` at runtime.

### Configuration

All settings are defined in `api/config.py` as a `Settings(BaseSettings)` class. Add new config values there:

```python
MY_NEW_SETTING: str = "default_value"
```

Access it anywhere via:

```python
from api.config import settings
settings.MY_NEW_SETTING
```

Settings are validated on startup. Missing required values raise a `ValueError` immediately.

---

## Frontend Development

### Tech Stack

| Library | Version | Purpose |
|---------|---------|---------|
| Next.js | 15.x | App Router, SSR, API routes |
| React | 18.x | UI components |
| TypeScript | 5.7 | Type safety |
| Tailwind CSS | 3.4 | Utility-first styling |
| Zustand | 5.0 | Client-side state management |
| SWR | 2.4 | Server state / data fetching |
| `@supabase/supabase-js` | 2.47 | Optional Supabase client-side auth |

### Running the frontend without Docker

```bash
cd frontend
npm ci
NEXT_PUBLIC_API_URL=http://localhost:8081 npm run dev
```

The frontend runs on port 3000. Hot Module Replacement is enabled.

### Environment Variables (Frontend)

Prefix with `NEXT_PUBLIC_` to expose to the browser:

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_API_URL` | Backend API base URL |
| `NEXT_PUBLIC_OLLAMA_URL` | Ollama URL for direct model access |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase Kong gateway URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anonymous key |

### State Management

Main state lives in `frontend/lib/store.ts` (Zustand with `persist` middleware → `localStorage`). Specialized stores are in `frontend/lib/stores/`.

All components use the `'use client'` directive since the frontend is client-rendered.

### Styling Conventions

- CSS variables for theming: `--bg-primary`, `--accent-blue`, `--text-primary`, etc. (defined in `app/globals.css`)
- Glassmorphism aesthetic: glass-card pattern with gradient accents on a dark background
- All chart components are pure CSS/SVG — no chart libraries

### Adding a New Page

1. Create a directory in `frontend/app/`:
   ```
   frontend/app/my-feature/page.tsx
   ```

2. Add `'use client'` at the top if the page uses state or browser APIs.

3. Add a navigation link in the `AppShell` component (`components/AppShell.tsx`).

---

## Testing

### API Tests (pytest)

```bash
make test-api
# or
cd api && python -m pytest --tb=short -q

# With coverage report:
make test-coverage
cd api && python -m pytest --cov=. --cov-report=term-missing --tb=short
```

Test files are in `api/tests/`. Naming convention: `test_<module>.py`.

The test suite includes 50+ test files covering routers, services, middleware, auth, embeddings, RAG, chunking, PII detection, and more.

**Key fixtures** (in `api/tests/conftest.py`):
- `mock_db` — async mock of asyncpg.Pool
- `mock_http_client` — httpx.AsyncClient mock
- `test_client` — FastAPI TestClient with `ALLOW_UNAUTHENTICATED=true`

Tests that need a real database use the `SUPABASE_DB_URL` env var (set in CI via a Postgres service container).

### Frontend Unit Tests (Jest)

```bash
make test-frontend
# or
cd frontend && npm test

# With coverage:
cd frontend && npm run test:coverage
```

Test files are in `frontend/__tests__/`. Uses `@testing-library/react` + `jest-environment-jsdom`.

### E2E Tests (Playwright)

```bash
make test-e2e
# or
cd frontend && npx playwright test

# Interactive UI mode:
make test-e2e-ui
```

E2E tests are in `frontend/e2e/`. Playwright config is at `frontend/playwright.config.ts`. Tests require the full stack to be running.

---

## Code Style

### Python (API)

- **Linter/formatter:** `ruff` — configuration in `pyproject.toml`
- Run: `make lint-api` (check) or `make lint-fix` (auto-fix + format)
- All public functions must have docstrings
- Use type hints throughout
- Error handling: always raise `HTTPException` with appropriate status codes and human-readable `detail`
- Never use bare `except:` — catch specific exception types
- Logging: use `logger = logging.getLogger(__name__)` at module level

### TypeScript (Frontend)

- **Linter:** ESLint with `eslint-config-next`
- Run: `make lint-frontend`
- All React components must have `'use client'` directive if they use state or effects
- Prefer functional components with hooks over class components
- Use TypeScript `interface` for prop types, `type` for unions and aliases

### Pre-commit Hooks

Hooks run automatically on `git commit`. Install with:

```bash
make setup-hooks
# or
pre-commit install
```

Hooks include: trailing whitespace, YAML/JSON validation, end-of-file fixes, ruff linting.

---

## Git Workflow

### Branch Strategy

- `Manic-AI-Prod` — main production branch (protected, requires PR)
- Feature branches: `feat/my-feature`
- Bug fixes: `fix/my-bug`

### Commit Format

```
<type>: <description>

<optional body>
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `ci`

Examples:
```
feat: add TOTP-based MFA to auth flow
fix: prevent duplicate document ingestion by content hash
test: add coverage for cross-encoder reranker
```

### Pull Request Process

1. Create a feature branch from `Manic-AI-Prod`
2. Write tests first (TDD)
3. Implement the feature
4. Ensure all tests pass: `make test`
5. Ensure linting passes: `make lint`
6. Open a PR against `Manic-AI-Prod`
7. CI runs all checks automatically
8. PR requires review approval before merge

---

## Adding a Feature End-to-End

Example: adding a `POST /v1/summarize` endpoint.

### 1. Write the schema

Create or update `api/schemas/summarize.py`:

```python
from pydantic import BaseModel, Field

class SummarizeRequest(BaseModel):
    text: str = Field(..., max_length=50_000)
    max_sentences: int = Field(default=3, ge=1, le=20)

class SummarizeResponse(BaseModel):
    summary: str
    sentence_count: int
```

### 2. Write the service

Create `api/services/summarize.py`:

```python
async def summarize_text(text: str, max_sentences: int, http_client) -> dict:
    # Business logic here
    ...
```

### 3. Write tests first

Create `api/tests/test_router_summarize.py`:

```python
def test_summarize_success(test_client):
    resp = test_client.post("/v1/summarize", json={"text": "Long text...", "max_sentences": 2})
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    assert "summary" in resp.json()["data"]
```

### 4. Write the router

Create `api/routers/summarize.py`:

```python
from fastapi import APIRouter, Depends
import httpx
from api.dependencies import get_http_client
from api.schemas.envelope import ok
from api.schemas.summarize import SummarizeRequest
from api.services.summarize import summarize_text

router = APIRouter()

@router.post("/summarize", response_model=None, tags=["summarize"])
async def summarize(
    body: SummarizeRequest,
    client: httpx.AsyncClient = Depends(get_http_client),
):
    result = await summarize_text(body.text, body.max_sentences, client)
    return ok(result)
```

### 5. Register the router

In `api/app.py`:

```python
from api.routers import summarize as summarize_router
v1_router.include_router(summarize_router.router, dependencies=auth_dep, tags=["summarize"])
```

Add to `_TAGS_METADATA`:

```python
{"name": "summarize", "description": "Text summarization"},
```

### 6. Add frontend UI (optional)

Create `frontend/app/tools/summarize/page.tsx` with the `'use client'` directive and call the API via `fetch` or SWR.

### 7. Run tests and lint

```bash
make test-api lint-api
```

---

## Makefile Reference

```bash
make help         # Show all available commands
make up           # Start all services
make down         # Stop all services
make dev          # Start with dev overrides (hot reload)
make logs         # Tail all service logs
make status       # Show service status
make test         # Run all tests (API + frontend)
make test-api     # Run Python tests
make test-frontend  # Run Jest tests
make test-coverage  # Run API tests with coverage report
make test-e2e     # Run Playwright E2E tests
make lint         # Run all linters
make lint-fix     # Auto-fix Python lint issues
make build        # Build all Docker images
make clean        # Stop services and remove all volumes
make monitoring   # Start monitoring stack
make backup       # pg_dump → backups/
make sdk          # Generate TypeScript SDK from OpenAPI spec
make verify       # Verify dev environment setup
```
