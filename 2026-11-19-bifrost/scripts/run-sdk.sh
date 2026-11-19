#!/bin/bash
set -euo pipefail
. "$(dirname "$0")/demo-lib.sh"
export BIFROST_BASE="${BIFROST_BASE:-http://127.0.0.1:8088/openai/v1}"
echo "OpenAI SDK drop-in  base_url=\$BIFROST_BASE  api_key=\$VK_NETOPS (not printed)"
if [ -x "$ROOT/.venv/bin/python" ] && "$ROOT/.venv/bin/python" -c "import openai" 2>/dev/null; then
  "$ROOT/.venv/bin/python" "$ROOT/scripts/sdk_chat.py"
elif command -v python3 >/dev/null && python3 -c "import openai" 2>/dev/null; then
  python3 "$ROOT/scripts/sdk_chat.py"
else
  docker run --rm --network host \
    -e VK_NETOPS -e BIFROST_BASE \
    -v "$ROOT/scripts/sdk_chat.py:/app/sdk_chat.py:ro" \
    bifrost-demo-sdk:local python /app/sdk_chat.py
fi
finish bf-sdk
