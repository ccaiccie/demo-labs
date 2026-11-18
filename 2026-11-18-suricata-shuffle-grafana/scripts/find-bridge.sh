#!/usr/bin/env bash
set -euo pipefail
ID=$(docker network inspect ids-lab -f '{{.Id}}' 2>/dev/null || true)
if [[ -z "${ID}" ]]; then
  echo "ids-lab network not found" >&2
  exit 1
fi
# Docker bridge is br-<first 12 of network id>
BR="br-${ID:0:12}"
if [[ ! -d "/sys/class/net/$BR" ]]; then
  # fallback: look for bridge that has juiceshop veth
  BR=$(ip -o link show | awk -F': ' '/br-/{print $2}' | head -1)
fi
echo "$BR"
