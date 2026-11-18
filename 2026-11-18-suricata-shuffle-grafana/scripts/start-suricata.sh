#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

"$ROOT/scripts/prepare-suricata-yaml.sh"

docker compose up -d juiceshop
sleep 1
IFACE=$("$ROOT/scripts/find-bridge.sh")
echo "[*] Suricata will sniff interface: $IFACE"
ip -br link show "$IFACE" || true

docker rm -f ids-suricata 2>/dev/null || true

echo "[*] Updating Emerging Threats Open rules into volume (first run can take a bit)"
docker run --rm \
  -v ids-lab_suricata-lib:/var/lib/suricata \
  --entrypoint suricata-update \
  jasonish/suricata:latest || true

# Writable config copies (avoid RO chown failures on bind mounts from /mnt/c)
RUN="${HOME}/suricata-run"
rm -rf "$RUN"
mkdir -p "$RUN/etc/rules"
cp "$ROOT/suricata/etc/suricata.yaml" "$RUN/etc/"
cp "$ROOT/suricata/rules/local.rules" "$RUN/etc/rules/"
if [[ -f "$ROOT/suricata/etc/threshold.config" ]]; then cp "$ROOT/suricata/etc/threshold.config" "$RUN/etc/threshold.config"; else echo "# empty" > "$RUN/etc/threshold.config"; fi

docker run --rm \
  -v ids-lab_suricata-lib:/var/lib/suricata \
  -v "$RUN/etc/rules/local.rules:/local.rules:ro" \
  --entrypoint sh \
  jasonish/suricata:latest -c 'mkdir -p /var/lib/suricata/rules && cp /local.rules /var/lib/suricata/rules/local.rules && ls -la /var/lib/suricata/rules | head'

docker run -d --name ids-suricata \
  --net=host \
  --cap-add=net_admin --cap-add=net_raw --cap-add=sys_nice \
  -v ids-lab_suricata-logs:/var/log/suricata \
  -v ids-lab_suricata-lib:/var/lib/suricata \
  -v "$RUN/etc/suricata.yaml:/etc/suricata/suricata.yaml" \
  -v "$RUN/etc/rules/local.rules:/etc/suricata/rules/local.rules" \
  -v "$RUN/etc/threshold.config:/etc/suricata/threshold.config" \
  jasonish/suricata:latest -i "$IFACE" -v

echo "[+] ids-suricata started on $IFACE"
sleep 5
docker logs --tail 40 ids-suricata || true
