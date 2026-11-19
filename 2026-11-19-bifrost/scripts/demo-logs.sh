#!/bin/bash
set -euo pipefail
. "$(dirname "$0")/demo-lib.sh"
rm -f /tmp/bf-logs.done
echo "GET ${API}/api/logs?limit=5  (no auth)"
code=$(curl -sS -o /tmp/bf-logs-noauth.txt -w "%{http_code}" "${API}/api/logs?limit=5" || true)
echo "http=${code}"
sed -n '1,6p' /tmp/bf-logs-noauth.txt
echo
echo "GET ${API}/api/logs?limit=5  (basic auth from environment, password not printed)"
curl -sS -u "${BIFROST_ADMIN_USERNAME}:${BIFROST_ADMIN_PASSWORD}" \
  "${API}/api/logs?limit=5" -o /tmp/bf-logs.json
python3 - << 'PY'
import json,re
from pathlib import Path
raw=Path("/tmp/bf-logs.json").read_text()
raw=re.sub(r"sk-[A-Za-z0-9_-]+","sk-REDACTED",raw)
obj=json.loads(raw)
logs=obj.get("logs") or obj.get("data") or obj
if isinstance(logs, dict):
    logs = logs.get("logs") or logs.get("items") or [logs]
print("count", len(logs) if isinstance(logs, list) else "?")
for i,e in enumerate((logs or [])[:5]):
    if not isinstance(e, dict):
        print(i, e); continue
    keys=("id","timestamp","object","provider","model","served_model","status","status_code")
    print(i, {k:e.get(k) for k in keys if k in e})
PY
finish bf-logs
