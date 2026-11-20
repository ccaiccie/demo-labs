#!/usr/bin/env bash
set -euo pipefail

CONTAINER="${LIBRENMS_CONTAINER:-librenms-api-web}"
BASE_URL="${LIBRENMS_URL:-http://127.0.0.1:8012}"
ADMIN_USER="${LIBRENMS_ADMIN_USER:-labadmin}"
ADMIN_PASS="${LIBRENMS_ADMIN_PASS:-LabAdminPass!2026}"
ADMIN_EMAIL="${LIBRENMS_ADMIN_EMAIL:-labadmin@lab.internal}"
TOKEN_FILE="${LIBRENMS_TOKEN_FILE:-/tmp/librenms-api.token}"
WAIT_TIMEOUT="${WAIT_TIMEOUT:-180}"

echo "[bootstrap-auth] Waiting for ${CONTAINER} and ${BASE_URL} to be ready (timeout=${WAIT_TIMEOUT}s)..."
deadline=$((SECONDS + WAIT_TIMEOUT))
while true; do
  health="$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${CONTAINER}" 2>/dev/null || echo "missing")"
  http_code="$(curl -sS -o /dev/null -w '%{http_code}' "${BASE_URL}/" 2>/dev/null || echo "000")"
  if [[ "${health}" == "healthy" && ( "${http_code}" == "200" || "${http_code}" == "302" ) ]]; then
    echo "[bootstrap-auth] ${CONTAINER} is ${health} and ${BASE_URL}/ returned HTTP ${http_code}."
    break
  fi
  if (( SECONDS >= deadline )); then
    echo "[bootstrap-auth] ERROR: Timed out waiting for ${CONTAINER} (health=${health}, http=${http_code})." >&2
    exit 1
  fi
  sleep 3
done

echo "[bootstrap-auth] Ensuring LibreNMS admin user '${ADMIN_USER}' exists..."
user_exists="$(docker exec -u librenms "${CONTAINER}" php -r '
require "/opt/librenms/vendor/autoload.php";
$app = require "/opt/librenms/bootstrap/app.php";
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();
$u = App\Models\User::where("username", $argv[1])->first();
echo $u ? $u->user_id : "";
' -- "${ADMIN_USER}" 2>/dev/null || true)"

if [[ -z "${user_exists}" ]]; then
  docker exec -u librenms "${CONTAINER}" lnms user:add "${ADMIN_USER}" -p "${ADMIN_PASS}" -r admin -e "${ADMIN_EMAIL}" >/dev/null
  echo "[bootstrap-auth] Created admin user '${ADMIN_USER}'."
else
  echo "[bootstrap-auth] Admin user '${ADMIN_USER}' already exists (user_id=${user_exists})."
fi

echo "[bootstrap-auth] Provisioning Sanctum API token for '${ADMIN_USER}'..."
token=""
if [[ -f "${TOKEN_FILE}" ]]; then
  existing_token="$(cat "${TOKEN_FILE}")"
  if [[ -n "${existing_token}" ]]; then
    check_resp="$(curl -sS -H "X-Auth-Token: ${existing_token}" "${BASE_URL}/api/v0/system" 2>/dev/null || true)"
    if printf '%s' "${check_resp}" | grep -qE '"status"[[:space:]]*:[[:space:]]*"ok"'; then
      token="${existing_token}"
      echo "[bootstrap-auth] Reusing existing valid token from ${TOKEN_FILE} (value=<REDACTED_TOKEN>)."
    fi
  fi
fi

if [[ -z "${token}" ]]; then
  token="$(docker exec -u librenms "${CONTAINER}" php -r '
require "/opt/librenms/vendor/autoload.php";
$app = require "/opt/librenms/bootstrap/app.php";
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();
$user = App\Models\User::where("username", $argv[1])->firstOrFail();
$name = "lab-automation-token";
$user->tokens()->where("name", $name)->delete();
echo $user->createToken($name)->plainTextToken;
' -- "${ADMIN_USER}")"
fi

if [[ -z "${token}" ]]; then
  echo "[bootstrap-auth] ERROR: Failed to obtain API token." >&2
  exit 1
fi

umask 077
printf '%s' "${token}" > "${TOKEN_FILE}"
chmod 600 "${TOKEN_FILE}"

echo "[bootstrap-auth] Verifying API token against ${BASE_URL}/api/v0/system ..."
verify_resp="$(curl -sS -H "X-Auth-Token: ${token}" "${BASE_URL}/api/v0/system")"
if ! printf '%s' "${verify_resp}" | grep -qE '"status"[[:space:]]*:[[:space:]]*"ok"'; then
  echo "[bootstrap-auth] ERROR: API token verification failed: ${verify_resp}" >&2
  exit 1
fi

echo "[bootstrap-auth] OK: Token saved to ${TOKEN_FILE} (value=<REDACTED_TOKEN>) and verified against /api/v0/system."
