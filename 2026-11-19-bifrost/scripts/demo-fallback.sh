#!/bin/bash
set -euo pipefail
. "$(dirname "$0")/demo-lib.sh"
rm -f /tmp/bf-fallback.done
echo "POST ${API}/v1/chat/completions  bad OpenAI model, fallbacks=[ollama/llama3.2:1b]"
curl -sS -D /tmp/bf-fallback.headers -o /tmp/bf-fallback.body -w "http=%{http_code} time=%{time_total}\n" \
  "${API}/v1/chat/completions" \
  -H "Authorization: Bearer ${VK_NETOPS}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/this-model-does-not-exist-xyz",
    "fallbacks": ["ollama/llama3.2:1b"],
    "messages": [{"role": "user", "content": "Say hello in five words. Do not call tools."}],
    "max_tokens": 40,
    "temperature": 0
  }'
echo "==== headers ===="
show_headers /tmp/bf-fallback.headers
echo "==== body ===="
python3 "$SHOW" /tmp/bf-fallback.body
cp -f "$SHOW" /tmp/bf-show.py
finish bf-fallback
