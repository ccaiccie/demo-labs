#!/usr/bin/env bash
# Usage: set-webhook.sh https://... or http://127.0.0.1:5001/api/v1/hooks/webhook_xxx
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
URL="${1:-}"
if [[ -z "$URL" ]]; then
  echo "usage: $0 <shuffle-webhook-url>" >&2
  exit 1
fi
cd "$ROOT"
echo "SHUFFLE_WEBHOOK=$URL" > .env.webhook
# recreate forwarder with new env
export SHUFFLE_WEBHOOK="$URL"
docker compose up -d forwarder
echo "[+] forwarder restarted with webhook"
