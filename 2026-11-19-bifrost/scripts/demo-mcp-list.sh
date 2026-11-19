#!/bin/bash
set -euo pipefail
. "$(dirname "$0")/demo-lib.sh"
rm -f /tmp/bf-mcp-list.done
echo "POST ${API}/mcp  tools/list  (Authorization: Bearer \$VK_NETOPS)"
curl -sS -D /tmp/bf-mcp-list.headers -o /tmp/bf-mcp-list.body -w "http=%{http_code} time=%{time_total}\n" \
  "${API}/mcp" \
  -H "Authorization: Bearer ${VK_NETOPS}" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
echo "==== headers ===="
show_headers /tmp/bf-mcp-list.headers
echo "==== body ===="
python3 "$SHOW" /tmp/bf-mcp-list.body
finish bf-mcp-list
