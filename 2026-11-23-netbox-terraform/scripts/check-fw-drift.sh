#!/usr/bin/env bash
set -euo pipefail
CONTAINER="nb-tf-fw-edge-01"

if ! docker exec "${CONTAINER}" test -f /etc/nftables.d/fw-edge-01.applied 2>/dev/null; then
  printf '{"firewall_state":"in_sync"}\n'
  exit 0
fi

LIVE_HASH=$(docker exec "${CONTAINER}" sh -c 'nft list table inet lab_fw 2>/dev/null | sha256sum | cut -d" " -f1')
APPLIED_HASH=$(docker exec "${CONTAINER}" sh -c 'sha256sum /etc/nftables.d/fw-edge-01.applied | cut -d" " -f1')

if [ "${LIVE_HASH}" = "${APPLIED_HASH}" ]; then
  printf '{"firewall_state":"in_sync"}\n'
else
  printf '{"firewall_state":"drifted-%s"}\n' "${LIVE_HASH:0:12}"
fi
