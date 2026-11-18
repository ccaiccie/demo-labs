#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
echo "[*] Starting ids-lab stack (juiceshop, loki, promtail, grafana, caselog, attacker, forwarder)"
docker compose up -d juiceshop attacker loki promtail grafana caselog
"$ROOT/scripts/start-suricata.sh"
# forwarder after suricata so eve.json path exists
docker compose up -d forwarder
docker compose ps
echo "[*] Grafana: http://127.0.0.1:3010  (admin / labadmin)"
echo "[*] Juice Shop: http://127.0.0.1:3200"
echo "[*] Case log: http://127.0.0.1:8099/cases"
