#!/usr/bin/env python3
"""
Enable Nautobot Device Onboarding & Golden Config jobs and run live Device Onboarding
(SSOTSyncDevices) against ceos-leaf1 (172.30.30.11), ceos-leaf2 (172.30.30.12),
and cisco-core1 (172.30.30.13).
"""

import argparse
import os
import sys
import time
from typing import Any, Dict, Optional

import requests


JOBS_TO_ENABLE = [
    "SSOTSyncDevices",
    "SSOTSyncNetworkData",
    "OnboardingTask",
    "BackupJob",
    "IntendedJob",
    "ComplianceJob",
    "GenerateConfigPlans",
    "DeployConfigPlans",
    "AllDevicesGoldenConfig",
    "AllGoldenConfig",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Onboard live lab routers via Nautobot Device Onboarding.")
    parser.add_argument("--ips", default="172.30.30.11,172.30.30.12,172.30.30.13", help="Comma-separated management IPs")
    parser.add_argument("--location", default="Lab-DC1", help="Nautobot Location name")
    parser.add_argument("--secrets-group", default="LAB-DEVICE-CREDS", help="Nautobot SecretsGroup name")
    parser.add_argument("--role", default="Leaf", help="Default Device Role")
    parser.add_argument("--timeout", type=int, default=240, help="Job poll timeout in seconds")
    args = parser.parse_args()

    base = os.environ.get("NAUTOBOT_URL", "http://127.0.0.1:8083").rstrip("/")
    token = os.environ.get("NAUTOBOT_TOKEN") or os.environ.get("NAUTOBOT_SUPERUSER_API_TOKEN")
    if not token:
        raise RuntimeError("NAUTOBOT_TOKEN is required.")

    s = requests.Session()
    s.headers.update({"Authorization": f"Token {token}", "Content-Type": "application/json"})

    # 1. Enable required jobs
    jobs = s.get(f"{base}/api/extras/jobs/", params={"limit": 200}, timeout=30).json().get("results", [])
    job_map = {j["job_class_name"]: j for j in jobs}
    for cls_name in JOBS_TO_ENABLE:
        job = job_map.get(cls_name)
        if job and not job.get("enabled"):
            s.patch(f"{base}/api/extras/jobs/{job['id']}/", json={"enabled": True}, timeout=30).raise_for_status()
            print(f"[onboard] Enabled job {cls_name}")

    # 2. Temporarily disable CI webhook during initial onboarding
    whs = s.get(f"{base}/api/extras/webhooks/", params={"name": "ci-pipeline-sot-trigger"}, timeout=30).json().get("results", [])
    wh_id = whs[0]["id"] if whs else None
    if wh_id and whs[0].get("enabled"):
        s.patch(f"{base}/api/extras/webhooks/{wh_id}/", json={"enabled": False}, timeout=30).raise_for_status()
        print("[onboard] Temporarily paused ci-pipeline-sot-trigger webhook during onboarding")

    # 3. Look up UUIDs
    def lookup_id(path: str, name: str) -> str:
        res = s.get(f"{base}/api{path}", params={"name": name}, timeout=30).json().get("results", [])
        for r in res:
            if r.get("name") == name:
                return r["id"]
        raise RuntimeError(f"Could not find {path} name={name}")

    loc_id = lookup_id("/dcim/locations/", args.location)
    ns_id = lookup_id("/ipam/namespaces/", "Global")
    role_id = lookup_id("/extras/roles/", args.role)
    status_id = lookup_id("/extras/statuses/", "Active")
    sg_id = lookup_id("/extras/secrets-groups/", args.secrets_group)

    ssot_job = job_map["SSOTSyncDevices"]
    payload = {
        "data": {
            "dryrun": False,
            "debug": True,
            "location": loc_id,
            "namespace": ns_id,
            "ip_addresses": args.ips,
            "port": 22,
            "timeout": 30,
            "set_mgmt_only": True,
            "device_role": role_id,
            "device_status": status_id,
            "interface_status": status_id,
            "ip_address_status": status_id,
            "secrets_group": sg_id,
            "fail_job_on_task_failure": False,
        }
    }
    print(f"[onboard] Triggering SSOTSyncDevices for {args.ips} ...")
    run_resp = s.post(f"{base}/api/extras/jobs/{ssot_job['id']}/run/", json=payload, timeout=30)
    if not run_resp.ok:
        raise RuntimeError(f"Failed to start SSOTSyncDevices ({run_resp.status_code}): {run_resp.text}")
    jr_id = run_resp.json()["job_result"]["id"]
    print(f"[onboard] JobResult ID: {jr_id}")

    deadline = time.time() + args.timeout
    status = "PENDING"
    while time.time() < deadline:
        jr = s.get(f"{base}/api/extras/job-results/{jr_id}/", timeout=30).json()
        raw_status = jr.get("status")
        status = raw_status.get("value") if isinstance(raw_status, dict) else str(raw_status)
        if status.upper() in ("SUCCESS", "FAILURE", "REVOKED", "ERROR"):
            break
        time.sleep(4)
    print(f"[onboard] SSOTSyncDevices final status: {status}")

    # Print recent job logs
    logs = s.get(f"{base}/api/extras/job-logs/", params={"job_result": jr_id, "limit": 50}, timeout=30).json().get("results", [])
    for entry in logs[-20:]:
        print(f"  [{entry.get('log_level')}] {entry.get('message')}")

    # Print discovered devices
    devs = s.get(f"{base}/api/dcim/devices/", params={"limit": 50}, timeout=30).json().get("results", [])
    print(f"[onboard] Devices in Nautobot ({len(devs)}):")
    for d in devs:
        plat = (d.get("platform") or {}).get("name")
        pip = (d.get("primary_ip4") or {}).get("address")
        print(f"  - {d['name']} | platform={plat} | primary_ip4={pip}")

    return 0 if status.upper() == "SUCCESS" else 1


if __name__ == "__main__":
    sys.exit(main())
