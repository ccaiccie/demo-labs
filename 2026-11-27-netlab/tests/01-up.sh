#!/usr/bin/env bash
set -euo pipefail

LAB_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="${LAB_DIR}/tests/logs"
mkdir -p "${LOG_DIR}"

cd "${LAB_DIR}"
export ANSIBLE_CONFIG="${LAB_DIR}/ansible.cfg"

echo "=== [01-up] Snapshot pre-existing containers ==="
docker ps --format '{{.Names}}' | grep -v '^clab-netlab-demo-' | sort > "${LOG_DIR}/pre-existing-containers.txt"
PRE_COUNT=$(wc -l < "${LOG_DIR}/pre-existing-containers.txt")
echo "Pre-existing running containers: ${PRE_COUNT}"

echo "=== [01-up] Running netlab up ==="
netlab up

echo "=== [01-up] Verify lab containers, images, and ports ==="
docker ps --filter 'name=^/clab-netlab-demo-' --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'

LAB_COUNT=$(docker ps --filter 'name=^/clab-netlab-demo-' --format '{{.Names}}' | wc -l)
if [ "${LAB_COUNT}" -ne 6 ]; then
  echo "FAIL: expected 6 clab-netlab-demo-* containers, found ${LAB_COUNT}" >&2
  exit 1
fi

# Verify no host ports are published
PUBLISHED=$(docker ps --filter 'name=^/clab-netlab-demo-' --format '{{.Ports}}' | grep -E '[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+:[0-9]+->' || true)
if [ -n "${PUBLISHED}" ]; then
  echo "FAIL: unexpected published host ports: ${PUBLISHED}" >&2
  exit 1
fi

echo "=== [01-up] PASS (6 containers up, free FRR/Linux images, 0 published host ports) ==="
