#!/usr/bin/env python3
"""End-to-end hands-on verification suite for the Nautobot 3.2.9 NetOps lab.

Covers:
1. /health/ and /api/status/ verification
2. Idempotent seeding via testdata/seed_nautobot.py (2 runs, count comparison)
3. pynautobot REST API reads + live Create/Update/Delete cleanup test
4. Nautobot GraphQL API (/api/graphql/) query with devices, interfaces, IPs,
   custom_fields, and rendered config_context
5. Git Repository Data Source registration & sync + Git-backed Config Context merge
6. Git-synced Nautobot Job (LabInventoryAuditJob) execution in Celery + JobResult logs
7. CLI checks (nautobot-server --version, nautobot-server check, celery inspect ping)
8. Installed Nautobot apps & ecosystem app compatibility check (Golden Config,
   Device Onboarding, SSoT)

Never prints secrets, passwords, or API tokens.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pynautobot
import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
SEED_SCRIPT = REPO_ROOT / "testdata" / "seed_nautobot.py"
DEFAULT_URL = "http://127.0.0.1:8081"
GIT_REPO_NAME = "Lab Git Data Source"
GIT_REPO_SLUG = "lab_git_data_source"
GIT_REPO_URL = "http://git-server:8000/nautobot-lab-repo.git"
GIT_REPO_BRANCH = "main"
TARGET_DEVICE = "core-sw-01.lab.internal"
TARGET_JOB_CLASS = "LabInventoryAuditJob"
SMOKE_TAG_NAME = "smoke-test-temp"
SMOKE_PREFIX = "198.51.100.240/28"  # RFC 5737 TEST-NET-2


def load_env_file(env_path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not env_path.exists():
        return values
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        values[key] = val
    return values


def get_config() -> tuple[str, str]:
    env_file = load_env_file(REPO_ROOT / ".env")
    url = (
        os.environ.get("NAUTOBOT_URL")
        or env_file.get("NAUTOBOT_URL")
        or DEFAULT_URL
    ).rstrip("/")
    token = (
        os.environ.get("NAUTOBOT_TOKEN")
        or os.environ.get("NAUTOBOT_SUPERUSER_API_TOKEN")
        or env_file.get("NAUTOBOT_TOKEN")
        or env_file.get("NAUTOBOT_SUPERUSER_API_TOKEN")
        or ""
    )
    if not token:
        raise RuntimeError(
            "NAUTOBOT_TOKEN / NAUTOBOT_SUPERUSER_API_TOKEN not found in env or .env"
        )
    return url, token


def redact(text: str, secret: str) -> str:
    if secret and secret in text:
        return text.replace(secret, "[REDACTED]")
    return text


def section(title: str) -> None:
    print(f"\n{'=' * 72}")
    print(f"  {title}")
    print(f"{'=' * 72}")


def api_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Token {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def poll_job_result(
    session: requests.Session,
    base_url: str,
    job_result_id: str,
    timeout_s: int = 90,
) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    last_data: dict[str, Any] = {}
    while time.time() < deadline:
        resp = session.get(f"{base_url}/api/extras/job-results/{job_result_id}/", timeout=15)
        resp.raise_for_status()
        last_data = resp.json()
        status = last_data.get("status")
        if isinstance(status, dict):
            status_val = status.get("value") or status.get("label") or ""
        else:
            status_val = str(status or "")
        if status_val.upper() in {"SUCCESS", "FAILURE", "REVOKED"}:
            return last_data
        time.sleep(2)
    raise TimeoutError(
        f"Timed out waiting for JobResult {job_result_id}; last status={last_data.get('status')}"
    )


def test_health_and_status(session: requests.Session, base_url: str) -> dict[str, Any]:
    section("1. Health & /api/status/ Check")
    health_resp = session.get(f"{base_url}/health/", timeout=15)
    assert health_resp.status_code == 200, f"/health/ returned {health_resp.status_code}"
    print(f"GET /health/ -> HTTP {health_resp.status_code}")

    status_resp = session.get(f"{base_url}/api/status/", timeout=15)
    assert status_resp.status_code == 200, f"/api/status/ returned {status_resp.status_code}"
    status = status_resp.json()

    nautobot_ver = status.get("nautobot-version")
    django_ver = status.get("django-version")
    python_ver = status.get("python-version")
    celery_workers = status.get("celery-workers-running")
    installed_apps = status.get("installed-apps", {})
    plugins = status.get("plugins", {})

    print(f"Nautobot version      : {nautobot_ver}")
    print(f"Django version        : {django_ver}")
    print(f"Python version        : {python_ver}")
    print(f"Celery workers running: {celery_workers}")
    print(f"Installed apps count  : {len(installed_apps)}")
    print(f"Installed plugins     : {plugins}")

    assert nautobot_ver, "Missing nautobot-version in /api/status/"
    assert isinstance(celery_workers, int) and celery_workers >= 1, (
        f"Expected >=1 Celery worker running, got {celery_workers}"
    )
    return status


def collect_inventory_counts(nb: Any) -> dict[str, int]:
    endpoints = {
        "location_types": nb.dcim.location_types,
        "locations": nb.dcim.locations,
        "manufacturers": nb.dcim.manufacturers,
        "platforms": nb.dcim.platforms,
        "device_types": nb.dcim.device_types,
        "devices": nb.dcim.devices,
        "interfaces": nb.dcim.interfaces,
        "prefixes": nb.ipam.prefixes,
        "ip_addresses": nb.ipam.ip_addresses,
        "vlans": nb.ipam.vlans,
        "providers": nb.circuits.providers,
        "circuit_types": nb.circuits.circuit_types,
        "circuits": nb.circuits.circuits,
        "statuses": nb.extras.statuses,
        "roles": nb.extras.roles,
        "tags": nb.extras.tags,
        "custom_fields": nb.extras.custom_fields,
        "config_contexts": nb.extras.config_contexts,
    }
    return {name: ep.count() for name, ep in endpoints.items()}


def test_idempotent_seeding(base_url: str, token: str, nb: Any) -> dict[str, int]:
    section("2. Idempotent Seeding (testdata/seed_nautobot.py)")
    assert SEED_SCRIPT.exists(), f"Seed script not found: {SEED_SCRIPT}"

    env = os.environ.copy()
    env["NAUTOBOT_URL"] = base_url
    env["NAUTOBOT_TOKEN"] = token

    for run_num in (1, 2):
        print(f"\n--- Seed Run #{run_num} ---")
        proc = subprocess.run(
            [sys.executable, str(SEED_SCRIPT)],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
        )
        stdout_clean = redact(proc.stdout.strip(), token)
        stderr_clean = redact(proc.stderr.strip(), token)
        if stdout_clean:
            print(stdout_clean)
        if stderr_clean:
            print(f"[stderr]\n{stderr_clean}")
        assert proc.returncode == 0, f"seed_nautobot.py run #{run_num} exited {proc.returncode}"

        counts = collect_inventory_counts(nb)
        if run_num == 1:
            counts_run1 = counts
        else:
            counts_run2 = counts

    assert counts_run1 == counts_run2, (
        f"Seeding is NOT idempotent!\nRun 1: {counts_run1}\nRun 2: {counts_run2}"
    )
    print("\nIdempotency verified: object counts identical across Run #1 and Run #2.")
    return counts_run2


def test_pynautobot_rest_and_crud(nb: Any) -> dict[str, int]:
    section("3. pynautobot REST API Reads & Live CRUD Smoke Test")
    counts = collect_inventory_counts(nb)
    for k, v in counts.items():
        print(f"  {k:<18}: {v}")

    assert counts["locations"] >= 3, "Expected >=3 locations"
    assert counts["devices"] >= 4, "Expected >=4 devices"
    assert counts["interfaces"] >= 4, "Expected >=4 interfaces"
    assert counts["prefixes"] >= 3, "Expected >=3 prefixes"
    assert counts["ip_addresses"] >= 4, "Expected >=4 IP addresses"
    assert counts["vlans"] >= 3, "Expected >=3 VLANs"
    assert counts["circuits"] >= 1, "Expected >=1 circuit"
    assert counts["custom_fields"] >= 3, "Expected >=3 custom fields"

    # Sample read verification
    devices = list(nb.dcim.devices.all())
    print("\nSample devices via pynautobot:")
    for dev in devices:
        ip_str = str(dev.primary_ip4) if dev.primary_ip4 else "None"
        print(f"  - {dev.name} | role={dev.role} | location={dev.location} | primary_ip4={ip_str}")

    # Clean up any leftover smoke-test objects first
    existing_tag = nb.extras.tags.get(name=SMOKE_TAG_NAME)
    if existing_tag:
        existing_tag.delete()
    existing_prefix = nb.ipam.prefixes.get(prefix=SMOKE_PREFIX)
    if existing_prefix:
        existing_prefix.delete()

    created_tag = None
    created_prefix = None
    try:
        # 1) Create Tag
        created_tag = nb.extras.tags.create(
            name=SMOKE_TAG_NAME,
            color="00bcd4",
            description="Temporary pynautobot CRUD smoke test tag",
            content_types=["dcim.device", "ipam.prefix"],
        )
        assert created_tag and created_tag.id, "Failed to create smoke-test tag"
        print(f"\n[CREATE] Tag '{created_tag.name}' (id={created_tag.id})")

        # 2) Update Tag
        created_tag.description = "Updated pynautobot CRUD smoke test tag"
        assert created_tag.save(), "Failed to update smoke-test tag"
        refetched_tag = nb.extras.tags.get(id=created_tag.id)
        assert refetched_tag.description == "Updated pynautobot CRUD smoke test tag"
        print(f"[UPDATE] Tag description verified: '{refetched_tag.description}'")

        # 3) Create RFC 5737 Prefix
        active_status = nb.extras.statuses.get(name="Active")
        global_ns = nb.ipam.namespaces.get(name="Global")
        created_prefix = nb.ipam.prefixes.create(
            prefix=SMOKE_PREFIX,
            namespace=global_ns.id,
            status=active_status.id,
            description="Temporary CRUD test prefix (RFC 5737)",
            tags=[created_tag.id],
        )
        assert created_prefix and created_prefix.id, "Failed to create smoke-test prefix"
        print(f"[CREATE] Prefix '{created_prefix.prefix}' (id={created_prefix.id})")

        # 4) Update Prefix
        created_prefix.description = "Updated CRUD test prefix (RFC 5737)"
        assert created_prefix.save(), "Failed to update smoke-test prefix"
        refetched_prefix = nb.ipam.prefixes.get(id=created_prefix.id)
        assert refetched_prefix.description == "Updated CRUD test prefix (RFC 5737)"
        print(f"[UPDATE] Prefix description verified: '{refetched_prefix.description}'")
    finally:
        if created_prefix:
            assert created_prefix.delete(), "Failed to delete smoke-test prefix"
            print(f"[DELETE] Prefix '{SMOKE_PREFIX}' cleaned up")
        if created_tag:
            assert created_tag.delete(), "Failed to delete smoke-test tag"
            print(f"[DELETE] Tag '{SMOKE_TAG_NAME}' cleaned up")

    assert nb.extras.tags.get(name=SMOKE_TAG_NAME) is None
    assert nb.ipam.prefixes.get(prefix=SMOKE_PREFIX) is None
    print("Live CRUD create/update/delete verified cleanly.")
    return counts


def test_graphql_api(session: requests.Session, base_url: str, label: str = "4. GraphQL API Query") -> dict[str, Any]:
    section(label)
    query = """
    query LabDevices {
      devices {
        name
        status { name }
        role { name }
        device_type {
          model
          manufacturer { name }
        }
        platform { name }
        location {
          name
          parent { name }
        }
        primary_ip4 { address }
        interfaces {
          name
          type
          ip_addresses { address }
        }
        tags { name }
        _custom_field_data
        cf_asset_tag
        cf_maintenance_window
        config_context
      }
    }
    """
    resp = session.post(f"{base_url}/api/graphql/", json={"query": query}, timeout=20)
    assert resp.status_code == 200, f"GraphQL HTTP {resp.status_code}: {resp.text[:300]}"
    payload = resp.json()
    assert "errors" not in payload or not payload["errors"], f"GraphQL errors: {payload.get('errors')}"
    devices = payload.get("data", {}).get("devices", [])
    assert len(devices) >= 4, f"Expected >=4 devices from GraphQL, got {len(devices)}"

    print(json.dumps(payload, indent=2))
    return payload


def test_git_repo_sync_and_config_context(
    session: requests.Session, base_url: str
) -> dict[str, Any]:
    section("5. Git Repository Data Source Sync & Config Context Merge")
    repos_resp = session.get(
        f"{base_url}/api/extras/git-repositories/",
        params={"slug": GIT_REPO_SLUG},
        timeout=15,
    )
    repos_resp.raise_for_status()
    results = repos_resp.json().get("results", [])

    if results:
        repo = results[0]
        repo_id = repo["id"]
        print(f"Found existing GitRepository '{repo['name']}' (id={repo_id}); updating settings...")
        patch_resp = session.patch(
            f"{base_url}/api/extras/git-repositories/{repo_id}/",
            json={
                "remote_url": GIT_REPO_URL,
                "branch": GIT_REPO_BRANCH,
                "provided_contents": ["extras.configcontext", "extras.job"],
            },
            timeout=15,
        )
        patch_resp.raise_for_status()
        repo = patch_resp.json()
    else:
        print(f"Registering GitRepository '{GIT_REPO_NAME}' -> {GIT_REPO_URL} (branch={GIT_REPO_BRANCH})")
        create_resp = session.post(
            f"{base_url}/api/extras/git-repositories/",
            json={
                "name": GIT_REPO_NAME,
                "slug": GIT_REPO_SLUG,
                "remote_url": GIT_REPO_URL,
                "branch": GIT_REPO_BRANCH,
                "provided_contents": ["extras.configcontext", "extras.job"],
            },
            timeout=30,
        )
        assert create_resp.status_code in (200, 201), (
            f"GitRepository create failed ({create_resp.status_code}): {create_resp.text}"
        )
        repo = create_resp.json()
        repo_id = repo["id"]
        print(f"Created GitRepository id={repo_id}")

    # Trigger explicit sync
    sync_resp = session.post(
        f"{base_url}/api/extras/git-repositories/{repo_id}/sync/",
        json={},
        timeout=30,
    )
    assert sync_resp.status_code in (200, 201, 202), (
        f"Git sync failed ({sync_resp.status_code}): {sync_resp.text}"
    )
    sync_data = sync_resp.json()
    job_result_obj = sync_data.get("job_result") or {}
    job_result_id = job_result_obj.get("id") if isinstance(job_result_obj, dict) else job_result_obj
    assert job_result_id, f"No job_result ID returned from sync: {sync_data}"
    print(f"Triggered Git sync -> JobResult id={job_result_id}")

    result = poll_job_result(session, base_url, job_result_id, timeout_s=90)
    status_val = (
        result["status"].get("value") if isinstance(result.get("status"), dict) else result.get("status")
    )
    print(f"Git sync JobResult status: {status_val}")

    logs_resp = session.get(
        f"{base_url}/api/extras/job-logs/",
        params={"job_result": job_result_id, "limit": 100},
        timeout=15,
    )
    logs_resp.raise_for_status()
    for entry in logs_resp.json().get("results", []):
        print(f"  [{entry.get('log_level', 'info').upper()}] {entry.get('message', '')}")

    assert str(status_val).upper() == "SUCCESS", f"Git sync did not succeed: {result}"

    # Verify merged config_context on core-sw-01.lab.internal
    dev_resp = session.get(
        f"{base_url}/api/dcim/devices/",
        params={"name": TARGET_DEVICE, "include": "config_context"},
        timeout=15,
    )
    dev_resp.raise_for_status()
    dev_results = dev_resp.json().get("results", [])
    assert dev_results, f"Device {TARGET_DEVICE} not found"
    dev_id = dev_results[0]["id"]

    # Fetch device detail with config_context
    detail_resp = session.get(
        f"{base_url}/api/dcim/devices/{dev_id}/",
        params={"include": "config_context"},
        timeout=15,
    )
    detail_resp.raise_for_status()
    detail = detail_resp.json()
    rendered_ctx = detail.get("config_context") or {}
    print(f"\nRendered config_context for {TARGET_DEVICE}:")
    print(json.dumps(rendered_ctx, indent=2))

    # Expect both global base services (e.g., ntp/dns/syslog) AND Git-backed BGP context
    ctx_str = json.dumps(rendered_ctx).lower()
    assert "bgp" in ctx_str or "65001" in ctx_str, (
        f"Expected Git-backed BGP config context (dc_west_bgp.json) merged onto {TARGET_DEVICE}, "
        f"got: {rendered_ctx}"
    )
    assert "ntp" in ctx_str or "192.0.2" in ctx_str, (
        f"Expected global lab-base-services merged onto {TARGET_DEVICE}, got: {rendered_ctx}"
    )
    print(f"Verified global + Git-backed Config Context merge on {TARGET_DEVICE}!")
    return {"repo_id": repo_id, "sync_job_result_id": job_result_id, "config_context": rendered_ctx}


def test_git_synced_job(session: requests.Session, base_url: str) -> dict[str, Any]:
    section(f"6. Git-Synced Nautobot Job Execution ({TARGET_JOB_CLASS})")
    jobs_resp = session.get(
        f"{base_url}/api/extras/jobs/",
        params={"limit": 200},
        timeout=15,
    )
    jobs_resp.raise_for_status()
    all_jobs = jobs_resp.json().get("results", [])

    target_job = None
    for job in all_jobs:
        if (
            job.get("job_class_name") == TARGET_JOB_CLASS
            or TARGET_JOB_CLASS in str(job.get("name", ""))
            or "lab_inventory_audit" in str(job.get("module_name", ""))
        ):
            target_job = job
            break

    assert target_job is not None, (
        f"Could not find Git-synced job {TARGET_JOB_CLASS}. "
        f"Available jobs: {[j.get('job_class_name') for j in all_jobs]}"
    )
    job_id = target_job["id"]
    print(
        f"Found Job: name='{target_job.get('name')}' class='{target_job.get('job_class_name')}' "
        f"module='{target_job.get('module_name')}' enabled={target_job.get('enabled')}"
    )

    if not target_job.get("enabled"):
        patch_resp = session.patch(
            f"{base_url}/api/extras/jobs/{job_id}/",
            json={"enabled": True},
            timeout=15,
        )
        patch_resp.raise_for_status()
        print(f"Enabled Job id={job_id}")

    run_resp = session.post(
        f"{base_url}/api/extras/jobs/{job_id}/run/",
        json={"data": {}},
        timeout=30,
    )
    assert run_resp.status_code in (200, 201, 202), (
        f"Job run failed ({run_resp.status_code}): {run_resp.text}"
    )
    run_data = run_resp.json()
    job_result_obj = run_data.get("job_result") or run_data
    job_result_id = job_result_obj.get("id") if isinstance(job_result_obj, dict) else job_result_obj
    assert job_result_id, f"No job_result ID returned from job run: {run_data}"
    print(f"Queued Job in Celery -> JobResult id={job_result_id}")

    result = poll_job_result(session, base_url, job_result_id, timeout_s=90)
    status_val = (
        result["status"].get("value") if isinstance(result.get("status"), dict) else result.get("status")
    )
    print(f"JobResult status: {status_val}")

    logs_resp = session.get(
        f"{base_url}/api/extras/job-logs/",
        params={"job_result": job_result_id, "limit": 200},
        timeout=15,
    )
    logs_resp.raise_for_status()
    logs = logs_resp.json().get("results", [])
    print(f"JobResult log entries ({len(logs)}):")
    for entry in logs:
        lvl = str(entry.get("log_level", "info")).upper()
        msg = entry.get("message", "")
        print(f"  [{lvl}] {msg}")

    assert str(status_val).upper() == "SUCCESS", f"Job {TARGET_JOB_CLASS} failed: {result}"
    assert len(logs) >= 1, "Expected at least 1 log entry from LabInventoryAuditJob"
    return {"job_id": job_id, "job_result_id": job_result_id, "status": status_val, "log_count": len(logs)}


def run_wsl_docker_cmd(cmd: str) -> tuple[int, str]:
    wsl_path = "/mnt/c/Users/superuser/ag-lab/nautobot-demo-1121"
    full_cmd = ["wsl", "-e", "bash", "-lc", f"cd {wsl_path} && {cmd}"]
    proc = subprocess.run(full_cmd, capture_output=True, text=True, timeout=60)
    output = (proc.stdout + "\n" + proc.stderr).strip()
    return proc.returncode, output


def test_cli_checks(token: str) -> None:
    section("7. Nautobot CLI & Celery Health Checks")
    checks = [
        ("nautobot-server --version", "docker compose exec -T nautobot nautobot-server --version"),
        ("nautobot-server check", "docker compose exec -T nautobot nautobot-server check"),
        (
            "celery inspect ping",
            "docker compose exec -T celery_worker nautobot-server celery inspect ping",
        ),
    ]
    for label, cmd in checks:
        rc, out = run_wsl_docker_cmd(cmd)
        clean_out = redact(out, token)
        print(f"\n$ {cmd}\n{clean_out}")
        assert rc == 0, f"CLI check '{label}' failed with exit code {rc}"


def test_app_compatibility(status: dict[str, Any]) -> None:
    section("8. Installed Nautobot Apps & Ecosystem Compatibility Check")
    plugins = status.get("plugins", {})
    nautobot_ver = status.get("nautobot-version", "unknown")
    print(f"Running Nautobot version : {nautobot_ver}")
    print(f"Active plugins in image  : {plugins if plugins else 'None (pure official image)'}")

    ecosystem_apps = [
        "nautobot-golden-config",
        "nautobot-device-onboarding",
        "nautobot-ssot",
    ]
    print("\nPyPI latest release compatibility metadata vs Nautobot 3.2.9:")
    for pkg in ecosystem_apps:
        try:
            r = requests.get(f"https://pypi.org/pypi/{pkg}/json", timeout=10)
            if r.status_code == 200:
                info = r.json().get("info", {})
                ver = info.get("version", "unknown")
                reqs = info.get("requires_dist") or []
                nb_req = [x for x in reqs if x.lower().startswith("nautobot") and "extra ==" not in x]
                req_str = nb_req[0] if nb_req else "unspecified"
                print(f"  - {pkg}: latest={ver} | requirement='{req_str}'")
            else:
                print(f"  - {pkg}: PyPI HTTP {r.status_code}")
        except Exception as exc:
            print(f"  - {pkg}: unable to query PyPI ({exc})")


def main() -> int:
    base_url, token = get_config()
    print(f"Target Nautobot URL: {base_url}")

    session = requests.Session()
    session.headers.update(api_headers(token))
    nb = pynautobot.api(url=base_url, token=token)

    status = test_health_and_status(session, base_url)
    test_idempotent_seeding(base_url, token, nb)
    test_pynautobot_rest_and_crud(nb)
    test_git_repo_sync_and_config_context(session, base_url)
    test_graphql_api(session, base_url, label="4/5b. GraphQL API Query (post-Git Config Context merge)")
    test_git_synced_job(session, base_url)
    test_cli_checks(token)
    test_app_compatibility(status)

    section("ALL HANDS-ON TESTS PASSED")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as exc:
        print(f"\n[FAIL] Assertion failed: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"\n[ERROR] {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
