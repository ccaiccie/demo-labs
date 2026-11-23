#!/usr/bin/env bash
set -euo pipefail

NFT_FILE="${1:?Usage: apply-firewall.sh <path-to-nft-file>}"
CONTAINER="nb-tf-fw-edge-01"

echo "==> Copying generated nftables ruleset to ${CONTAINER}..."
docker cp "${NFT_FILE}" "${CONTAINER}:/etc/nftables.d/fw-edge-01.nft"

echo "==> Validating syntax on ${CONTAINER} (nft -c -f)..."
docker exec "${CONTAINER}" nft -c -f /etc/nftables.d/fw-edge-01.nft

echo "==> Applying ruleset on ${CONTAINER} (nft -f)..."
docker exec "${CONTAINER}" nft -f /etc/nftables.d/fw-edge-01.nft
docker exec "${CONTAINER}" sh -c 'nft list table inet lab_fw > /etc/nftables.d/fw-edge-01.applied'

echo "==> Applying NetBox gateway IPs to ${CONTAINER} interfaces..."
docker exec "${CONTAINER}" bash -c '
  ip addr replace 198.51.100.1/24 dev eth-lan
  ip addr replace 203.0.113.1/24 dev eth-dmz
  ip addr replace 192.0.2.1/24 dev eth-mgmt
'

echo "==> Firewall ${CONTAINER} updated successfully."
