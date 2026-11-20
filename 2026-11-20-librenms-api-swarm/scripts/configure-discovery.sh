#!/usr/bin/env bash
set -euo pipefail

CONTAINER="${LIBRENMS_CONTAINER:-librenms-api-web}"
BASE_URL="${LIBRENMS_URL:-http://127.0.0.1:8012}"
TOKEN_FILE="${LIBRENMS_TOKEN_FILE:-/tmp/librenms-api.token}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
FIXTURE="${REPO_ROOT}/fixtures/discovery.json"

if [[ -n "${LIBRENMS_API_TOKEN:-}" ]]; then
  TOKEN="${LIBRENMS_API_TOKEN}"
elif [[ -f "${TOKEN_FILE}" ]]; then
  TOKEN="$(cat "${TOKEN_FILE}")"
else
  echo "[configure-discovery] ERROR: API token not found. Run scripts/bootstrap-auth.sh first." >&2
  exit 1
fi

echo "[configure-discovery] Parsing ${FIXTURE}..."
NETS_JSON="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(json.dumps(d["nets"]))' "${FIXTURE}")"
COMM_JSON="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(json.dumps(d["snmp"]["community"]))' "${FIXTURE}")"
EXCL_JSON="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(json.dumps(d["settings"].get("autodiscovery.nets-exclude", [])))' "${FIXTURE}")"
DISC_BY_IP="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print("true" if d["settings"].get("discovery_by_ip", True) else "false")' "${FIXTURE}")"
NORMALIZE_TO_IP="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); s=d["settings"]; print("true" if s.get("normalize_discovered_hostname_to_ip", s.get("discovery_by_ip", True)) else "false")' "${FIXTURE}")"
SCAN_SUBNETS="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(" ".join(d["scan_subnets"]))' "${FIXTURE}")"

echo "[configure-discovery] Configuring LibreNMS auto-discovery subnets and settings via lnms config:set..."
docker exec -u librenms "${CONTAINER}" lnms config:set nets "${NETS_JSON}"
docker exec -u librenms "${CONTAINER}" lnms config:set discovery_by_ip "${DISC_BY_IP}"
docker exec -u librenms "${CONTAINER}" lnms config:set autodiscovery.nets-exclude "${EXCL_JSON}"

echo "[configure-discovery] Registering SNMPv2c community credential(s) in LibreNMS Secrets store..."
CRED_IDS_JSON="$(docker exec -u librenms "${CONTAINER}" php -r '
require "/opt/librenms/vendor/autoload.php";
$app = require "/opt/librenms/bootstrap/app.php";
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();

$communities = json_decode($argv[1], true, 512, JSON_THROW_ON_ERROR);
$ids = [];
foreach ($communities as $comm) {
    $existing = App\Models\Secret::where("secret_type", LibreNMS\Enum\SecretType::SnmpCommunity)
        ->get()
        ->first(fn ($s) => ($s->data["community"] ?? null) === $comm);
    if ($existing) {
        $ids[] = (int) $existing->id;
    } else {
        $created = App\Models\Secret::create([
            "description" => "Lab SNMPv2c Community",
            "secret_type" => LibreNMS\Enum\SecretType::SnmpCommunity,
            "data" => ["community" => $comm],
        ]);
        $ids[] = (int) $created->id;
    }
}
echo json_encode(array_values(array_unique($ids)));
' -- "${COMM_JSON}")"
echo "[configure-discovery] Binding snmp.default_credentials to secret ID(s): ${CRED_IDS_JSON}"
docker exec -u librenms "${CONTAINER}" lnms config:set snmp.default_credentials "${CRED_IDS_JSON}"

echo "[configure-discovery] Current configured nets and snmp.default_credentials:"
docker exec -u librenms "${CONTAINER}" lnms config:get nets
docker exec -u librenms "${CONTAINER}" lnms config:get snmp.default_credentials

for subnet in ${SCAN_SUBNETS}; do
  echo "[configure-discovery] Running lnms scan:network ${subnet}..."
  docker exec -u librenms "${CONTAINER}" lnms scan:network "${subnet}"
done

if [[ "${NORMALIZE_TO_IP}" == "true" ]]; then
  echo "[configure-discovery] Normalizing auto-discovered hostnames in scanned subnet(s) to IP..."
  PRE_DEVICES_JSON="$(curl -sS -H "X-Auth-Token: ${TOKEN}" "${BASE_URL}/api/v0/devices")"
  RENAME_PAIRS="$(python3 - "${PRE_DEVICES_JSON}" "${FIXTURE}" <<'PY'
import ipaddress
import json
import sys

resp = json.loads(sys.argv[1])
fixture = json.load(open(sys.argv[2], encoding="utf-8"))
nets = [ipaddress.ip_network(n) for n in fixture.get("scan_subnets", [])]
expected_ips = {e["ip"] for e in fixture.get("expected_discovered_devices", [])}

for d in resp.get("devices", []):
    ip = (d.get("ip") or "").strip()
    hostname = (d.get("hostname") or "").strip()
    if not ip or not hostname or hostname == ip:
        continue
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        continue
    if ip in expected_ips or any(addr in net for net in nets):
        print(f"{hostname}\t{ip}")
PY
)"
  if [[ -n "${RENAME_PAIRS}" ]]; then
    while IFS=$'\t' read -r old_host target_ip; do
      [[ -z "${old_host}" || -z "${target_ip}" ]] && continue
      echo "[configure-discovery] Renaming discovered device '${old_host}' -> '${target_ip}'..."
      docker exec -u librenms "${CONTAINER}" lnms device:rename "${old_host}" "${target_ip}"
    done <<< "${RENAME_PAIRS}"
  else
    echo "[configure-discovery] All discovered devices already use IP hostnames."
  fi
fi

echo "[configure-discovery] Running discovery and poller across all devices..."
docker exec -u librenms "${CONTAINER}" lnms device:discover all >/dev/null
docker exec -u librenms "${CONTAINER}" lnms device:poll all >/dev/null

echo "[configure-discovery] Verifying auto-discovered devices via GET /api/v0/devices (auth=<REDACTED_TOKEN>)..."
DEVICES_JSON="$(curl -sS -H "X-Auth-Token: ${TOKEN}" "${BASE_URL}/api/v0/devices")"

python3 - "${DEVICES_JSON}" "${FIXTURE}" <<'PY'
import json
import sys

resp = json.loads(sys.argv[1])
fixture = json.load(open(sys.argv[2], encoding="utf-8"))
devices = resp.get("devices", [])
normalize_to_ip = fixture.get("settings", {}).get(
    "normalize_discovered_hostname_to_ip",
    fixture.get("settings", {}).get("discovery_by_ip", True),
)

print(f"[configure-discovery] Total devices in LibreNMS: {len(devices)}")
for d in devices:
    print(
        f"  - id={d.get('device_id')} hostname={d.get('hostname')} ip={d.get('ip')} "
        f"sysName={d.get('sysName')} status={d.get('status')} "
        f"uptime={d.get('uptime')} last_polled={d.get('last_polled')}"
    )

missing = []
unpolled = []
wrong_hostname = []
for exp in fixture["expected_discovered_devices"]:
    ip = exp["ip"]
    sys_name = exp.get("sysName")
    dev = next(
        (
            d
            for d in devices
            if d.get("ip") == ip
            or d.get("hostname") == ip
            or (sys_name and d.get("sysName") == sys_name)
        ),
        None,
    )
    if not dev:
        missing.append(f"{ip} ({sys_name})")
    else:
        if normalize_to_ip and dev.get("hostname") != ip:
            wrong_hostname.append((ip, dev.get("hostname")))
        if not dev.get("last_polled") or str(dev.get("status")) != "1":
            unpolled.append((ip, dev.get("status"), dev.get("last_polled")))

if missing:
    print(f"[configure-discovery] ERROR: Expected auto-discovered devices missing: {missing}", file=sys.stderr)
    sys.exit(1)
if wrong_hostname:
    print(f"[configure-discovery] ERROR: Auto-discovered devices not named by IP: {wrong_hostname}", file=sys.stderr)
    sys.exit(1)
if unpolled:
    print(f"[configure-discovery] ERROR: Auto-discovered devices not healthy/polled: {unpolled}", file=sys.stderr)
    sys.exit(1)

print("[configure-discovery] OK: All expected edge devices were auto-discovered, named by IP, and polled.")
PY
