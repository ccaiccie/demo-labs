#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

echo "=== [1/6] Validate and start Docker Compose stack (project: librenms-api) ==="
docker compose -p librenms-api config -q
docker compose -p librenms-api up -d --build

echo "=== [2/6] Bootstrap LibreNMS admin user and API token ==="
bash "${SCRIPT_DIR}/bootstrap-auth.sh"

echo "=== [3/6] Bulk-add lab devices via REST API v0 ==="
python3 "${SCRIPT_DIR}/bulk-add-devices.py"

echo "=== [4/6] Configure auto-discovery and scan edge subnet ==="
bash "${SCRIPT_DIR}/configure-discovery.sh"

echo "=== [5/6] Load NetOps alert rules pack via REST API v0 ==="
python3 "${SCRIPT_DIR}/load-alert-rules.py"

echo "=== [6/6] Configure local webhook transport and verify alert delivery ==="
bash "${SCRIPT_DIR}/configure-webhook-and-test.sh"

echo ""
echo "=== ALL LIBRENMS-API LAB TESTS PASSED ==="
docker compose -p librenms-api ps
