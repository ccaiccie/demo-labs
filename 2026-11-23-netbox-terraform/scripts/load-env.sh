#!/usr/bin/env bash
# Load NetBox API credentials into the current shell without printing secrets.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck disable=SC1091
source "${ROOT_DIR}/docker/.env"
export NETBOX_SERVER_URL="http://127.0.0.1:8000"
export NETBOX_API_TOKEN="${SUPERUSER_API_TOKEN}"
export PATH="$HOME/.local/bin:$PATH"
echo "Loaded NETBOX_SERVER_URL=${NETBOX_SERVER_URL} and NETBOX_API_TOKEN (masked)."
