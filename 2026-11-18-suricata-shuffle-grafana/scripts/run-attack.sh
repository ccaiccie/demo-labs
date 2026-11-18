#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo "[*] Running local attacker against ids-juiceshop (lab network only)"
docker exec ids-attacker sh /attack.sh
sleep 3
echo "[*] Suricata alert summary:"
"$ROOT/scripts/show-alerts.sh"
