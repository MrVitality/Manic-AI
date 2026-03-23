#!/bin/bash
# Manic AI -- Host Provisioning Script
# Run on a fresh Ubuntu 22.04+ server to prepare for deployment
set -euo pipefail

echo "============================================"
echo "  Manic AI -- Host Provisioning"
echo "============================================"

# Check root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (sudo)"
  exit 1
fi

# Update system
echo "[1/6] Updating system packages..."
apt-get update -qq && apt-get upgrade -y -qq

# Install Docker
echo "[2/6] Installing Docker..."
if ! command -v docker &> /dev/null; then
  curl -fsSL https://get.docker.com | sh
  systemctl enable docker
  systemctl start docker
else
  echo "  Docker already installed: $(docker --version)"
fi

# Install Docker Compose plugin
echo "[3/6] Verifying Docker Compose..."
docker compose version || {
  apt-get install -y docker-compose-plugin
}

# Create deploy user
DEPLOY_USER=${1:-deploy}
echo "[4/6] Creating deploy user: $DEPLOY_USER"
if ! id "$DEPLOY_USER" &>/dev/null; then
  useradd -m -s /bin/bash -G docker "$DEPLOY_USER"
  echo "  User $DEPLOY_USER created and added to docker group"
else
  usermod -aG docker "$DEPLOY_USER"
  echo "  User $DEPLOY_USER already exists, added to docker group"
fi

# Configure firewall
echo "[5/6] Configuring firewall (ufw)..."
apt-get install -y -qq ufw
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp    # HTTP (Caddy redirect)
ufw allow 443/tcp   # HTTPS (Caddy)
ufw allow 443/udp   # HTTP/3 (Caddy)
ufw --force enable
echo "  Firewall enabled: SSH + HTTP/HTTPS only"

# Install useful tools
echo "[6/6] Installing utilities..."
apt-get install -y -qq git curl wget htop ncdu jq

echo ""
echo "============================================"
echo "  Provisioning complete!"
echo "============================================"
echo ""
echo "Next steps:"
echo "  1. Switch to deploy user:  su - $DEPLOY_USER"
echo "  2. Clone the repo:         git clone <repo-url> ~/Manic-AI"
echo "  3. Copy env file:          cp .env.example .env && nano .env"
echo "  4. Generate Supabase keys: ./scripts/gen-supabase-keys.sh"
echo "  5. Start services:         docker compose up -d"
echo "  6. Point DNS:              A record -> this server's IP"
echo ""
