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

# Start from upstream .env and override only what the lab needs.
# (Keep OUTER_HOSTNAME=shuffle-backend so Orborus/workers can reach the backend.)
git show HEAD:.env > .env.upstream 2>/dev/null || cp .env .env.upstream
ENC=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')
OSPASS=$(python3 -c 'import secrets; print("Lab-" + secrets.token_urlsafe(16) + "Aa1!")')
python3 - "$ENC" "$OSPASS" << 'PYENV'
import sys, re
enc, ospass = sys.argv[1], sys.argv[2]
t = open(".env.upstream").read()
over = {
  "SSO_REDIRECT_URL": "http://127.0.0.1:3001",
  "FRONTEND_PORT": "3001", "FRONTEND_PORT_HTTPS": "3443", "BACKEND_PORT": "5001",
  "OUTER_HOSTNAME": "shuffle-backend",
  "SHUFFLE_ENCRYPTION_MODIFIER": enc,
  "SHUFFLE_OPENSEARCH_PASSWORD": ospass,
  "TZ": "America/Los_Angeles",
  "SHUFFLE_APP_REPLICAS": "1",
}
for k, v in over.items():
    if re.search(rf"^{k}=.*$", t, re.M):
        t = re.sub(rf"^{k}=.*$", f"{k}={v}", t, flags=re.M)
    else:
        t += f"\n{k}={v}\n"
open(".env", "w").write(t)
print("[+] wrote .env (upstream + lab overrides; secrets generated, not printed)")
PYENV

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

echo "[*] Waiting for Shuffle backend API"
for i in $(seq 1 60); do
  code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:5001/api/v1/checkusers || true)
  if [[ "$code" == "200" ]]; then echo "[+] Shuffle backend ready"; break; fi
  sleep 5
done

docker compose ps --format 'table {{.Name}}\t{{.Status}}\t{{.Ports}}'
echo "[*] Open http://127.0.0.1:3001 and create the first admin user on camera."
