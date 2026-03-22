# Manic-AI

> Full-stack AI platform with RAG, local LLMs, and a self-hosted tool ecosystem.

![Tests](https://img.shields.io/badge/tests-333%20passing-brightgreen)
![Python](https://img.shields.io/badge/python-3.11-blue)
![Next.js](https://img.shields.io/badge/next.js-15.3.9-black)
![Docker](https://img.shields.io/badge/docker-compose-2496ED)

---

## Architecture

```
 Browser
    │
    ▼
┌─────────────────────┐     ┌──────────────────────────────────────────┐
│  Frontend           │     │  Tools & Observability                   │
│  Next.js 15 :3000   │     │  Open WebUI   :3006  (chat interface)    │
└────────┬────────────┘     │  n8n          :5679  (workflow automation)│
         │ REST/SSE         │  Flowise      :3008  (LLM flow builder)  │
         ▼                  │  Langfuse     :3007  (LLM tracing)       │
┌─────────────────────┐     └──────────────────────────────────────────┘
│  API                │
│  FastAPI    :8081   │     ┌──────────────────────────────────────────┐
└──┬──────────────────┘     │  Monitoring (--profile monitoring)       │
   │                        │  Prometheus   :9090                      │
   ├──► Ollama      :11434  │  Grafana      :3009                      │
   ├──► Supabase    :5433   └──────────────────────────────────────────┘
   │    (pgvector + BM25)
   ├──► Qdrant      :6333
   ├──► Redis       :6379
   └──► SearXNG     :8889
```

---

## Quick Start

```bash
cp .env.example .env          # fill in required values (see Configuration)
make setup                    # install deps + create .env scaffold
make up                       # start all 18 services
python scripts/setup_qdrant.py  # initialize vector collections
```

Open [http://localhost:3000](http://localhost:3000)

---

## Development

| Command | Description |
|---------|-------------|
| `make dev` | Hot-reload mode (mounts source via docker-compose.dev.yml) |
| `make test` | Run all tests — 333 passing |
| `make test-coverage` | API tests with coverage report |
| `make lint` | ruff (Python) + eslint (frontend) |
| `make lint-fix` | Auto-fix Python lint issues |
| `make logs` | Tail all service logs |
| `make status` | Show Docker service health |
| `make monitoring` | Start Prometheus + Grafana |
| `make clean` | Stop services and remove volumes |

---

## API Endpoints

Base URL: `http://localhost:8081`

| Router | Prefix | Purpose |
|--------|--------|---------|
| health | `/health` | Service liveness + readiness |
| chat | `/chat` | LLM chat with RAG (SSE streaming) |
| search | `/search` | Hybrid vector + keyword search |
| ingest | `/ingest` | Document ingestion pipeline |
| documents | `/documents` | CRUD for ingested documents |
| collections | `/collections` | Supabase vector collection management |
| qdrant | `/qdrant` | Qdrant collection management |
| analytics | `/analytics` | Usage and retrieval analytics |
| system | `/system` | System info and service status |
| models | `/models` | Available Ollama model listing |
| agent | `/agent` | Autonomous agent endpoints |
| eval | `/eval` | RAG evaluation and scoring |

---

## Configuration

Copy `.env.example` to `.env` and fill in required values before starting:

| Variable | Required | Description |
|----------|----------|-------------|
| `POSTGRES_PASSWORD` | Yes | Supabase PostgreSQL password |
| `ANON_KEY` | Yes | Supabase JWT for anon role |
| `SERVICE_ROLE_KEY` | Yes | Supabase JWT for service_role |
| `REDIS_PASSWORD` | Yes | Redis auth password |
| `QDRANT_API_KEY` | Yes | Qdrant API key (any secret string) |
| `N8N_PASSWORD` | Yes | n8n admin password |
| `SEARXNG_SECRET_KEY` | Yes | Generate: `openssl rand -hex 32` |
| `FLOWISE_PASSWORD` | Yes | Flowise admin password |
| `LANGFUSE_DB_PASSWORD` | Yes | Langfuse PostgreSQL password |
| `LANGFUSE_SECRET` | Yes | NextAuth secret for Langfuse |
| `CHAT_MODEL` | No | Default: `llama3.2:3b` |
| `EMBEDDING_MODEL` | No | Default: `bge-m3` (1024 dims) |
| `ANTHROPIC_API_KEY` | No | Required for Obsidian agent (Paddy) |

---

## Monitoring

Enable the monitoring stack (Prometheus + Grafana):

```bash
make monitoring
# or: docker compose --profile monitoring up -d
```

| Service | URL |
|---------|-----|
| Grafana | http://localhost:3009 |
| Prometheus | http://localhost:9090 |

---

## Testing

```bash
make test            # run all 333 tests (API + frontend)
make test-coverage   # API tests with line-level coverage report
make test-api        # API only (pytest)
make test-frontend   # frontend only (jest)
```

---

## Project Structure

```
frontend/           Next.js 15 UI (TypeScript + Tailwind + Zustand)
api/
  main.py           FastAPI entry point
  config.py         Environment-based configuration
  database.py       asyncpg connection pool
  routers/          12 HTTP route handlers
  services/         RAG, embedding, chunking, ingestion logic
supabase/           DB config and SQL migrations
sql-parts/          SQL schema fragments
scripts/            Setup utilities (Qdrant init, etc.)
searxng/            SearXNG configuration
obsidian-agent/     Paddy — Obsidian RAG sidecar
docker-compose.yml  18-service orchestration
Makefile            Development commands
.env.example        Environment variable reference
```

---

## License

See [LICENSE](LICENSE).
