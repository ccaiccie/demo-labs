#!/usr/bin/env python3
"""Bulk-add lab devices to LibreNMS via REST API v0 from fixtures/devices.json."""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = os.environ.get("LIBRENMS_URL", "http://127.0.0.1:8012").rstrip("/")
TOKEN_FILE = os.environ.get("LIBRENMS_TOKEN_FILE", "/tmp/librenms-api.token")
REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_PATH = REPO_ROOT / "fixtures" / "devices.json"


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
    endpoint = fixture.get("endpoint", "/api/v0/devices")
    devices = fixture["devices"]

    print(f"[bulk-add-devices] Target: {BASE_URL}{endpoint} (auth=<REDACTED_TOKEN>)")
    print(f"[bulk-add-devices] Loading {len(devices)} devices from {FIXTURE_PATH.name}...")

    for dev in devices:
        hostname = dev["hostname"]
        display = dev.get("display", "")
        status, resp = api_request("POST", endpoint, token, dev)
        msg = resp.get("message", "")
        if status in (200, 201) and resp.get("status") == "ok":
            print(f"  + Added {hostname} ({display}): HTTP {status} - {msg}")
        elif status in (400, 409, 500) and "already exists" in msg.lower():
            print(f"  = Already exists {hostname} ({display}): {msg}")
        else:
            print(f"  ! Failed {hostname} ({display}): HTTP {status} - {resp}", file=sys.stderr)
            return 1

    status, resp = api_request("GET", "/api/v0/devices", token)
    if status != 200 or resp.get("status") != "ok":
        print(f"[bulk-add-devices] ERROR: GET /api/v0/devices failed: HTTP {status} - {resp}", file=sys.stderr)
        return 1

    returned = resp.get("devices", [])
    by_host = {d.get("hostname"): d for d in returned}
    print(f"\n[bulk-add-devices] Verified GET /api/v0/devices ({len(returned)} total device(s)):")
    for d in returned:
        print(
            f"  - id={d.get('device_id')} hostname={d.get('hostname')} "
            f"display={d.get('display')} sysName={d.get('sysName')} "
            f"os={d.get('os')} status={d.get('status')}"
        )

    missing = [dev["hostname"] for dev in devices if dev["hostname"] not in by_host]
    if missing:
        print(f"[bulk-add-devices] ERROR: Missing expected devices: {missing}", file=sys.stderr)
        return 1

    print("[bulk-add-devices] OK: All fixture devices verified via GET /api/v0/devices.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
