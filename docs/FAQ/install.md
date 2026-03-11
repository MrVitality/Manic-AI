# Manic AI - Installation Guide

Complete step-by-step guide to deploy the Manic AI stack on your machine.

---

## Prerequisites

### Hardware Requirements
| Resource | Minimum | Recommended |
|----------|---------|-------------|
| **RAM** | 16 GB | 32 GB |
| **CPU** | 4 cores | 8+ cores |
| **Disk** | 40 GB free | 100 GB+ SSD |
| **GPU** | Not required | NVIDIA GPU w/ 6GB+ VRAM (for faster inference) |

> The stack runs 18 containers. Ollama alone needs ~4-8 GB for a 3B model in memory. Supabase + supporting services add another 4-6 GB.

### Software Requirements
1. **Docker Desktop** (v4.25+) with Docker Compose v2
   - Windows: [Download Docker Desktop](https://www.docker.com/products/docker-desktop/)
   - Enable WSL 2 backend (Settings > General > "Use the WSL 2 based engine")
   - Allocate at least **12 GB RAM** to Docker (Settings > Resources > Memory)
2. **Git** (to clone or manage the repo)
3. **A web browser** (Chrome/Edge/Firefox)

### Network Requirements
- The stack binds all services to a single IP address (`BIND_IP` in `.env`)
- Your current `.env` uses Tailscale IP `100.81.119.103` — change this to your machine's IP
- If running locally only, use `127.0.0.1` or `0.0.0.0`

---

## Step 1: Configure Environment Variables

The `.env` file already exists with your credentials. Review and update it:

```bash
# Open the .env file in your editor
notepad .env          # Windows
# OR
code .env             # VS Code
```

### Critical settings to verify:

| Variable | Current Value | What to check |
|----------|--------------|---------------|
| `BIND_IP` | `100.81.119.103` | Change to your machine's IP, `127.0.0.1` for local-only, or `0.0.0.0` to listen on all interfaces |
| `POSTGRES_PASSWORD` | (set) | Keep as-is or change to a new strong password |
| `JWT_SECRET` | (set) | Keep as-is (must match ANON_KEY/SERVICE_ROLE_KEY JWTs) |
| `GOTRUE_SITE_URL` | `http://100.81.119.103:3006` | Update IP to match your BIND_IP |
| `SUPABASE_URL` | `http://100.81.119.103:8001` | Update IP to match your BIND_IP |
| `API_EXTERNAL_URL` | `http://100.81.119.103:8001` | Update IP to match your BIND_IP |
| `SUPABASE_PUBLIC_URL` | `http://100.81.119.103:8001` | Update IP to match your BIND_IP |

> **If you change `BIND_IP`**: Do a find-and-replace in `.env` — replace `100.81.119.103` with your new IP in all URL fields.

---

## Step 2: Generate Frontend Lock File

The frontend Docker build needs a `package-lock.json`. Generate it:

```bash
cd frontend
npm install
cd ..
```

> This creates `frontend/node_modules/` (used for local dev only) and `frontend/package-lock.json` (needed for the Docker build). The Docker build will do its own `npm install` inside the container.

---

## Step 3: Build and Launch

### Option A: Full stack (all 18 services)

```bashls

docker compose up -d --build
```

This will:
1. Pull 15 pre-built images (~8-10 GB total download on first run)
2. Build 2 custom images (`api` and `frontend`)
3. Start all 18 containers on the `ai-network` bridge
4. Initialize PostgreSQL with the RAG schema (pgvector, hybrid search, etc.)

**Expect first launch to take 5-15 minutes** depending on internet speed and machine.

### Option B: Staged launch (recommended for first time)

Launch in stages to catch issues early:

```bash
# Stage 1: Core infrastructure (database + cache)
docker compose up -d supabase-db redis
# Wait 30 seconds for DB to initialize
sleep 30

# Stage 2: Supabase services
docker compose up -d supabase-auth supabase-rest supabase-meta supabase-storage supabase-kong supabase-studio

# Stage 3: AI engine
docker compose up -d ollama qdrant

# Stage 4: Manic AI backend + frontend
docker compose up -d --build api frontend

# Stage 5: Supporting tools
docker compose up -d n8n open-webui searxng langfuse-db langfuse flowise
```

---

## Step 4: Pull AI Models

Ollama starts with **no models**. You need to pull them:

```bash
# Pull the chat model (required)
docker exec ollama ollama pull llama3.2:3b

# Pull the embedding model (required for RAG)
docker exec ollama ollama pull nomic-embed-text
```

| Model | Size | Purpose |
|-------|------|---------|
| `llama3.2:3b` | ~2 GB | Chat/conversation (default) |
| `nomic-embed-text` | ~274 MB | Text embeddings for RAG |

> **Optional**: Pull larger models for better quality:
> ```bash
> docker exec ollama ollama pull llama3.1:8b      # 4.7 GB - much better quality
> docker exec ollama ollama pull mistral:7b        # 4.1 GB - good alternative
> docker exec ollama ollama pull codellama:7b      # 3.8 GB - code generation
> ```
> You can also pull models from the Manic AI frontend (Models tab).

---

## Step 5: Verify Everything is Running

### Check container status:

```bash
docker compose ps
```

All 18 services should show `Up` or `Up (healthy)`:

| Container | Port | Status to expect |
|-----------|------|------------------|
| `ollama` | 11434 | `Up (healthy)` |
| `manic-ai-api` | 8081 | `Up (healthy)` |
| `manic-ai-frontend` | 3000 | `Up` |
| `ai-supabase-db` | 5433 | `Up (healthy)` |
| `ai-supabase-kong` | 8001 | `Up` |
| `ai-supabase-studio` | 3005 | `Up` |
| `ai-supabase-auth` | — | `Up` |
| `ai-supabase-rest` | — | `Up` |
| `ai-supabase-meta` | — | `Up` |
| `ai-supabase-storage` | — | `Up` |
| `qdrant` | 6333 | `Up` |
| `ai-redis` | 6380 | `Up (healthy)` |
| `ai-n8n` | 5679 | `Up` |
| `ai-open-webui` | 3006 | `Up` |
| `ai-searxng` | 8889 | `Up` |
| `ai-langfuse-db` | — | `Up` |
| `ai-langfuse` | 3007 | `Up` |
| `ai-flowise` | 3008 | `Up` |

### Check API health:

```bash
curl http://<YOUR_BIND_IP>:8081/health
```

Expected response:
```json
{
  "status": "healthy",
  "services": {
    "database": "connected",
    "ollama": "healthy"
  },
  "config": {
    "chat_model": "llama3.2:3b",
    "embedding_model": "nomic-embed-text"
  }
}
```

### Check full service status:

```bash
curl http://<YOUR_BIND_IP>:8081/services/status
```

---

## Step 6: Access the UIs

Open these URLs in your browser (replace `<IP>` with your `BIND_IP`):

| Service | URL | Description |
|---------|-----|-------------|
| **Manic AI** | `http://<IP>:3000` | Main frontend (chat, RAG, models, dashboard) |
| **Supabase Studio** | `http://<IP>:3005` | Database management UI |
| **Open WebUI** | `http://<IP>:3006` | Alternative Ollama chat UI |
| **Langfuse** | `http://<IP>:3007` | LLM observability dashboard |
| **Flowise** | `http://<IP>:3008` | Visual LLM workflow builder |
| **n8n** | `http://<IP>:5679` | Workflow automation |
| **SearXNG** | `http://<IP>:8889` | Meta search engine |
| **Manic AI API** | `http://<IP>:8081/docs` | FastAPI Swagger docs |

---

## Troubleshooting

### Container won't start

```bash
# Check logs for a specific service
docker compose logs <service-name> --tail 50

# Examples:
docker compose logs api --tail 50
docker compose logs supabase-db --tail 50
docker compose logs frontend --tail 50
```

### "Port already in use" error

Another process is using that port. Find and stop it:

```bash
# Windows
netstat -ano | findstr :<PORT>
taskkill /PID <PID> /F

# Or change the port in docker-compose.yml
```

### Database connection failed in API logs

- Verify `supabase-db` is healthy: `docker compose ps supabase-db`
- The API waits for the DB health check, but if timing is off: `docker compose restart api`
- Check DB logs: `docker compose logs supabase-db --tail 30`

### Frontend shows "API connection error"

- Verify the API is running: `curl http://<BIND_IP>:8081/health`
- Check that `BIND_IP` is accessible from your browser's machine
- If using Tailscale: ensure both machines are on the same tailnet

### Ollama out of memory

- Reduce Docker memory limit for Ollama in `docker-compose.yml` (currently 8G)
- Use a smaller model: `llama3.2:1b` instead of `llama3.2:3b`
- Close other memory-heavy containers you don't need

### Frontend build fails in Docker

If the frontend container fails to build:

```bash
# Check the build output
docker compose build frontend 2>&1 | tail -30

# Common fix: regenerate lock file
cd frontend && rm -rf node_modules package-lock.json && npm install && cd ..
docker compose build frontend
```

### "Cannot connect to Docker daemon"

- Windows: Make sure Docker Desktop is running
- WSL: `sudo service docker start`

---

## Common Operations

### Stop everything
```bash
docker compose down
```

### Stop and remove all data (fresh start)
```bash
docker compose down -v
```
> **Warning**: `-v` deletes all Docker volumes (database data, model cache, etc.)

### Update images
```bash
docker compose pull
docker compose up -d --build
```

### View real-time logs
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f api
```

### Restart a single service
```bash
docker compose restart api
docker compose restart frontend
```

### Connect to PostgreSQL directly
```bash
docker exec -it ai-supabase-db psql -U postgres -d postgres
```

Then run SQL:
```sql
-- Check RAG tables
SELECT tablename FROM pg_tables WHERE schemaname = 'rag';

-- Count documents
SELECT count(*) FROM rag.documents;

-- Check extensions
SELECT extname FROM pg_extension;
```

---

## Port Reference

| Port | Service | Protocol |
|------|---------|----------|
| 3000 | Manic AI Frontend | HTTP |
| 3005 | Supabase Studio | HTTP |
| 3006 | Open WebUI | HTTP |
| 3007 | Langfuse | HTTP |
| 3008 | Flowise | HTTP |
| 5433 | PostgreSQL | TCP |
| 5679 | n8n | HTTP |
| 6333 | Qdrant HTTP | HTTP |
| 6334 | Qdrant gRPC | gRPC |
| 6380 | Redis | TCP |
| 8001 | Supabase Kong (API Gateway) | HTTP |
| 8081 | Manic AI API | HTTP |
| 8444 | Supabase Kong (HTTPS) | HTTPS |
| 8889 | SearXNG | HTTP |
| 11434 | Ollama | HTTP |

---

## Architecture Overview

```
Browser (:3000)
    |
    v
[Manic AI Frontend]  (Next.js)
    |
    v
[Manic AI API :8081]  (FastAPI Python)
    |
    +---> [Ollama :11434]         -- LLM inference (chat + embeddings)
    +---> [PostgreSQL :5433]      -- RAG storage (pgvector), Supabase data
    +---> [Qdrant :6333]          -- Vector DB (optional secondary)
    +---> [Redis :6380]           -- Caching layer
    +---> [SearXNG :8889]         -- Web search

[Supabase Stack]
    Kong (:8001) -> Auth, REST, Meta, Storage

[Tooling]
    n8n (:5679)      -- Workflow automation
    Open WebUI (:3006) -- Alternative chat UI
    Langfuse (:3007) -- LLM observability
    Flowise (:3008)  -- Visual AI workflows
```

---

## GPU Acceleration (Optional)

If you have an NVIDIA GPU and want faster inference:

### 1. Install NVIDIA Container Toolkit

```bash
# WSL2 / Linux
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

### 2. Add GPU to Ollama in docker-compose.yml

Add under the `ollama` service:
```yaml
  ollama:
    ...
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

### 3. Restart Ollama

```bash
docker compose up -d ollama
```

Verify GPU is detected:
```bash
docker exec ollama ollama run llama3.2:3b "Hi" 2>&1 | head -5
# Should be noticeably faster than CPU
```

---

## Local Development (without Docker)

If you want to run the frontend or API outside Docker for development:

### Frontend
```bash
cd frontend
npm install
npm run dev
# Runs on http://localhost:3000
# Edit NEXT_PUBLIC_API_URL in next.config.js if API is on a different host
```

### API
```bash
cd api
pip install -r requirements.txt
# Set environment variables or create a local .env
export OLLAMA_URL=http://localhost:11434
export SUPABASE_DB_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5433/postgres
python main.py
# Runs on http://localhost:8081
```

> When developing locally, you still need the infrastructure services (Ollama, PostgreSQL, Redis, etc.) running via Docker. Just comment out the `api` and `frontend` services in `docker-compose.yml`.
