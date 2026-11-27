#!/usr/bin/env bash
set -euo pipefail

LAB_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="${LAB_DIR}/tests/logs"
mkdir -p "${LOG_DIR}"

cd "${LAB_DIR}"
export ANSIBLE_CONFIG="${LAB_DIR}/ansible.cfg"

echo "=== [06-down] Running netlab down --cleanup ==="
netlab down --cleanup

echo "=== [06-down] Verify no clab-netlab-demo-* containers remain ==="
LEFTOVER=$(docker ps -a --filter 'name=^/clab-netlab-demo-' --format '{{.Names}}' || true)
if [ -n "${LEFTOVER}" ]; then
  echo "FAIL: leftover containers found: ${LEFTOVER}" >&2
  exit 1
fi
echo "Confirmed: 0 clab-netlab-demo-* containers remain."

echo "=== [06-down] Verify netlab-demo-mgmt Docker network removed ==="
if docker network ls --format '{{.Name}}' | grep -qx 'netlab-demo-mgmt'; then
  echo "FAIL: netlab-demo-mgmt Docker network still exists" >&2
  exit 1
fi
echo "Confirmed: netlab-demo-mgmt Docker network removed."

echo "=== [06-down] Verify pre-existing containers untouched ==="
docker ps --format '{{.Names}}' | grep -v '^clab-netlab-demo-' | sort > "${LOG_DIR}/post-existing-containers.txt"
POST_COUNT=$(wc -l < "${LOG_DIR}/post-existing-containers.txt")
echo "Post-teardown pre-existing running containers: ${POST_COUNT}"
if [ -f "${LOG_DIR}/pre-existing-containers.txt" ]; then
  if diff -u "${LOG_DIR}/pre-existing-containers.txt" "${LOG_DIR}/post-existing-containers.txt"; then
    echo "Confirmed: pre-existing container set is identical before and after lab run."
  else
    echo "WARNING: pre-existing container list changed (review diff above)."
  fi
fi

echo "=== [06-down] PASS ==="
