#!/usr/bin/env bash
set -euo pipefail
echo "[*] Running local attacker against ids-juiceshop"
docker exec ids-attacker sh /attack.sh
echo "[*] Recent eve alerts:"
docker run --rm -v ids-lab_suricata-logs:/var/log/suricata --entrypoint sh jasonish/suricata:latest -c \
  "grep '\"event_type\":\"alert\"' /var/log/suricata/eve.json | tail -20" || true
