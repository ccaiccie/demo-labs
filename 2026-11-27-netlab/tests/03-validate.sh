#!/usr/bin/env bash
set -euo pipefail

LAB_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${LAB_DIR}"
export ANSIBLE_CONFIG="${LAB_DIR}/ansible.cfg"

echo "=== [03-validate] Running netlab validate ==="
netlab validate

echo "=== [03-validate] PASS ==="
