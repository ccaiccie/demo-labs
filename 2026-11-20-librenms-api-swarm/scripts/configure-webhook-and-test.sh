#!/usr/bin/env bash
set -euo pipefail

CONTAINER="${LIBRENMS_CONTAINER:-librenms-api-web}"
WEBHOOK_CONTAINER="${WEBHOOK_CONTAINER:-librenms-api-webhook}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
FIXTURE="${REPO_ROOT}/fixtures/alert-transport.json"

echo "[configure-webhook] Provisioning alert transport and alert operation from ${FIXTURE}..."
FIXTURE_JSON="$(python3 -c 'import json,sys; print(json.dumps(json.load(open(sys.argv[1]))))' "${FIXTURE}")"

PROVISION_OUT="$(docker exec -u librenms "${CONTAINER}" php -r '
require "/opt/librenms/vendor/autoload.php";
$app = require "/opt/librenms/bootstrap/app.php";
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();

use Illuminate\Support\Facades\DB;

$fixture = json_decode($argv[1], true, 512, JSON_THROW_ON_ERROR);
$data = $fixture["transport"];
$transport = App\Models\AlertTransport::where("transport_name", $data["transport_name"])->first();
if (!$transport) {
    $transport = new App\Models\AlertTransport();
}
$transport->transport_name = $data["transport_name"];
$transport->transport_type = $data["transport_type"];
$transport->is_default = !empty($data["is_default"]) ? 1 : 0;
$transport->transport_config = $data["transport_config"];
$transport->save();

$opCfg = $fixture["operation"] ?? [
    "name" => "Lab Local Webhook Operation",
    "default_operation_step_duration_seconds" => 300,
    "segments" => [
        [
            "position" => 0,
            "operation_phase" => "problem",
            "escalation_step_from" => 1,
            "escalation_step_to" => 1,
            "start_in_seconds" => 0,
            "step_duration_seconds" => 300,
        ],
        [
            "position" => 0,
            "operation_phase" => "recovery",
            "escalation_step_from" => 1,
            "escalation_step_to" => 1,
            "start_in_seconds" => 0,
            "step_duration_seconds" => 300,
        ],
    ],
];

$opName = $opCfg["name"];
$defaultStepSec = (int) ($opCfg["default_operation_step_duration_seconds"] ?? 300);
$op = DB::table("alert_operations")->where("name", $opName)->first();
if ($op) {
    $opId = (int) $op->id;
    DB::table("alert_operations")->where("id", $opId)->update([
        "default_operation_step_duration_seconds" => $defaultStepSec,
    ]);
} else {
    $opId = (int) DB::table("alert_operations")->insertGetId([
        "name" => $opName,
        "default_operation_step_duration_seconds" => $defaultStepSec,
    ]);
}

$segmentSummary = [];
foreach ($opCfg["segments"] as $segCfg) {
    $phase = $segCfg["operation_phase"];
    $fields = [
        "position" => (int) ($segCfg["position"] ?? 0),
        "escalation_step_from" => (int) ($segCfg["escalation_step_from"] ?? 1),
        "escalation_step_to" => $segCfg["escalation_step_to"] === null ? null : (int) $segCfg["escalation_step_to"],
        "start_in_seconds" => (int) ($segCfg["start_in_seconds"] ?? 0),
        "step_duration_seconds" => (int) ($segCfg["step_duration_seconds"] ?? $defaultStepSec),
    ];

    $segment = DB::table("alert_operation_segments")
        ->where("alert_operation_id", $opId)
        ->where("operation_phase", $phase)
        ->first();
    if ($segment) {
        $segmentId = (int) $segment->id;
        DB::table("alert_operation_segments")->where("id", $segmentId)->update($fields);
    } else {
        $segmentId = (int) DB::table("alert_operation_segments")->insertGetId(array_merge([
            "alert_operation_id" => $opId,
            "operation_phase" => $phase,
        ], $fields));
    }

    $mapExists = DB::table("alert_operation_transport_map")
        ->where("segment_id", $segmentId)
        ->where("transport_or_group_id", $transport->transport_id)
        ->where("target_type", "single")
        ->exists();
    if (!$mapExists) {
        DB::table("alert_operation_transport_map")->insert([
            "segment_id" => $segmentId,
            "transport_or_group_id" => $transport->transport_id,
            "target_type" => "single",
        ]);
    }
    $toVal = $fields["escalation_step_to"] === null ? "inf" : (string) $fields["escalation_step_to"];
    $segmentSummary[] = "{$phase}:id={$segmentId}(steps={$fields["escalation_step_from"]}..{$toVal})";
}

$updated = DB::table("alert_rules")
    ->where("name", "like", "Lab:%")
    ->update(["alert_operation_id" => $opId]);

echo "transport_id={$transport->transport_id} operation_id={$opId} segments=" . implode(",", $segmentSummary) . " rules_linked={$updated}";
' -- "${FIXTURE_JSON}")"

if [[ -z "${PROVISION_OUT}" ]]; then
  echo "[configure-webhook] ERROR: Failed to provision alert transport/operation." >&2
  exit 1
fi
echo "[configure-webhook] Provisioned 'lab-local-webhook': ${PROVISION_OUT}"

echo "[configure-webhook] Polling 192.0.2.11 to evaluate alert rules, then running alerts.php..."
docker exec -u librenms "${CONTAINER}" lnms device:poll 192.0.2.11 >/dev/null
docker exec -u librenms "${CONTAINER}" php /opt/librenms/alerts.php || true

echo "[configure-webhook] Checking webhook-receiver (/tmp/alerts.jsonl) for delivered alert payloads..."
sleep 2
ALERT_LINES="$(docker exec "${WEBHOOK_CONTAINER}" sh -c 'test -f /tmp/alerts.jsonl && wc -l < /tmp/alerts.jsonl || echo 0' | tr -d '[:space:]')"

if [[ "${ALERT_LINES}" -eq 0 ]]; then
  echo "[configure-webhook] No alerts delivered yet from alerts.php; running LibreNMS test-alert.php..."
  RULE_ID="$(docker exec -u librenms "${CONTAINER}" php -r '
require "/opt/librenms/vendor/autoload.php";
$app = require "/opt/librenms/bootstrap/app.php";
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();
$r = App\Models\AlertRule::where("name", "Lab: Deterministic Webhook Test")->first();
echo $r ? $r->id : "";
' 2>/dev/null || true)"
  if [[ -n "${RULE_ID}" ]]; then
    docker exec -u librenms "${CONTAINER}" php /opt/librenms/scripts/test-alert.php -r "${RULE_ID}" -h 192.0.2.11 -d || true
  fi
  sleep 2
  ALERT_LINES="$(docker exec "${WEBHOOK_CONTAINER}" sh -c 'test -f /tmp/alerts.jsonl && wc -l < /tmp/alerts.jsonl || echo 0' | tr -d '[:space:]')"
fi

if [[ "${ALERT_LINES}" -eq 0 ]]; then
  echo "[configure-webhook] ERROR: webhook-receiver received 0 alert payloads." >&2
  docker logs --tail 30 "${WEBHOOK_CONTAINER}" >&2 || true
  exit 1
fi

echo "[configure-webhook] OK: webhook-receiver captured ${ALERT_LINES} alert payload(s). Latest 3 entries:"
docker exec "${WEBHOOK_CONTAINER}" tail -n 3 /tmp/alerts.jsonl
