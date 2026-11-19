#!/bin/bash
set -euo pipefail
. "$(dirname "$0")/demo-lib.sh"
echo "CACHE HIT  same prompt, key=netops-rec-19  (direct)"
curl -sS -D /tmp/bf-cache2.headers -o /tmp/bf-cache2.body -w "http=%{http_code} time=%{time_total}\n" \
  "${API}/v1/chat/completions" \
  -H "Authorization: Bearer ${VK_NETOPS}" \
  -H "Content-Type: application/json" \
  -H "x-bf-cache-key: netops-rec-19" \
  -d '{"model":"openai/gpt-4o-mini","messages":[{"role":"user","content":"Name one common cause of an OSPF neighbor stuck in EXSTART, in one short sentence."}],"max_tokens":40,"temperature":0}'
echo "==== headers ===="
show_headers /tmp/bf-cache2.headers
echo "==== body ===="
python3 "$SHOW" /tmp/bf-cache2.body
finish bf-cache2
