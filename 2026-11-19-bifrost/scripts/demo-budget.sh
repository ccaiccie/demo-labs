#!/bin/bash
set -euo pipefail
. "$(dirname "$0")/demo-lib.sh"
n="${1:-1}"
rm -f "/tmp/bf-budget${n}.done"
echo "BUDGET call ${n}  (Authorization: Bearer \$VK_BUDGET, x-bf-cache-no-store: true)"
curl -sS -D "/tmp/bf-budget${n}.headers" -o "/tmp/bf-budget${n}.body" -w "http=%{http_code} time=%{time_total}\n" \
  "${API}/v1/chat/completions" \
  -H "Authorization: Bearer ${VK_BUDGET}" \
  -H "Content-Type: application/json" \
  -H "x-bf-cache-no-store: true" \
  -d "{\"model\":\"openai/gpt-4o-mini\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with the single word ok and nonce budget${n}.\"}],\"max_tokens\":8,\"temperature\":0}"
echo "==== headers ===="
show_headers "/tmp/bf-budget${n}.headers"
echo "==== body ===="
python3 "$SHOW" "/tmp/bf-budget${n}.body"
finish "bf-budget${n}"
