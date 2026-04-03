#!/bin/bash
# ============================================================
# Manic AI — First-Time VPS Deploy Script
# Run as: ssh manic@72.61.78.179 'bash -s' < scripts/vps-deploy.sh
# OR: copy to VPS and run: bash ~/vps-deploy.sh
# ============================================================
set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; }

REPO_URL="https://github.com/MrVitality/Manic-AI.git"
INSTALL_DIR="$HOME/Manic-AI"
BRANCH="Manic-AI-Prod"

echo ""
echo "============================================"
echo "  Manic AI — VPS First-Time Deploy"
echo "============================================"
echo ""

# ----------------------------------------------------------
# Phase 1: Check prerequisites
# ----------------------------------------------------------
echo "--- Phase 1: Checking prerequisites ---"

if ! command -v docker &> /dev/null; then
    err "Docker not found. Installing..."
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker "$USER"
    warn "Docker installed. You may need to log out and back in for group changes."
    warn "Then re-run this script."
    exit 1
else
    log "Docker: $(docker --version)"
fi

if ! docker compose version &> /dev/null; then
    err "Docker Compose plugin not found. Installing..."
    sudo apt-get install -y docker-compose-plugin
fi
log "Docker Compose: $(docker compose version --short)"

if ! groups | grep -q docker; then
    warn "User '$USER' is not in docker group. Adding..."
    sudo usermod -aG docker "$USER"
    warn "Added to docker group. Log out and back in, then re-run."
    exit 1
fi

if ! command -v git &> /dev/null; then
    warn "Git not found. Installing..."
    sudo apt-get update -qq && sudo apt-get install -y -qq git curl wget jq htop ncdu
fi
log "Git: $(git --version)"

# ----------------------------------------------------------
# Phase 2: System setup (swap + firewall)
# ----------------------------------------------------------
echo ""
echo "--- Phase 2: System setup ---"

# Add swap if none exists
if [ "$(swapon --show | wc -l)" -eq 0 ]; then
    warn "No swap detected. Creating 4GB swap..."
    sudo fallocate -l 4G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab > /dev/null
    log "4GB swap created and enabled"
else
    log "Swap already configured: $(free -h | grep Swap | awk '{print $2}')"
fi

# Firewall
if command -v ufw &> /dev/null; then
    sudo ufw allow ssh 2>/dev/null || true
    sudo ufw allow 80/tcp 2>/dev/null || true
    sudo ufw allow 443/tcp 2>/dev/null || true
    sudo ufw allow 443/udp 2>/dev/null || true
    if command -v tailscale &> /dev/null; then
        sudo ufw allow in on tailscale0 2>/dev/null || true
    fi
    sudo ufw --force enable 2>/dev/null || true
    log "Firewall configured (SSH + HTTP/HTTPS)"
else
    warn "UFW not installed. Install with: sudo apt install ufw"
fi

# ----------------------------------------------------------
# Phase 3: Clone or update repo
# ----------------------------------------------------------
echo ""
echo "--- Phase 3: Repository ---"

if [ -d "$INSTALL_DIR/.git" ]; then
    log "Repo exists at $INSTALL_DIR — pulling latest..."
    cd "$INSTALL_DIR"
    git fetch origin
    git checkout "$BRANCH"
    git pull origin "$BRANCH"
else
    log "Cloning repo to $INSTALL_DIR..."
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
    git checkout "$BRANCH"
fi
log "On branch: $(git branch --show-current) @ $(git log -1 --format='%h %s')"

# ----------------------------------------------------------
# Phase 4: Check .env
# ----------------------------------------------------------
echo ""
echo "--- Phase 4: Environment check ---"

# Move .env from home dir if uploaded there via scp
if [ -f "$HOME/.env" ] && [ ! -f "$INSTALL_DIR/.env" ]; then
    mv "$HOME/.env" "$INSTALL_DIR/.env"
    log "Moved .env from ~/ to $INSTALL_DIR/"
fi

if [ -f "$INSTALL_DIR/.env" ]; then
    log ".env file found ($(wc -l < "$INSTALL_DIR/.env") lines)"

    # Verify critical vars are set (not empty)
    MISSING=""
    for var in POSTGRES_PASSWORD QDRANT_API_KEY API_SECRET_KEY SEARXNG_SECRET_KEY GRAFANA_ADMIN_PASSWORD LANGFUSE_DB_PASSWORD; do
        val=$(grep "^${var}=" "$INSTALL_DIR/.env" | cut -d'=' -f2- | tr -d ' ')
        if [ -z "$val" ] || [[ "$val" == *"PASTE"* ]]; then
            MISSING="$MISSING $var"
        fi
    done

    if [ -n "$MISSING" ]; then
        err "These vars are missing or still have placeholders:$MISSING"
        err "Edit .env and re-run this script."
        exit 1
    fi
    log "All critical environment variables are set"
else
    err ".env file not found!"
    echo ""
    echo "Upload it from your local machine with:"
    echo "  scp C:/Users/mark_/desktop/Manic-AI/.env manic@72.61.78.179:~/Manic-AI/.env"
    echo ""
    echo "Then re-run this script."
    exit 1
fi

# ----------------------------------------------------------
# Phase 5: Create .htpasswd for Supabase Studio
# ----------------------------------------------------------
echo ""
echo "--- Phase 5: Supabase Studio auth ---"

if [ ! -f "$INSTALL_DIR/supabase/.htpasswd" ]; then
    if command -v htpasswd &> /dev/null; then
        STUDIO_PASS=$(openssl rand -hex 8)
        htpasswd -cb "$INSTALL_DIR/supabase/.htpasswd" admin "$STUDIO_PASS"
        log "Created .htpasswd (user: admin, pass: $STUDIO_PASS)"
        warn "SAVE THIS PASSWORD — you need it to access Supabase Studio"
    else
        sudo apt-get install -y -qq apache2-utils
        STUDIO_PASS=$(openssl rand -hex 8)
        htpasswd -cb "$INSTALL_DIR/supabase/.htpasswd" admin "$STUDIO_PASS"
        log "Created .htpasswd (user: admin, pass: $STUDIO_PASS)"
        warn "SAVE THIS PASSWORD — you need it to access Supabase Studio"
    fi
else
    log ".htpasswd already exists"
fi

# ----------------------------------------------------------
# Phase 6: Pull images & start services
# ----------------------------------------------------------
echo ""
echo "--- Phase 6: Docker services ---"

cd "$INSTALL_DIR"

log "Pulling Docker images (this takes 5-15 minutes on first run)..."
docker compose pull 2>&1 | tail -5

log "Starting all services with production overrides..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d 2>&1 | tail -20

echo ""
log "Waiting 30 seconds for services to initialize..."
sleep 30

echo ""
echo "--- Container Status ---"
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || docker compose ps

# ----------------------------------------------------------
# Phase 7: Pull AI models
# ----------------------------------------------------------
echo ""
echo "--- Phase 7: AI models ---"

if docker ps --format '{{.Names}}' | grep -q 'ollama'; then
    log "Pulling embedding model (bge-m3 ~1.5GB)..."
    docker exec ollama ollama pull bge-m3 2>&1 | tail -3

    log "Pulling chat model (llama3.2:3b ~2GB)..."
    docker exec ollama ollama pull llama3.2:3b 2>&1 | tail -3

    echo ""
    log "Installed models:"
    docker exec ollama ollama list
else
    warn "Ollama container not running yet. Pull models manually later:"
    echo "  docker exec ollama ollama pull bge-m3"
    echo "  docker exec ollama ollama pull llama3.2:3b"
fi

# ----------------------------------------------------------
# Phase 8: Health checks
# ----------------------------------------------------------
echo ""
echo "--- Phase 8: Health checks ---"

sleep 10

check_health() {
    local name=$1
    local url=$2
    if curl -sf --max-time 5 "$url" > /dev/null 2>&1; then
        log "$name: healthy"
    else
        warn "$name: not ready yet (may still be starting)"
    fi
}

check_health "API"       "http://localhost:8081/health"
check_health "Frontend"  "http://localhost:3000"

# ----------------------------------------------------------
# Phase 9: SSH key for CI/CD
# ----------------------------------------------------------
echo ""
echo "--- Phase 9: CI/CD setup ---"

if [ ! -f "$HOME/.ssh/github_deploy" ]; then
    ssh-keygen -t ed25519 -f "$HOME/.ssh/github_deploy" -N "" -q
    cat "$HOME/.ssh/github_deploy.pub" >> "$HOME/.ssh/authorized_keys"
    chmod 600 "$HOME/.ssh/authorized_keys"
    log "Generated CI/CD deploy key"
    echo ""
    echo "============================================"
    echo "  ADD THIS PRIVATE KEY TO GITHUB SECRETS"
    echo "  Settings > Secrets > Actions"
    echo "  Secret name: DEPLOY_SSH_KEY"
    echo "============================================"
    echo ""
    cat "$HOME/.ssh/github_deploy"
    echo ""
    echo "============================================"
    echo "  Also add these secrets:"
    echo "  DEPLOY_HOST = 72.61.78.179"
    echo "  DEPLOY_USER = manic"
    echo "============================================"
else
    log "Deploy key already exists at ~/.ssh/github_deploy"
fi

# ----------------------------------------------------------
# Done
# ----------------------------------------------------------
echo ""
echo "============================================"
echo "  Deployment complete!"
echo "============================================"
echo ""
echo "Public access:"
echo "  https://manixsystems.cloud"
echo "  https://manixsystems.cloud/health"
echo ""
echo "Admin tools (via Tailscale VPN):"
echo "  Grafana:      http://100.115.61.105:3009"
echo "  Prometheus:   http://100.115.61.105:9090"
echo "  Qdrant:       http://100.115.61.105:6333/dashboard"
echo "  n8n:          http://100.115.61.105:5679"
echo "  Langfuse:     http://100.115.61.105:3007"
echo "  Open WebUI:   http://100.115.61.105:3006"
echo "  Flowise:      http://100.115.61.105:3008"
echo ""
echo "Useful commands:"
echo "  docker compose ps                    # container status"
echo "  docker compose logs -f api           # follow API logs"
echo "  docker stats --no-stream             # resource usage"
echo "  docker compose -f docker-compose.yml -f docker-compose.prod.yml restart api   # restart a service"
echo ""
