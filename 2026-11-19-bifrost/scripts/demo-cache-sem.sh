#!/bin/bash
set -euo pipefail
. "$(dirname "$0")/demo-lib.sh"
echo "CACHE SEMANTIC  similar wording, key=netops-rec-19"
curl -sS -D /tmp/bf-cache3.headers -o /tmp/bf-cache3.body -w "http=%{http_code} time=%{time_total}\n" \
  "${API}/v1/chat/completions" \
  -H "Authorization: Bearer ${VK_NETOPS}" \
  -H "Content-Type: application/json" \
  -H "x-bf-cache-key: netops-rec-19" \
  -H "x-bf-cache-type: semantic" \
  -d '{"model":"openai/gpt-4o-mini","messages":[{"role":"user","content":"In one short sentence, what often causes an OSPF neighbor to stay in the EXSTART state?"}],"max_tokens":40,"temperature":0}'
echo "==== headers ===="
show_headers /tmp/bf-cache3.headers
echo "==== body ===="
python3 "$SHOW" /tmp/bf-cache3.body
finish bf-cache3
