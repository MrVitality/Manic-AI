# Manic AI - Implementation Guide

**Version:** 2.0.0
**Last Updated:** February 2026
**Tailscale Network IP:** `100.111.244.124`

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Service Endpoints](#service-endpoints)
3. [Prerequisites](#prerequisites)
4. [Installation Steps](#installation-steps)
5. [Configuration](#configuration)
6. [Post-Installation](#post-installation)
7. [Troubleshooting](#troubleshooting)
8. [Maintenance](#maintenance)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              TAILSCALE NETWORK                               │
│                            (100.111.244.124)                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐  │
│  │  Manic AI        │      │  Manic AI        │      │  Ollama          │  │
│  │  Frontend        │─────▶│  API             │─────▶│  LLM Engine      │  │
│  │  :3000           │      │  :8081           │      │  :11434          │  │
│  └──────────────────┘      └────────┬─────────┘      └──────────────────┘  │
│                                     │                                        │
│                    ┌────────────────┼────────────────┐                      │
│                    │                │                │                      │
│                    ▼                ▼                ▼                      │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐          │
│  │  PostgreSQL      │  │  Qdrant          │  │  SearXNG         │          │
│  │  (Supabase)      │  │  Vector DB       │  │  Search Engine   │          │
│  │  :5433           │  │  :6333           │  │  :8889           │          │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘          │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                         SUPPORTING SERVICES                           │  │
│  ├──────────────┬──────────────┬──────────────┬──────────────┬──────────┤  │
│  │ Supabase     │ Open WebUI   │ n8n          │ Langfuse     │ Flowise  │  │
│  │ Studio :3005 │ :3006        │ :5679        │ :3007        │ :3008    │  │
│  └──────────────┴──────────────┴──────────────┴──────────────┴──────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Service Endpoints

All services are bound to Tailscale IP `100.111.244.124` for secure access.

### Core Services

| Service | URL | Purpose |
|---------|-----|---------|
| **Manic AI Frontend** | http://100.111.244.124:3000 | Main chat interface with RAG |
| **Manic AI API** | http://100.111.244.124:8081 | Unified backend API |
| **API Documentation** | http://100.111.244.124:8081/docs | Swagger/OpenAPI docs |
| **Ollama** | http://100.111.244.124:11434 | LLM inference engine |

### Database & Storage

| Service | URL/Connection | Purpose |
|---------|----------------|---------|
| **PostgreSQL** | 100.111.244.124:5433 | Primary database (Supabase) |
| **Qdrant** | http://100.111.244.124:6333 | Vector database |
| **Redis** | 100.111.244.124:6380 | Caching layer |

### Supporting Tools

| Service | URL | Purpose |
|---------|-----|---------|
| **Supabase Studio** | http://100.111.244.124:3005 | Database management UI |
| **Open WebUI** | http://100.111.244.124:3006 | Alternative Ollama chat UI |
| **Langfuse** | http://100.111.244.124:3007 | LLM observability |
| **Flowise** | http://100.111.244.124:3008 | Visual AI workflow builder |
| **n8n** | http://100.111.244.124:5679 | Workflow automation |
| **SearXNG** | http://100.111.244.124:8889 | Meta search engine |

---

## Prerequisites

### Hardware Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| RAM | 16 GB | 32 GB |
| CPU | 4 cores | 8+ cores |
| Disk | 40 GB SSD | 100 GB+ SSD |
| GPU | Not required | NVIDIA 6GB+ VRAM |

### Software Requirements

1. **Ubuntu 22.04 LTS** (or compatible Linux)
2. **Docker Engine** 24.0+
3. **Docker Compose** v2.20+
4. **Tailscale** (for secure network access)
5. **Node.js 18+** (for local development only)

---

## Installation Steps

### Step 1: Install Docker

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Verify installation
docker --version
docker compose version
```

### Step 2: Install Tailscale

```bash
# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# Start and authenticate
sudo tailscale up

# Get your Tailscale IP
tailscale ip -4
```

### Step 3: Clone Repository

```bash
cd ~
git clone <repository-url> Manic-AI
cd Manic-AI
```

### Step 4: Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit with your Tailscale IP
nano .env
```

**Critical settings to update:**

```bash
# Network - Set to your Tailscale IP
BIND_IP=100.111.244.124

# Update all URL references
SUPABASE_URL=http://100.111.244.124:8001
API_EXTERNAL_URL=http://100.111.244.124:8001
GOTRUE_SITE_URL=http://100.111.244.124:3006
SUPABASE_PUBLIC_URL=http://100.111.244.124:8001

# Database - Use matching passwords
POSTGRES_PASSWORD=<your-secure-password>
GOTRUE_DB_DATABASE_URL=postgresql://postgres:<your-secure-password>@supabase-db:5432/postgres?search_path=auth
```

**Important:** The `GOTRUE_DB_DATABASE_URL` password must NOT contain `/` or `=` characters.

### Step 5: Generate Frontend Lock File

```bash
cd frontend
npm install --legacy-peer-deps
cd ..
```

### Step 6: Build and Start Services

```bash
# Build and start all services
sudo docker compose up -d --build

# Monitor startup (wait for healthy status)
watch -n 2 'docker compose ps'
```

### Step 7: Pull AI Models

```bash
# Required models
sudo docker exec ollama ollama pull llama3.2:3b
sudo docker exec ollama ollama pull nomic-embed-text

# Optional models
sudo docker exec ollama ollama pull mistral:7b
sudo docker exec ollama ollama pull codellama:7b
```

### Step 8: Configure Frontend

1. Open http://100.111.244.124:3000
2. Click **Settings** (gear icon)
3. Set **API URL** to: `http://100.111.244.124:8081`
4. Click Refresh to connect

---

## Configuration

### Environment Variables Reference

#### Network
```bash
BIND_IP=100.111.244.124          # Tailscale IP for service binding
```

#### AI Models
```bash
CHAT_MODEL=llama3.2:3b           # Default chat model
EMBEDDING_MODEL=nomic-embed-text  # Embedding model for RAG
VECTOR_DIMENSION=768              # Vector dimensions (match embedding model)
```

#### RAG Settings
```bash
RAG_TOP_K=5                       # Number of documents to retrieve
RAG_THRESHOLD=0.7                 # Minimum similarity score
RAG_KEYWORD_WEIGHT=0.3            # Hybrid search keyword weight
```

#### Database
```bash
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<secure-password>
POSTGRES_DB=postgres
```

### Docker Compose Overrides

To customize resource limits, create `docker-compose.override.yml`:

```yaml
services:
  ollama:
    deploy:
      resources:
        limits:
          memory: 16G  # Increase for larger models
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

---

## Post-Installation

### Verify Services

```bash
# Check all containers are running
sudo docker compose ps

# Test API health
curl http://100.111.244.124:8081/health

# Expected response:
# {"status":"healthy","services":{"database":"connected","ollama":"healthy"}}
```

### Access Points

Connect from any device on your Tailscale network:

| Application | URL |
|-------------|-----|
| Manic AI Chat | http://100.111.244.124:3000 |
| API Docs | http://100.111.244.124:8081/docs |
| Database Admin | http://100.111.244.124:3005 |

### Keyboard Shortcuts (Frontend)

| Shortcut | Action |
|----------|--------|
| `Ctrl+N` | New chat |
| `Ctrl+D` | Documents view |
| `Ctrl+M` | Models view |
| `Ctrl+H` | Dashboard/Health view |
| `Escape` | Return to chat |

---

## Troubleshooting

### Common Issues

#### 1. Ollama Health Check Fails

**Symptom:** `dependency failed to start: container ollama is unhealthy`

**Solution:** The Ollama container doesn't have curl. Use `ollama list` for health check:

```yaml
# In docker-compose.yml
ollama:
  healthcheck:
    test: ["CMD", "ollama", "list"]
    interval: 30s
    timeout: 10s
    retries: 5
    start_period: 120s
```

#### 2. Supabase Auth Crashing

**Symptom:** `ai-supabase-auth` keeps restarting with SIGSEGV

**Cause:** Password in `GOTRUE_DB_DATABASE_URL` contains `/` or `=` characters

**Solution:** Use a simple alphanumeric password:
```bash
GOTRUE_DB_DATABASE_URL=postgresql://postgres:simplePassword123@supabase-db:5432/postgres?search_path=auth
```

#### 3. Frontend Can't Connect to API

**Symptom:** Settings shows "Disconnected"

**Solution:**
1. Verify API is running: `curl http://100.111.244.124:8081/health`
2. Clear browser localStorage
3. Re-enter API URL in Settings: `http://100.111.244.124:8081`

#### 4. Services Not Accessible from Browser

**Symptom:** Can't reach services from local machine

**Solution:** Ensure Tailscale is running on your local machine and you're logged into the same account:
```bash
# On local machine
tailscale status
ping 100.111.244.124
```

#### 5. Docker Build Fails for Frontend

**Symptom:** `npm install` fails with peer dependency errors

**Solution:** Use legacy peer deps flag:
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install --legacy-peer-deps
```

### Viewing Logs

```bash
# All services
sudo docker compose logs -f

# Specific service
sudo docker compose logs -f api
sudo docker compose logs -f ollama
sudo docker compose logs -f supabase-auth

# Last 50 lines
sudo docker compose logs --tail 50 <service-name>
```

### Restarting Services

```bash
# Restart single service
sudo docker compose restart api

# Recreate single service
sudo docker compose up -d --force-recreate api

# Restart everything
sudo docker compose down && sudo docker compose up -d
```

---

## Maintenance

### Backup Database

```bash
# Backup PostgreSQL
sudo docker exec ai-supabase-db pg_dump -U postgres postgres > backup_$(date +%Y%m%d).sql

# Backup with compression
sudo docker exec ai-supabase-db pg_dump -U postgres postgres | gzip > backup_$(date +%Y%m%d).sql.gz
```

### Update Services

```bash
# Pull latest images
sudo docker compose pull

# Rebuild and restart
sudo docker compose up -d --build
```

### Monitor Resources

```bash
# Container resource usage
docker stats

# Disk usage
docker system df

# Clean unused resources
docker system prune -a
```

### Pull New Models

```bash
# List available models
sudo docker exec ollama ollama list

# Pull new model
sudo docker exec ollama ollama pull <model-name>

# Remove model
sudo docker exec ollama ollama rm <model-name>
```

---

## Security Notes

1. **Tailscale-only access:** All services are bound to `100.111.244.124`, not accessible from public internet
2. **No exposed ports:** Services are only reachable via Tailscale VPN
3. **Database credentials:** Stored in `.env` file (not committed to git)
4. **JWT secrets:** Used for Supabase authentication

### Firewall (Optional Additional Security)

```bash
# Block all external access to Docker ports
sudo ufw default deny incoming
sudo ufw allow ssh
sudo ufw allow in on tailscale0
sudo ufw enable
```

---

## File Structure

```
~/Manic-AI/
├── docker-compose.yml      # Service definitions
├── .env                    # Environment configuration
├── .env.example            # Template for .env
├── IMPLEMENTATION.md       # This document
├── INSTALL.md              # Quick start guide
├── api/                    # Unified Python API
│   ├── main.py
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/               # Next.js frontend
│   ├── app/
│   ├── components/
│   ├── hooks/
│   ├── lib/
│   ├── types/
│   ├── Dockerfile
│   └── package.json
├── supabase/               # Database initialization
│   ├── init.sql
│   └── kong.yml
├── searxng/                # Search engine config
│   └── settings.yml
└── sql-parts/              # Reference SQL scripts
```

---

## Support

### Useful Commands Cheatsheet

```bash
# Start all services
sudo docker compose up -d

# Stop all services
sudo docker compose down

# View running containers
sudo docker compose ps

# View logs
sudo docker compose logs -f <service>

# Restart a service
sudo docker compose restart <service>

# Rebuild and restart
sudo docker compose up -d --build --force-recreate <service>

# Pull AI model
sudo docker exec ollama ollama pull <model>

# Check API health
curl http://100.111.244.124:8081/health

# Check Tailscale status
tailscale status
```

---

*Document generated for Manic AI v2.0.0 deployment on Tailscale network.*
