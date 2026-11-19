#!/usr/bin/env bash
# Read-only health check for the self-hosted Nod stack. Prints .env variable NAMES only, never values.
set -euo pipefail
cd "${1:-$HOME/nod/deployment/self-host}"
echo "== .env variable names (values hidden)"; grep -oE '^[A-Z_]+=' .env
echo "== non-secret settings"; grep -E '^(PORT|NOD_BIND_ADDRESS|NOD_PUBLIC_URL)=' .env
echo "== containers"; docker compose ps --format 'table {{.Service}}\t{{.Status}}\t{{.Ports}}'
echo "== recent logs"; docker compose logs --tail 4 server browser
echo "== HTTP"; curl -s -o /dev/null -w 'HTTP %{http_code}\n' "http://localhost:${PORT:-4310}/"
docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}' $(docker compose ps -q)
