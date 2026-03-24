# Manic AI — Hostinger VPS Deployment Guide

**VPS IP:** `72.61.78.179`
**Tailscale IP:** `100.115.61.105`
**Domain:** `manixsystems.ai`
**Specs:** 4 CPU / 16 GB RAM / 200 GB SSD

---

## Step 0: DNS Configuration (Do This First)

Log into your Hostinger DNS panel and create these records:

```
Type    Name    Value              TTL
A       @       72.61.78.179       3600
A       www     72.61.78.179       3600
```

Verify propagation (run from your laptop):

```bash
nslookup manixsystems.ai
# Should return: 72.61.78.179
```

DNS can take 5-30 minutes to propagate. Start the VPS setup while you wait.

---

## Step 1: SSH Into Your VPS

```bash
ssh root@72.61.78.179
```

If you haven't set up SSH keys yet:
```bash
# From your Windows laptop (PowerShell):
ssh-keygen -t ed25519 -C "mark@manixsystems"
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh root@72.61.78.179 "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

---

## Step 2: Install Docker + System Setup

Run these commands on the VPS as root:

```bash
# Update system
apt-get update -qq && apt-get upgrade -y -qq

# Install Docker
curl -fsSL https://get.docker.com | sh
systemctl enable docker && systemctl start docker

# Verify
docker --version
docker compose version

# Install utilities
apt-get install -y -qq git curl wget htop ncdu jq

# Create deploy user
useradd -m -s /bin/bash -G docker deploy
echo "deploy ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers.d/deploy

# Add swap (recommended for 16GB)
fallocate -l 4G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

---

## Step 3: Install Tailscale

```bash
# Still as root on the VPS:
curl -fsSL https://tailscale.com/install.sh | sh
tailscale up

# It will print a URL — open it in your browser to authenticate
# After auth, verify:
tailscale ip -4
# Should show: 100.115.61.105
```

---

## Step 4: Configure Firewall

```bash
apt-get install -y -qq ufw

# Allow Tailscale interface (all traffic from VPN)
ufw allow in on tailscale0

# Public ports (Caddy only)
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 443/udp    # HTTP/3

# Enable firewall
ufw --force enable
ufw status

# Expected output:
# 22/tcp    ALLOW  Anywhere
# 80/tcp    ALLOW  Anywhere
# 443/tcp   ALLOW  Anywhere
# 443/udp   ALLOW  Anywhere
# Anywhere  ALLOW  IN on tailscale0
```

> **Important:** If Hostinger has its own firewall panel (VPS → Firewall), also allow ports 80 and 443 there.

---

## Step 5: Get the Code on the VPS

### Option A: Clone from GitHub (Recommended)

```bash
# Switch to deploy user
su - deploy

# Clone the repo
git clone https://github.com/MrVitality/Manic-AI.git ~/Manic-AI
cd ~/Manic-AI
```

### Option B: Transfer from your laptop via SCP

From your Windows laptop (PowerShell):

```powershell
# Transfer the entire project (excluding node_modules, .git, etc.)
# First, create a tar archive locally:
cd C:\Users\mark_\Desktop
tar --exclude='node_modules' --exclude='.next' --exclude='__pycache__' --exclude='.git' --exclude='*.pyc' --exclude='venv' -czf Manic-AI.tar.gz Manic-AI

# Upload to VPS
scp Manic-AI.tar.gz deploy@72.61.78.179:~/

# SSH in and extract
ssh deploy@72.61.78.179
cd ~
tar xzf Manic-AI.tar.gz
cd Manic-AI

# Initialize git (needed for CI/CD later)
git init
git remote add origin https://github.com/MrVitality/Manic-AI.git
git fetch origin
git checkout -b Manic-AI-Prod origin/Manic-AI-Prod
```

### Option B2: Transfer via rsync (faster for updates)

From your Windows laptop (Git Bash or WSL):

```bash
rsync -avz --progress \
  --exclude='node_modules' \
  --exclude='.next' \
  --exclude='__pycache__' \
  --exclude='.git' \
  --exclude='venv' \
  --exclude='*.pyc' \
  /c/Users/mark_/Desktop/Manic-AI/ \
  deploy@72.61.78.179:~/Manic-AI/
```

---

## Step 6: Generate Secrets

```bash
cd ~/Manic-AI

# Copy the example env file
cp .env.example .env

# Generate Supabase JWT keys
bash scripts/gen-supabase-keys.sh
# Copy the JWT_SECRET, ANON_KEY, and SERVICE_ROLE_KEY from the output

# Generate a secure API secret key
python3 -c "import secrets; print('API_SECRET_KEY=' + secrets.token_urlsafe(32))"

# Generate other passwords
python3 -c "import secrets; print('POSTGRES_PASSWORD=' + secrets.token_urlsafe(24))"
python3 -c "import secrets; print('REDIS_PASSWORD=' + secrets.token_urlsafe(24))"
python3 -c "import secrets; print('QDRANT_API_KEY=' + secrets.token_urlsafe(24))"
python3 -c "import secrets; print('GRAFANA_ADMIN_PASSWORD=' + secrets.token_urlsafe(16))"
python3 -c "import secrets; print('SEARXNG_SECRET_KEY=' + secrets.token_urlsafe(24))"
python3 -c "import secrets; print('LANGFUSE_DB_PASSWORD=' + secrets.token_urlsafe(24))"
```

---

## Step 7: Edit .env

```bash
nano .env
```

Fill in these values (paste the generated secrets from Step 6):

```bash
# === CORE ===
BIND_IP=100.115.61.105
PUBLIC_DOMAIN=manixsystems.ai

# === DATABASE ===
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<paste-generated>
POSTGRES_DB=postgres
ANON_KEY=<paste-from-gen-supabase-keys>
SERVICE_ROLE_KEY=<paste-from-gen-supabase-keys>

# === REDIS ===
REDIS_PASSWORD=<paste-generated>

# === QDRANT ===
QDRANT_API_KEY=<paste-generated>

# === AUTH ===
API_SECRET_KEY=<paste-generated>
# AUTH_MODE=single   (change to multi_user when ready)

# === SEARXNG ===
SEARXNG_SECRET_KEY=<paste-generated>

# === LANGFUSE ===
LANGFUSE_DB_PASSWORD=<paste-generated>

# === GRAFANA ===
GRAFANA_ADMIN_PASSWORD=<paste-generated>

# === AI INFERENCE ===
# ANTHROPIC_API_KEY=sk-ant-...   (if using Anthropic)
# OPENAI_API_KEY=sk-...          (if using OpenAI)

# === CORS ===
CORS_ORIGINS=https://manixsystems.ai,http://localhost:3000
```

Save with `Ctrl+O`, exit with `Ctrl+X`.

---

## Step 8: Launch Everything

```bash
cd ~/Manic-AI

# Start all services (first boot takes 5-10 minutes to pull images)
docker compose up -d

# Watch the startup logs
docker compose logs -f caddy api frontend supabase-db redis qdrant ollama

# Press Ctrl+C when you see services reporting healthy
```

Check all services are running:

```bash
docker compose ps
```

Expected: all containers show `Up` or `healthy`.

---

## Step 9: Pull AI Models

```bash
# Pull the embedding model (REQUIRED for RAG)
docker exec ai-ollama ollama pull bge-m3

# Pull a chat model (choose based on your preference)
docker exec ai-ollama ollama pull llama3.1:8b    # Best quality for 16GB
# OR
docker exec ai-ollama ollama pull llama3.2:3b    # Faster, lighter

# Verify models are loaded
docker exec ai-ollama ollama list
```

---

## Step 10: Verify Deployment

### Public Access (from your laptop)

```bash
# Health check
curl https://manixsystems.ai/health
# Expected: {"status":"healthy"}

# Readiness check (DB + Redis)
curl https://manixsystems.ai/health/ready
# Expected: {"status":"ready"}

# Open in browser
# https://manixsystems.ai
# You should see the Manic AI setup wizard on first visit
```

### Tailscale Access (from your laptop on the VPN)

```bash
# Grafana (monitoring dashboards)
# http://100.115.61.105:3009
# Login: admin / <your GRAFANA_ADMIN_PASSWORD>

# Qdrant Dashboard
# http://100.115.61.105:6333/dashboard

# Prometheus
# http://100.115.61.105:9090

# n8n (workflow automation)
# http://100.115.61.105:5679

# Langfuse (LLM tracing)
# http://100.115.61.105:3007

# Open WebUI (alternative chat interface)
# http://100.115.61.105:3006
```

### From the VPS itself

```bash
# Check all services
docker compose ps

# Check API directly
curl http://localhost:8081/health

# Check container resource usage
docker stats --no-stream

# Check disk usage
df -h
docker system df
```

---

## Step 11: Set Up CI/CD (GitHub Actions Auto-Deploy)

### Generate SSH key for the deploy user

```bash
# On the VPS as deploy user:
ssh-keygen -t ed25519 -f ~/.ssh/github_deploy -N ""
cat ~/.ssh/github_deploy.pub >> ~/.ssh/authorized_keys
cat ~/.ssh/github_deploy
# Copy the PRIVATE key output
```

### Add GitHub Secrets

Go to: `https://github.com/MrVitality/Manic-AI/settings/secrets/actions`

Add these secrets:

| Secret Name | Value |
|-------------|-------|
| `DEPLOY_HOST` | `72.61.78.179` |
| `DEPLOY_USER` | `deploy` |
| `DEPLOY_SSH_KEY` | The private key from above (entire content including BEGIN/END lines) |

Now every push to `Manic-AI-Prod` will automatically deploy to your VPS.

---

## Step 12: Configure Alertmanager

Edit the alertmanager config to receive alerts:

```bash
nano ~/Manic-AI/monitoring/alertmanager.yml
```

### For Slack alerts:

```yaml
receivers:
  - name: default
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
        channel: '#manic-ai-alerts'
        send_resolved: true
        title: '{{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'
```

### For email alerts:

```yaml
receivers:
  - name: default
    email_configs:
      - to: 'your-email@manixsystems.ai'
        from: 'alerts@manixsystems.ai'
        smarthost: 'smtp.gmail.com:587'
        auth_username: 'your-gmail@gmail.com'
        auth_password: 'your-app-password'
        send_resolved: true
```

After editing, restart alertmanager:

```bash
docker compose restart alertmanager
```

---

## Step 13: Verify Backups

Backups run automatically at 3 AM daily. To test manually:

```bash
# Run a manual backup
docker exec ai-backup python /scripts/backup_db.py

# Check backup files
ls -la ~/Manic-AI/backups/
```

---

## Quick Reference Card

### URLs

| Service | URL | Access |
|---------|-----|--------|
| App | https://manixsystems.ai | Public |
| API | https://manixsystems.ai/v1/ | Public |
| Grafana | http://100.115.61.105:3009 | Tailscale |
| Prometheus | http://100.115.61.105:9090 | Tailscale |
| Jaeger | http://100.115.61.105:16686 | Tailscale |
| Qdrant | http://100.115.61.105:6333/dashboard | Tailscale |
| n8n | http://100.115.61.105:5679 | Tailscale |
| Langfuse | http://100.115.61.105:3007 | Tailscale |
| Open WebUI | http://100.115.61.105:3006 | Tailscale |
| Flowise | http://100.115.61.105:3008 | Tailscale |
| Alertmanager | http://100.115.61.105:9093 | Tailscale |

### Common Commands

```bash
# View all services
docker compose ps

# View logs (all)
docker compose logs -f --tail=100

# View logs (specific service)
docker compose logs -f api

# Restart a service
docker compose restart api

# Update (from GitHub)
cd ~/Manic-AI && git pull origin Manic-AI-Prod && docker compose up -d

# Update (production overlay)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Check resource usage
docker stats --no-stream

# Manual backup
docker exec ai-backup python /scripts/backup_db.py

# Pull a new model
docker exec ai-ollama ollama pull <model-name>

# Stop everything
docker compose down

# Stop and remove all data (DESTRUCTIVE)
docker compose down -v
```

### Troubleshooting

| Problem | Fix |
|---------|-----|
| Caddy shows "connection refused" | DNS not propagated yet. Check: `dig manixsystems.ai` |
| API returns 500 | Check logs: `docker compose logs api --tail=50` |
| "API unreachable" in browser | Verify CORS_ORIGINS includes `https://manixsystems.ai` |
| Ollama OOM killed | Reduce model size: use `llama3.2:3b` instead of `8b` |
| Qdrant unhealthy | Check memory: `docker stats ai-qdrant`. May need more RAM. |
| Redis connection refused | Verify REDIS_PASSWORD matches in .env |
| Grafana won't load | Access via Tailscale IP, not public IP |
| SSL certificate error | Ensure ports 80+443 are open in both UFW and Hostinger firewall |
| "Setup wizard" keeps showing | Clear localStorage in browser, or check API key in settings |
| Database migration failed | `docker exec ai-api python -m alembic upgrade head` |
