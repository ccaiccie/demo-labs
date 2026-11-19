#!/bin/bash
set -euo pipefail
. "$(dirname "$0")/demo-lib.sh"
n="${1:-1}"
rm -f "/tmp/bf-limit${n}.done"
echo "RATE LIMIT call ${n}  (Authorization: Bearer \$VK_LIMITED)"
curl -sS -D "/tmp/bf-limit${n}.headers" -o "/tmp/bf-limit${n}.body" -w "http=%{http_code} time=%{time_total}\n" \
  "${API}/v1/chat/completions" \
  -H "Authorization: Bearer ${VK_LIMITED}" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"openai/gpt-4o-mini\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with the single word ok${n}.\"}],\"max_tokens\":6,\"temperature\":0}"
echo "==== headers ===="
show_headers "/tmp/bf-limit${n}.headers"
echo "==== body ===="
python3 "$SHOW" "/tmp/bf-limit${n}.body"
finish "bf-limit${n}"
