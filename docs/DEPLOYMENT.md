# Manic AI Deployment Guide

This guide covers deploying Manic AI from scratch on a Linux server through to a production HTTPS setup with SSL/TLS, CI/CD, monitoring, and rollback procedures.

---

## Prerequisites

### Host Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| OS | Ubuntu 22.04 LTS | Ubuntu 24.04 LTS |
| CPU | 4 cores | 8+ cores |
| RAM | 16 GB | 32 GB |
| Storage | 50 GB SSD | 200 GB SSD |
| GPU | — | NVIDIA (for Ollama GPU inference) |

### Software Requirements

- Docker Engine 24+
- Docker Compose plugin (`docker compose` not `docker-compose`)
- Git

### DNS Requirements

Point your domain's A record to the server's public IP **before** deploying. Caddy performs automatic TLS via Let's Encrypt using HTTP-01 challenges on port 80.

```
manixsystems.ai     A    <server-public-ip>
www.manixsystems.ai A    <server-public-ip>
```

---

## Host Provisioning

Run the included provisioning script on a fresh Ubuntu server as root. It installs Docker, creates a deploy user, and configures UFW firewall:

```bash
sudo bash scripts/provision-host.sh deploy
```

The firewall is configured to allow only SSH (22), HTTP (80), and HTTPS (443/tcp + 443/udp for HTTP/3). All other inbound ports are blocked.

After provisioning, switch to the deploy user:

```bash
su - deploy
```

---

## Tailscale VPN Setup (Recommended)

Tailscale provides secure access to admin/monitoring interfaces without exposing them to the public internet.

### Install Tailscale

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
# Authenticate via the URL shown, then note your Tailscale IP:
tailscale ip -4
# Example output: 100.64.0.5
```

### Configure UFW for Tailscale

```bash
# Allow all traffic on the Tailscale interface
sudo ufw allow in on tailscale0
```

### Set BIND_IP to Tailscale IP

In your `.env` file, set `BIND_IP` to your VPS's Tailscale IP:

```bash
BIND_IP=100.64.0.5   # Replace with your actual Tailscale IP
```

This binds all service ports (Grafana, n8n, Qdrant, Prometheus, etc.) to the Tailscale interface only. They become accessible to your team via VPN but invisible to the public internet.

Caddy binds separately to `0.0.0.0:80/443` for public HTTPS traffic — this is unaffected by `BIND_IP`.

### Access Pattern

| Service | URL | Access |
|---------|-----|--------|
| **Frontend** | `https://manixsystems.ai` | Public |
| **API** | `https://manixsystems.ai/v1/*` | Public |
| **Grafana** | `http://100.64.0.5:3009` | Tailscale only |
| **Prometheus** | `http://100.64.0.5:9090` | Tailscale only |
| **Jaeger** | `http://100.64.0.5:16686` | Tailscale only |
| **Qdrant Dashboard** | `http://100.64.0.5:6333/dashboard` | Tailscale only |
| **n8n** | `http://100.64.0.5:5679` | Tailscale only |
| **Open WebUI** | `http://100.64.0.5:3006` | Tailscale only |
| **Flowise** | `http://100.64.0.5:3008` | Tailscale only |
| **Langfuse** | `http://100.64.0.5:3007` | Tailscale only |
| **Alertmanager** | `http://100.64.0.5:9093` | Tailscale only |
| **Loki** | `http://100.64.0.5:3100` | Tailscale only |

### Verify Tailscale Access

From another machine on your tailnet:

```bash
# Should work (Tailscale)
curl http://100.64.0.5:3009    # Grafana
curl http://100.64.0.5:8081/health   # API direct

# Should NOT work (public IP, blocked by UFW)
curl http://<public-ip>:3009   # Connection refused
curl http://<public-ip>:8081   # Connection refused
```

---

## Clone and Configure

```bash
git clone <your-repo-url> ~/Desktop/Manic-AI
cd ~/Desktop/Manic-AI
cp .env.example .env
```

Edit `.env` with your secrets:

```bash
nano .env
```

---

## Environment Variables Reference

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `POSTGRES_USER` | PostgreSQL username | `postgres` |
| `POSTGRES_PASSWORD` | PostgreSQL password (strong, random) | `openssl rand -hex 32` |
| `POSTGRES_DB` | Database name | `postgres` |
| `API_SECRET_KEY` | Shared API key / signing key | `openssl rand -hex 32` |
| `QDRANT_API_KEY` | Qdrant authentication key | `openssl rand -hex 32` |
| `SEARXNG_SECRET_KEY` | SearXNG instance secret | `openssl rand -hex 32` |
| `GRAFANA_ADMIN_PASSWORD` | Grafana admin password | `openssl rand -hex 16` |
| `LANGFUSE_DB_PASSWORD` | Langfuse database password | `openssl rand -hex 32` |
| `BIND_IP` | IP to bind host-facing ports to | `0.0.0.0` (or `127.0.0.1` behind reverse proxy) |

### Core Service Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `PUBLIC_DOMAIN` | `manixsystems.ai` | Your domain — used by Caddy for TLS |
| `CHAT_MODEL` | `llama3.2:3b` | Default Ollama model for chat |
| `EMBEDDING_MODEL` | `bge-m3` | Embedding model (1024-dim output) |
| `VECTOR_DIMENSION` | `1024` | Must match the embedding model |
| `INFERENCE_BACKEND` | `ollama` | `ollama`, `vllm`, `openai`, or `anthropic` |
| `AUTH_MODE` | `single` | `single` (shared key) or `multi_user` (per-user keys) |

### Optional Cloud Inference

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | Enable OpenAI as inference backend |
| `ANTHROPIC_API_KEY` | Enable Anthropic (Claude) as inference backend |
| `VLLM_URL` | Enable vLLM as inference backend (e.g. `http://vllm:8000`) |
| `MODEL_FALLBACK_CHAIN` | Ordered fallback list e.g. `ollama,anthropic,openai` |

### Observability (optional)

| Variable | Description |
|----------|-------------|
| `LANGFUSE_PUBLIC_KEY` | Enable Langfuse LLM tracing |
| `LANGFUSE_SECRET_KEY` | Enable Langfuse LLM tracing |
| `SENTRY_DSN` | Enable Sentry error reporting |
| `OTEL_ENABLED` | `true` to enable OpenTelemetry (Jaeger) |

### RAG Tuning

| Variable | Default | Description |
|----------|---------|-------------|
| `RAG_TOP_K` | `5` | Number of chunks to retrieve |
| `RAG_THRESHOLD` | `0.7` | Minimum similarity score (0–1) |
| `RAG_KEYWORD_WEIGHT` | `0.3` | BM25 weight in hybrid scoring |

### Rate Limits

| Variable | Default | Description |
|----------|---------|-------------|
| `RATE_LIMIT_PER_MINUTE` | `60` | Chat/search rate limit |
| `RATE_LIMIT_INGEST_PER_MINUTE` | `10` | Ingest rate limit |
| `RATE_LIMIT_MUTATIONS_PER_MINUTE` | `30` | Delete/pull/etc. rate limit |
| `RATE_LIMIT_AGENT_PER_MINUTE` | `20` | Agent rate limit |

### CORS

| Variable | Default | Description |
|----------|---------|-------------|
| `CORS_ORIGINS` | — | Comma-separated allowed origins. Required in production. |

Example: `CORS_ORIGINS=https://manixsystems.ai,https://www.manixsystems.ai`

---

## First Deploy

### 1. Start all services

```bash
make up
# or
docker compose up -d
```

This starts all services including Caddy, the API, frontend, Ollama, Supabase, Redis, Qdrant, and all tools.

### 2. Verify services are healthy

```bash
make status
# or
docker compose ps
```

Wait for all services to reach the `healthy` state. Ollama may take up to 2 minutes on first start.

### 3. Initialize Qdrant collections

```bash
python scripts/setup_qdrant.py
```

This creates the required vector collections in Qdrant.

### 4. Pull the default LLM and embedding model

```bash
docker exec ollama ollama pull bge-m3
docker exec ollama ollama pull llama3.2:3b
```

The BGE-M3 model is required for embeddings. The chat model can be any Ollama-compatible model.

### 5. Verify setup

```bash
python scripts/verify_setup.py
```

### 6. Test the API

```bash
curl https://manixsystems.ai/health
```

Expected response: `{"success":true,"data":{"status":"healthy",...}}`

---

## SSL/TLS (Caddy Auto-HTTPS)

Caddy handles TLS automatically via Let's Encrypt. No configuration is required beyond:

1. Setting `PUBLIC_DOMAIN` in `.env` to your domain
2. Ensuring port 80 and 443 are reachable from the internet (for ACME HTTP-01 challenge)

Caddy stores certificates in the `caddy-data` Docker volume. Certificates auto-renew before expiry.

**HTTP/3** is enabled by default (port 443/udp). If your upstream load balancer or CDN strips QUIC, remove the UDP port mapping from `docker-compose.yml`.

**www redirect:** `www.manixsystems.ai` permanently redirects to `manixsystems.ai` (configured in `caddy/Caddyfile`).

---

## CI/CD Pipeline

The pipeline is defined in `.github/workflows/ci.yml` and triggers on:
- Pull requests to `Manic-AI-Prod`
- Pushes to `Manic-AI-Prod`
- Nightly at 03:00 UTC (security scan only)

### Pipeline Jobs

| Job | Description |
|-----|-------------|
| `api-lint` | Ruff linting of `api/` |
| `pre-commit` | All pre-commit hooks |
| `api-test` | pytest with coverage, against a live Postgres + Redis |
| `frontend-lint` | ESLint |
| `frontend-typecheck` | TypeScript strict type check |
| `frontend-test` | Jest with coverage |
| `build-api` | Docker build + Trivy image scan → push to GHCR |
| `build-frontend` | Next.js build + Docker build → push to GHCR |
| `docker-compose-check` | Validates docker-compose.yml syntax |
| `security-scan` | pip-audit, bandit, npm audit, Trivy FS scan, Gitleaks secret scan |
| `sql-check` | Validates `supabase/init.sql` syntax |
| `deploy` | SSH deploy to production (push to `Manic-AI-Prod` only) |

### Deploy Step

On a push to `Manic-AI-Prod` that passes all prior jobs:

```bash
cd ~/Desktop/Manic-AI
git pull origin Manic-AI-Prod
docker compose pull      # Pull latest images from GHCR
docker compose up -d --remove-orphans
docker compose ps
```

### Required GitHub Secrets

| Secret | Description |
|--------|-------------|
| `DEPLOY_HOST` | Production server hostname or IP |
| `DEPLOY_USER` | SSH username on production server |
| `DEPLOY_SSH_KEY` | Private SSH key for `DEPLOY_USER` |

---

## Monitoring

### Start the monitoring stack

```bash
make monitoring
# or
docker compose --profile monitoring up -d
```

This starts Prometheus, Grafana, Alertmanager, Loki, Promtail, cAdvisor, node-exporter, blackbox-exporter, and Jaeger.

### Access monitoring UIs

| Service | URL (internal bind IP) | Credentials |
|---------|----------------------|-------------|
| Grafana | `http://<BIND_IP>:3001` | admin / `GRAFANA_ADMIN_PASSWORD` |
| Prometheus | `http://<BIND_IP>:9090` | — |
| Alertmanager | `http://<BIND_IP>:9093` | — |
| Jaeger | `http://<BIND_IP>:16686` | — |
| Langfuse | `http://<BIND_IP>:3007` | Set at first login |

### Alert rules

Alert rules are defined in `monitoring/alerts/`. Alertmanager routes are in `monitoring/alertmanager.yml`.

---

## Database Backups

Run a pg_dump backup to the `backups/` directory:

```bash
make backup
# or
python scripts/backup_db.py
```

Backups are named `backup_<timestamp>.sql.gz`. Set up a cron job for automated backups:

```bash
0 2 * * * cd ~/Desktop/Manic-AI && python scripts/backup_db.py
```

---

## Updating

To update to the latest version:

```bash
cd ~/Desktop/Manic-AI
git pull origin Manic-AI-Prod
docker compose pull
docker compose up -d --remove-orphans
```

The API container has a `stop_grace_period: 35s` setting, so Docker will wait up to 35 seconds for in-flight requests to complete before force-stopping.

### Database Migrations

Alembic migrations run automatically via the API container's `entrypoint.sh`. To run manually:

```bash
docker exec manic-ai-api python -m alembic upgrade head
```

---

## Rollback

To roll back to a previous image:

```bash
# Find the previous image tag from GHCR
docker pull ghcr.io/mrvitality/manic-ai-api:<previous-sha>

# Update docker-compose to use the specific tag, then:
docker compose up -d api
```

Or roll back via git and redeploy:

```bash
git revert HEAD
git push origin Manic-AI-Prod
# CI/CD will automatically redeploy
```

---

## Development vs Production

The project ships three Compose files:

| File | Use |
|------|-----|
| `docker-compose.yml` | Base configuration (all environments) |
| `docker-compose.dev.yml` | Development overrides (hot reload, volume mounts) |
| `docker-compose.prod.yml` | Production overrides (resource limits, logging) |

For local development:

```bash
make dev
# Starts: docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

---

## Troubleshooting

### API container keeps restarting

Check logs:
```bash
docker compose logs api --tail=50
```

Common causes:
- `SUPABASE_DB_URL` is not set or the DB is not reachable
- `API_SECRET_KEY` is not set and `ALLOW_UNAUTHENTICATED` is not `true`
- Ollama has not finished starting (dependency healthcheck should handle this)

### Caddy fails to obtain TLS certificate

- Verify the DNS A record points to this server's public IP
- Verify ports 80 and 443 are open inbound (`ufw status`)
- Check Caddy logs: `docker compose logs caddy`

### Ollama out of memory

Reduce `OLLAMA_MAX_LOADED_MODELS` environment variable or switch to a smaller model:
```bash
CHAT_MODEL=llama3.2:1b docker compose up -d api
```

### Embeddings slow or timing out

Increase `EMBEDDING_CONCURRENCY` for throughput or reduce it if Ollama is overloaded:
```bash
EMBEDDING_CONCURRENCY=4 docker compose up -d api
```

### Qdrant collection not found

Run the setup script:
```bash
python scripts/setup_qdrant.py
```

### Check readiness

```bash
curl http://localhost:8081/health/ready
```

Returns `{"status":"ready"}` when DB and Redis are healthy.
