#!/bin/bash
set -euo pipefail
. "$(dirname "$0")/demo-lib.sh"
echo "POST ${API}/v1/chat/completions  (Authorization: Bearer \$VK_NETOPS)"
curl -sS -D /tmp/bf-dropin1.headers -o /tmp/bf-dropin1.body -w "http=%{http_code} time=%{time_total}\n" \
  "${API}/v1/chat/completions" \
  -H "Authorization: Bearer ${VK_NETOPS}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-4o-mini",
    "messages": [{"role": "user", "content": "In one sentence, what is a BGP hold timer?"}],
    "max_tokens": 60,
    "temperature": 0
  }'
echo "==== headers ===="
show_headers /tmp/bf-dropin1.headers
echo "==== body ===="
python3 "$SHOW" /tmp/bf-dropin1.body
finish bf-dropin1
