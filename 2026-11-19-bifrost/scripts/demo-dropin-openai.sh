#!/bin/bash
set -euo pipefail
. "$(dirname "$0")/demo-lib.sh"
echo "POST ${API}/openai/v1/chat/completions  (Authorization: Bearer \$VK_NETOPS)"
curl -sS -D /tmp/bf-dropin2.headers -o /tmp/bf-dropin2.body -w "http=%{http_code} time=%{time_total}\n" \
  "${API}/openai/v1/chat/completions" \
  -H "Authorization: Bearer ${VK_NETOPS}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "Reply with the single word pong."}],
    "max_tokens": 8,
    "temperature": 0
  }'
echo "==== headers ===="
show_headers /tmp/bf-dropin2.headers
echo "==== body ===="
python3 "$SHOW" /tmp/bf-dropin2.body
finish bf-dropin2
