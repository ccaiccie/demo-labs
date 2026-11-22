#!/usr/bin/env python3
"""Clean, reusable Golden Config job trigger & baseline helper for Nautobot 3.2.x.

Usage:
  python3 scripts/trigger_golden_config.py --enable-jobs
  python3 scripts/trigger_golden_config.py --backup-compliance
  python3 scripts/trigger_golden_config.py --remediate
  python3 scripts/trigger_golden_config.py --find-baseline
  python3 scripts/trigger_golden_config.py --status
"""
import argparse
import base64
import os
import sys
import time
import requests

NAUTOBOT_URL = os.environ.get("NAUTOBOT_URL", "http://nautobot:8080").rstrip("/")
GITEA_URL = os.environ.get("GITEA_URL", "http://gitea:3000").rstrip("/")
TOKEN = os.environ.get("NAUTOBOT_TOKEN") or os.environ.get("NAUTOBOT_SUPERUSER_API_TOKEN", "")
GITEA_TOKEN = os.environ.get("GITEA_TOKEN", "")


def nb_headers():
    return {
        "Authorization": f"Token {TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def enable_golden_config_jobs():
    r = requests.get(f"{NAUTOBOT_URL}/api/extras/jobs/?limit=200", headers=nb_headers(), timeout=30)
    r.raise_for_status()
    enabled = []
    for job in r.json().get("results", []):
        mod = job.get("module_name", "")
        name = job.get("name", "")
        if "golden_config" in mod or "Deploy Config Plan" in name or "Config Plan" in name:
            if not job.get("enabled"):
                pr = requests.patch(
                    f"{NAUTOBOT_URL}/api/extras/jobs/{job['id']}/",
                    headers=nb_headers(),
                    json={"enabled": True},
                    timeout=30,
                )
                pr.raise_for_status()
                enabled.append(name)
    print(f"Enabled Golden Config jobs: {enabled or ['(all already enabled)']}")


def run_job(job_class_name: str, data: dict | None = None, timeout_s: int = 240) -> str:
    r = requests.get(f"{NAUTOBOT_URL}/api/extras/jobs/?limit=200", headers=nb_headers(), timeout=30)
    r.raise_for_status()
    matches = [j for j in r.json().get("results", []) if j.get("job_class_name") == job_class_name]
    if not matches:
        raise RuntimeError(f"Nautobot job_class_name={job_class_name} not found")
    job = matches[0]
    if not job.get("enabled"):
        requests.patch(
            f"{NAUTOBOT_URL}/api/extras/jobs/{job['id']}/",
            headers=nb_headers(),
            json={"enabled": True},
            timeout=30,
        ).raise_for_status()

    run_r = requests.post(
        f"{NAUTOBOT_URL}/api/extras/jobs/{job['id']}/run/",
        headers=nb_headers(),
        json={"data": data or {}},
        timeout=30,
    )
    run_r.raise_for_status()
    jr = run_r.json().get("job_result") or run_r.json()
    jid = jr["id"]
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        st_r = requests.get(f"{NAUTOBOT_URL}/api/extras/job-results/{jid}/", headers=nb_headers(), timeout=30)
        st_r.raise_for_status()
        st = st_r.json().get("status")
        val = st.get("value") if isinstance(st, dict) else st
        if val in ("SUCCESS", "FAILURE", "REVOKED"):
            return val
        time.sleep(2)
    return "TIMEOUT"


def print_compliance_summary() -> tuple[int, int]:
    rows = requests.get(
        f"{NAUTOBOT_URL}/api/plugins/golden-config/config-compliance/?limit=200&depth=1",
        headers=nb_headers(),
        timeout=30,
    ).json().get("results", [])
    ok = sum(1 for x in rows if x.get("compliance"))
    total = len(rows)
    print(f"Compliance summary: {ok}/{total} compliant")
    for x in rows:
        if not x.get("compliance"):
            dev = (x.get("device") or {}).get("name") or (x.get("device") or {}).get("display", "unknown")
            rule = (x.get("rule") or {}).get("display", "unknown")
            missing = (x.get("missing") or "").strip().replace("\n", " ; ")
            extra = (x.get("extra") or "").strip().replace("\n", " ; ")
            print(f"  NON-COMPLIANT: {dev} [{rule}]")
            if missing:
                print(f"    missing: {missing}")
            if extra:
                print(f"    extra:   {extra}")
    return ok, total


def do_backup_compliance():
    st_b = run_job("BackupJob")
    print(f"BackupJob: {st_b}", flush=True)
    st_c = run_job("ComplianceJob")
    print(f"ComplianceJob: {st_c}", flush=True)
    ok, total = print_compliance_summary()
    if st_b != "SUCCESS" or st_c != "SUCCESS":
        sys.exit(1)
    return ok, total


def do_remediate(change_id: str):
    enable_golden_config_jobs()
    st_g = run_job(
        "GenerateConfigPlans",
        {"plan_type": "remediation", "change_control_id": change_id},
    )
    print(f"GenerateConfigPlans (remediation): {st_g}", flush=True)

    plans = requests.get(
        f"{NAUTOBOT_URL}/api/plugins/golden-config/config-plan/?status=Not+Approved&limit=50",
        headers=nb_headers(),
        timeout=30,
    ).json().get("results", [])
    pids = []
    for pl in plans:
        if pl.get("change_control_id") == change_id or not change_id:
            pids.append(pl["id"])
            requests.patch(
                f"{NAUTOBOT_URL}/api/plugins/golden-config/config-plan/{pl['id']}/",
                headers=nb_headers(),
                json={"status": "Approved"},
                timeout=30,
            ).raise_for_status()
            dev = (pl.get("device") or {}).get("display", "device")
            print(f"  Approved ConfigPlan for {dev}:")
            for line in (pl.get("config_set") or "").strip().splitlines():
                print(f"    {line}")

    if not pids:
        print("ERROR: No remediation ConfigPlans were generated!", file=sys.stderr)
        sys.exit(1)

    st_d = run_job("DeployConfigPlans", {"config_plan": pids})
    print(f"DeployConfigPlans: {st_d}", flush=True)
    if st_d != "SUCCESS":
        sys.exit(1)

    print("Running post-remediation BackupJob + ComplianceJob...", flush=True)
    ok, total = do_backup_compliance()
    if ok != total:
        sys.exit(1)


def find_true_baseline():
    import subprocess, tempfile
    from pathlib import Path
    gitea_user = os.environ.get("GITEA_ADMIN_USER") or os.environ.get("GITEA_USER", "labadmin")
    gitea_secret = GITEA_TOKEN or os.environ.get("GITEA_ADMIN_PASSWORD", "")
    proto, rest = GITEA_URL.split("://", 1)
    auth_url = f"{proto}://{gitea_user}:{gitea_secret}@{rest}/netops/gc-intended.git"
    with tempfile.TemporaryDirectory(prefix="find-base-") as td:
        rd = Path(td) / "repo"
        subprocess.run(["git", "clone", "--branch", "main", auth_url, str(rd)], check=True, capture_output=True, text=True)
        shas = subprocess.run(["git", "-C", str(rd), "log", "--format=%H", "-n", "40"], check=True, capture_output=True, text=True).stdout.splitlines()
        for sha in shas:
            subprocess.run(["git", "-C", str(rd), "checkout", "-q", sha], check=True)
            cfgs = {f.stem: f.read_text(encoding="utf-8", errors="ignore") for f in rd.rglob("*.cfg")}
            t1 = cfgs.get("ceos-leaf1", "")
            t3 = cfgs.get("cisco-core1", "")
            if t1 and t3 and ("vlan 300" not in t1) and ("Loopback10" not in t3) and ("CI/CD Managed" not in t1):
                print(sha[:10])
                return
    print("ERROR: No pre-change baseline commit found", file=sys.stderr)
    sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--enable-jobs", action="store_true")
    ap.add_argument("--backup-compliance", action="store_true")
    ap.add_argument("--remediate", action="store_true")
    ap.add_argument("--find-baseline", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--change-id", default="DEMO-REMEDIATE-V2")
    args = ap.parse_args()

    if args.find_baseline:
        find_true_baseline()
        return

    if not TOKEN:
        print("ERROR: NAUTOBOT_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    if args.enable_jobs:
        enable_golden_config_jobs()
    if args.backup_compliance:
        do_backup_compliance()
    if args.remediate:
        do_remediate(args.change_id)
    if args.status:
        print_compliance_summary()


if __name__ == "__main__":
    main()
