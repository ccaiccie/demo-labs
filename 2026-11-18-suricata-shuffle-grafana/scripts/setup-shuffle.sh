#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -d shuffle/.git ]]; then
  echo "[*] Cloning Shuffle"
  git clone --depth 1 https://github.com/Shuffle/Shuffle.git shuffle
else
  echo "[*] Shuffle already cloned"
fi

cd shuffle
mkdir -p shuffle-apps shuffle-files shuffle-database

# Generate lab secrets if missing
if [[ ! -f .env.lab ]]; then
  ENC=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')
  OSPASS=$(python3 -c 'import secrets; print("Lab-" + secrets.token_urlsafe(16) + "Aa1!")')
  cat > .env.lab << EENV
# Lab-only Shuffle env for 2026-11-18-suricata-shuffle-grafana
BASE_URL=http://shuffle-backend:5001
SSO_REDIRECT_URL=http://127.0.0.1:3001
BACKEND_HOSTNAME=shuffle-backend
BACKEND_PORT=5001
FRONTEND_PORT=3001
FRONTEND_PORT_HTTPS=3443
SHUFFLE_SECURITY_PORT=3002
SHUFFLE_SECURITY_PORT_HTTPS=3444
OUTER_HOSTNAME=127.0.0.1
SHUFFLE_ENCRYPTION_MODIFIER=${ENC}
SHUFFLE_OPENSEARCH_PASSWORD=${OSPASS}
OPENSEARCH_INITIAL_ADMIN_PASSWORD=${OSPASS}
SHUFFLE_APP_HOTLOAD_LOCATION=./shuffle-apps
SHUFFLE_FILE_LOCATION=./shuffle-files
SHUFFLE_ELASTIC=true
TZ=America/Los_Angeles
EENV
  echo "[+] wrote .env.lab (secrets generated for lab only)"
fi

# Merge into .env for compose
cp .env.lab .env

# Override publish addresses to loopback only
cat > docker-compose.override.yml << 'OYAML'
services:
  frontend:
    ports: !override
      - "127.0.0.1:3001:80"
      - "127.0.0.1:3443:443"
  backend:
    ports: !override
      - "127.0.0.1:5001:5001"
  opensearch:
    ports: !override
      - "127.0.0.1:9200:9200"
    environment:
      - "OPENSEARCH_JAVA_OPTS=-Xms1024m -Xmx1024m"
  shuffle-security:
    ports: !override
      - "127.0.0.1:3002:80"
      - "127.0.0.1:3444:443"
OYAML

# Docker Swarm may be required by Orborus
if ! docker info 2>/dev/null | grep -q 'Swarm: active'; then
  echo "[*] Initializing Docker Swarm (local, for Shuffle Orborus)"
  docker swarm init || docker swarm init --advertise-addr 127.0.0.1 || true
fi

echo "[*] Pulling Shuffle images (this can take several minutes)"
docker compose pull

echo "[*] Starting Shuffle"
docker compose up -d

echo "[*] Waiting for Shuffle frontend on :3001"
for i in $(seq 1 90); do
  code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3001/ || true)
  if [[ "$code" =~ ^(200|302|301|401|403)$ ]]; then
    echo "[+] Shuffle UI responding HTTP $code"
    break
  fi
  sleep 5
  echo "  ... wait $i ($code)"
done

docker compose ps
echo "[*] Open http://127.0.0.1:3001 and create the first admin user on camera."
