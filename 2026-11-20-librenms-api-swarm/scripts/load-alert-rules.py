#!/usr/bin/env python3
"""Load NetOps alert rules pack into LibreNMS via REST API v0 from fixtures/alert-rules.json."""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = os.environ.get("LIBRENMS_URL", "http://127.0.0.1:8012").rstrip("/")
TOKEN_FILE = os.environ.get("LIBRENMS_TOKEN_FILE", "/tmp/librenms-api.token")
REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_PATH = REPO_ROOT / "fixtures" / "alert-rules.json"


def load_token() -> str:
    token = os.environ.get("LIBRENMS_API_TOKEN", "").strip()
    if token:
        return token
    token_path = Path(TOKEN_FILE)
    if token_path.exists():
        token = token_path.read_text(encoding="utf-8").strip()
    if not token:
        raise RuntimeError(
            f"API token not found in LIBRENMS_API_TOKEN or {TOKEN_FILE}. "
            "Run scripts/bootstrap-auth.sh first."
        )
    return token


def api_request(method: str, path: str, token: str, payload: dict | None = None) -> tuple[int, dict]:
    url = f"{BASE_URL}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {
        "X-Auth-Token": token,
        "Accept": "application/json",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"raw": body}
        return exc.code, parsed


def main() -> int:
    token = load_token()
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    endpoint = fixture.get("endpoint", "/api/v0/rules")
    rules = fixture["rules"]

    print(f"[load-alert-rules] Target: {BASE_URL}{endpoint} (auth=<REDACTED_TOKEN>)")

    status, existing_resp = api_request("GET", endpoint, token)
    if status != 200 or existing_resp.get("status") != "ok":
        print(f"[load-alert-rules] ERROR: GET {endpoint} failed: HTTP {status} - {existing_resp}", file=sys.stderr)
        return 1

    existing_names = {r.get("name") for r in existing_resp.get("rules", [])}
    print(f"[load-alert-rules] Loading {len(rules)} alert rules from {FIXTURE_PATH.name}...")

    for rule in rules:
        name = rule["name"]
        if name in existing_names:
            print(f"  = Already exists: {name}")
            continue
        status, resp = api_request("POST", endpoint, token, rule)
        if status in (200, 201) and resp.get("status") == "ok":
            print(f"  + Created rule '{name}': HTTP {status} - {resp.get('message', 'ok')}")
        else:
            print(f"  ! Failed rule '{name}': HTTP {status} - {resp}", file=sys.stderr)
            return 1

    status, verify_resp = api_request("GET", endpoint, token)
    if status != 200 or verify_resp.get("status") != "ok":
        print(f"[load-alert-rules] ERROR: GET {endpoint} verify failed: HTTP {status} - {verify_resp}", file=sys.stderr)
        return 1

    returned = verify_resp.get("rules", [])
    returned_names = {r.get("name") for r in returned}
    print(f"\n[load-alert-rules] Verified GET {endpoint} ({len(returned)} total rule(s)):")
    for r in returned:
        print(
            f"  - id={r.get('id')} name={r.get('name')!r} "
            f"severity={r.get('severity')} disabled={r.get('disabled')}"
        )

    missing = [r["name"] for r in rules if r["name"] not in returned_names]
    if missing:
        print(f"[load-alert-rules] ERROR: Missing expected rules: {missing}", file=sys.stderr)
        return 1

    print("[load-alert-rules] OK: All fixture alert rules verified via GET /api/v0/rules.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
