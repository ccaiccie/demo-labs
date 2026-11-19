#!/bin/bash
set -euo pipefail
. "$(dirname "$0")/demo-lib.sh"
rm -f /tmp/bf-mcp-chat.done
echo "POST ${API}/v1/chat/completions  (ask the model to use tools)"
curl -sS -D /tmp/bf-mcp-chat.headers -o /tmp/bf-mcp-chat.body -w "http=%{http_code} time=%{time_total}\n" \
  "${API}/v1/chat/completions" \
  -H "Authorization: Bearer ${VK_NETOPS}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-4o-mini",
    "messages": [{"role": "user", "content": "Use the available tools to read the sample interface brief and tell me which interface is administratively down. One short sentence."}],
    "max_tokens": 80,
    "temperature": 0
  }'
echo "==== headers ===="
show_headers /tmp/bf-mcp-chat.headers
echo "==== body ===="
python3 "$SHOW" /tmp/bf-mcp-chat.body
finish bf-mcp-chat
