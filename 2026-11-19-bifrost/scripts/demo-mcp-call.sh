#!/bin/bash
set -euo pipefail
. "$(dirname "$0")/demo-lib.sh"
rm -f /tmp/bf-mcp-call.done
echo "POST ${API}/mcp  tools/call get_interface_brief"
curl -sS -D /tmp/bf-mcp-call.headers -o /tmp/bf-mcp-call.body -w "http=%{http_code} time=%{time_total}\n" \
  "${API}/mcp" \
  -H "Authorization: Bearer ${VK_NETOPS}" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"get_interface_brief","arguments":{}}}'
# If the unprefixed name failed, retry with the client-prefixed tool name.
if ! python3 -c "import pathlib; t=pathlib.Path('/tmp/bf-mcp-call.body').read_text(); raise SystemExit(0 if 'Gigabit' in t or 'administratively' in t.lower() else 1)"; then
  echo "retrying with prefixed name netops-get_interface_brief"
  curl -sS -D /tmp/bf-mcp-call.headers -o /tmp/bf-mcp-call.body -w "http=%{http_code} time=%{time_total}\n" \
    "${API}/mcp" \
    -H "Authorization: Bearer ${VK_NETOPS}" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"netops-get_interface_brief","arguments":{}}}'
fi
echo "==== headers ===="
show_headers /tmp/bf-mcp-call.headers
echo "==== body ===="
python3 "$SHOW" /tmp/bf-mcp-call.body
finish bf-mcp-call
