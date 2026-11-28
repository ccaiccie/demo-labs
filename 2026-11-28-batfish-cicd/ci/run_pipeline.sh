#!/usr/bin/env bash
set -euo pipefail

BATFISH_HOST="${BATFISH_HOST:-127.0.0.1}"
SNAPSHOT_DIR="${SNAPSHOT_DIR:-snapshots/lab}"
export BATFISH_HOST SNAPSHOT_DIR

echo "=== Batfish Pre-Deployment Validation Pipeline ==="
echo "Batfish Host : ${BATFISH_HOST}"
echo "Snapshot Dir : ${SNAPSHOT_DIR}"

check_port() {
  local host="$1"
  local port="$2"
  if command -v python3 >/dev/null 2>&1; then
    python3 -c "import socket, sys; s = socket.create_connection((sys.argv[1], int(sys.argv[2])), timeout=3); s.close()" "$host" "$port" 2>/dev/null
  else
    (echo >/dev/tcp/"$host"/"$port") >/dev/null 2>&1
  fi
}

for port in 9996 9997; do
  if ! check_port "${BATFISH_HOST}" "${port}"; then
    echo "FAIL: Batfish is not reachable on ${BATFISH_HOST}:${port}." >&2
    echo "Start Batfish first (e.g. 'docker compose up -d') and verify ports 9996 and 9997." >&2
    exit 1
  fi
done

if command -v python3 >/dev/null 2>&1; then
  if ! python3 -c "import sys, urllib.request; r = urllib.request.urlopen(f'http://{sys.argv[1]}:9996/v2/version', timeout=3); sys.exit(0 if r.status == 200 else 1)" "${BATFISH_HOST}" 2>/dev/null; then
    echo "FAIL: Batfish HTTP API at http://${BATFISH_HOST}:9996/v2/version did not return HTTP 200." >&2
    exit 1
  fi
fi
echo "OK: Batfish reachable on ${BATFISH_HOST}:9996 (v2 API healthy) and ${BATFISH_HOST}:9997"

if [ -x ".venv/bin/pytest" ]; then
  PYTEST_BIN=".venv/bin/pytest"
else
  PYTEST_BIN="pytest"
fi

echo "Running validation checks with ${PYTEST_BIN}..."
set +e
"${PYTEST_BIN}" -v --tb=short tests/test_network.py
rc=$?
set -e

if [ "${rc}" -eq 0 ]; then
  echo "=== PIPELINE RESULT: PASS ==="
else
  echo "=== PIPELINE RESULT: FAIL (exit code ${rc}) ===" >&2
fi
exit "${rc}"
