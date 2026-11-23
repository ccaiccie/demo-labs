#!/usr/bin/env bash
set -euo pipefail

CONTAINER="nb-tf-fw-edge-01"

echo "============================================================"
echo "  LIVE FIREWALL INTERFACES (${CONTAINER})"
echo "============================================================"
docker exec "${CONTAINER}" ip -br addr show | grep -E "eth-"

echo ""
echo "============================================================"
echo "  LIVE NFTABLES RULESET (${CONTAINER})"
echo "============================================================"
docker exec "${CONTAINER}" nft list table inet lab_fw
