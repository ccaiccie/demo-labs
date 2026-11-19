#!/usr/bin/env bash
# Usage: ./senders/send-log.sh <host> "<log message>"
# POSTs one device log as JSON to the n8n webhook and pretty-prints the AI verdict n8n returns.
# Needs only curl and python3.
URL="${N8N_URL:-http://localhost:5678/webhook/netlog}"
HOST="${1:?host}"; MSG="${2:?message}"
BODY=$(python3 -c 'import json,sys; print(json.dumps({"host": sys.argv[1], "message": sys.argv[2]}))' "$HOST" "$MSG")
curl -s -X POST "$URL" -H 'Content-Type: application/json' -d "$BODY" | python3 -m json.tool
