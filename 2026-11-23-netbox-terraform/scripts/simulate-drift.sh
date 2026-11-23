#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck disable=SC1091
source "${ROOT_DIR}/docker/.env"

NETBOX_URL="${NETBOX_SERVER_URL:-http://127.0.0.1:8000}"
AUTH_HEADER="Authorization: Token ${SUPERUSER_API_TOKEN}"

echo "==> 1. Simulating manual NetBox edit (someone changed eth-lan description by hand)..."
IFACE_ID=$(curl -fsS -H "${AUTH_HEADER}" "${NETBOX_URL}/api/dcim/interfaces/?name=eth-lan&device=fw-edge-01" \
  | python3 -c 'import sys,json; d=json.load(sys.stdin)["results"]; print(d[0]["id"])')

curl -fsS -X PATCH \
  -H "${AUTH_HEADER}" \
  -H "Content-Type: application/json" \
  -d '{"description": "MANUAL-HOTFIX-TEMP-DO-NOT-USE"}' \
  "${NETBOX_URL}/api/dcim/interfaces/${IFACE_ID}/" >/dev/null

echo "    Changed NetBox interface eth-lan (id=${IFACE_ID}) description to: MANUAL-HOTFIX-TEMP-DO-NOT-USE"

echo "==> 2. Simulating manual firewall drift (someone added an unauthorized Telnet rule on nb-tf-fw-edge-01)..."
docker exec nb-tf-fw-edge-01 nft insert rule inet lab_fw forward tcp dport 23 accept comment '"ROGUE_MANUAL_TELNET"'

echo "==> Drift injected! Now run 'terraform plan' to see Terraform detect it."
