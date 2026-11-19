#!/bin/bash
# Shared helpers for on-camera demo scripts. Sources .env without printing values.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
set -a
# shellcheck disable=SC1091
source "$ROOT/.env"
set +a
API="${BIFROST_API:-http://127.0.0.1:8088}"
SHOW="$ROOT/scripts/bf-show.py"

show_headers() {
  local f="$1"
  grep -iE '^(HTTP/|HTTP |x-bifrost-|x-bf-|content-type:)' "$f" || true
}

finish() {
  local stamp="$1"
  touch "/tmp/${stamp}.done"
}
