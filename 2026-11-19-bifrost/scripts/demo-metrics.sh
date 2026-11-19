#!/bin/bash
set -euo pipefail
. "$(dirname "$0")/demo-lib.sh"
rm -f /tmp/bf-metrics.done
echo "GET ${API}/metrics  (no auth)"
code=$(curl -sS -o /tmp/bf-metrics-noauth.txt -w "%{http_code}" "${API}/metrics" || true)
echo "http=${code}"
sed -n '1,8p' /tmp/bf-metrics-noauth.txt
echo
echo "GET ${API}/metrics  (basic auth from environment, password not printed)"
curl -sS -u "${BIFROST_ADMIN_USERNAME}:${BIFROST_ADMIN_PASSWORD}" \
  "${API}/metrics" | grep -E '^(# HELP bifrost_|# TYPE bifrost_|bifrost_(cost_total|input_tokens_total|active_requests|requests_total|cache))' | head -n 40
finish bf-metrics
