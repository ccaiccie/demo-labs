#!/usr/bin/env python3
"""
Reproducible End-to-End Test Runner for the Nautobot 3.2.9 CI/CD & Golden Config Lab.

Runs on the lab host (`mydell1`) using Python 3.8+ stdlib only, and delegates
API/SSH/pipeline/remediation/rollback checks into `nautobot-cicd-ci-runner`
(which has network access to `nautobot-cicd-mgmt` 172.30.30.0/24 and all lab env vars).

Tests executed (and saved to evidence/):
  T1: Compose & Containerlab health + 127.0.0.1-only port bindings (`evidence/t1_health_ports.txt`)
  T2: Nautobot 3.2.9 /api/status/ (4 apps), Gitea version, webhook health (`evidence/t2_apps_status.txt`)
  T3: Device Onboarding history + live eBGP Established on all 3 routers (`evidence/t3_onboarding_bgp.txt`)
  T4: Baseline Golden Config Backup + Intended + Compliance = 20/20 (`evidence/t4_baseline_compliance.txt`)
  T5: SoT Change -> Webhook -> CI/CD -> Gitea PR -> Live Deploy -> CLI + 20/20 (`evidence/t5_sot_cicd_deploy.txt`)
  T6: Manual Drift -> Non-Compliant -> Golden Config Remediation Plan -> Deploy -> 20/20 (`evidence/t6_drift_remediation.txt`)
  T7: Rollback via pipeline/rollback.py + SoT revert -> CLI verify + 20/20 (`evidence/t7_rollback.txt`)
  Summary JSON: `evidence/summary.json`
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_DIR = REPO_ROOT / "evidence"
CONTAINER_NAME = "nautobot-cicd-ci-runner"
BASELINE_SHA_FILE = EVIDENCE_DIR / ".baseline_sha"

EXPECTED_APPS = [
    "nautobot_plugin_nornir",
    "nautobot_ssot",
    "nautobot_device_onboarding",
    "nautobot_golden_config",
]

EXPECTED_SERVICES = [
    "nautobot",
    "celery-worker",
    "celery-beat",
    "postgres",
    "redis",
    "gitea",
    "ci-runner",
]

EXPECTED_LOOPBACK_PORTS = [8083, 3002, 2223, 8086]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def redact_secrets(text: str) -> str:
    """Redact any API tokens, passwords, or basic-auth URLs before writing evidence."""
    if not text:
        return text
    out = text
    for env_key in (
        "NAUTOBOT_TOKEN",
        "NAUTOBOT_SUPERUSER_API_TOKEN",
        "GITEA_TOKEN",
        "GITEA_ADMIN_PASSWORD",
        "GITEA_PASSWORD",
        "DEVICE_PASSWORD",
        "DEVICE_ENABLE_SECRET",
        "LAB_DEVICE_PASSWORD",
        "LAB_DEVICE_SECRET",
    ):
        val = os.environ.get(env_key, "").strip()
        if val and len(val) >= 6:
            out = out.replace(val, "<REDACTED>")
    out = re.sub(r"(?i)(Token\s+)[0-9a-f]{24,}", r"\1<REDACTED>", out)
    out = re.sub(r"(https?://[^:@/\s]+:)([^@/\s]+)(@)", r"\1<REDACTED>\3", out)
    return out


def write_evidence(filename: str, content: str) -> Path:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    path = EVIDENCE_DIR / filename
    path.write_text(redact_secrets(content), encoding="utf-8")
    return path


def run_cmd(cmd: List[str], cwd: Optional[Path] = None, timeout: int = 300) -> Tuple[int, str, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout, proc.stderr


# =============================================================================
# Host-side T1 check
# =============================================================================

def run_t1_host() -> Dict[str, Any]:
    lines: List[str] = [
        f"# T1: Lab Health, Containerlab Topology & Port Bindings",
        f"Timestamp: {utc_now()}",
        "",
    ]
    errors: List[str] = []

    rc_ps, out_ps, err_ps = run_cmd(
        ["docker", "compose", "-f", "compose/docker-compose.yml", "ps"],
        cwd=REPO_ROOT,
    )
    lines.append("## docker compose -f compose/docker-compose.yml ps")
    lines.append(out_ps.strip() or err_ps.strip())
    lines.append("")
    if rc_ps != 0:
        errors.append(f"docker compose ps exited {rc_ps}")

    for svc in EXPECTED_SERVICES:
        if not re.search(rf"\b{re.escape(svc)}\b.*\(healthy\)", out_ps):
            errors.append(f"Service {svc} is not healthy in docker compose ps")

    # Verify Postgres and Redis are not published on host
    for internal_svc in ("nautobot-cicd-postgres", "nautobot-cicd-redis"):
        m = re.search(rf"^{re.escape(internal_svc)}.*$", out_ps, re.M)
        if m and "->" in m.group(0):
            errors.append(f"Internal service {internal_svc} has a published host port: {m.group(0)}")

    rc_clab, out_clab, err_clab = run_cmd(
        ["sudo", "-n", "clab", "inspect", "-t", "clab/topology.clab.yml"],
        cwd=REPO_ROOT,
    )
    lines.append("## sudo clab inspect -t clab/topology.clab.yml")
    lines.append((out_clab + "\n" + err_clab).strip())
    lines.append("")
    if rc_clab != 0:
        errors.append(f"clab inspect exited {rc_clab}")
    for router, ip in [
        ("clab-nautobot-cicd-ceos-leaf1", "172.30.30.11"),
        ("clab-nautobot-cicd-ceos-leaf2", "172.30.30.12"),
        ("clab-nautobot-cicd-cisco-core1", "172.30.30.13"),
    ]:
        if router not in out_clab or ip not in out_clab:
            errors.append(f"Missing router {router} ({ip}) in clab inspect")

    rc_ss, out_ss, err_ss = run_cmd(["ss", "-lnt"])
    filtered_ss = [
        ln for ln in out_ss.splitlines()
        if ln.startswith("State") or re.search(r":(8083|3002|2223|8086|5432|6379)\b", ln)
    ]
    lines.append("## ss -lnt (filtered for lab ports 8083, 3002, 2223, 8086, 5432, 6379)")
    lines.append("\n".join(filtered_ss))
    lines.append("")
    if rc_ss != 0:
        errors.append(f"ss -lnt exited {rc_ss}")

    port_bindings: Dict[str, List[str]] = {}
    for port in EXPECTED_LOOPBACK_PORTS:
        matches = [ln for ln in out_ss.splitlines() if re.search(rf":{port}\b", ln)]
        port_bindings[str(port)] = matches
        if not matches:
            errors.append(f"Expected port {port} not listening in ss -lnt")
        for ln in matches:
            cols = ln.split()
            local_addr = cols[3] if len(cols) >= 4 else ln
            if not local_addr.startswith("127.0.0.1:"):
                errors.append(f"Port {port} bound to non-loopback address: {local_addr}")

    passed = len(errors) == 0
    lines.append(f"## Result: {'PASS' if passed else 'FAIL'}")
    if errors:
        lines.append("Errors:")
        for e in errors:
            lines.append(f"  - {e}")

    write_evidence("t1_health_ports.txt", "\n".join(lines) + "\n")
    return {
        "test": "T1",
        "name": "Lab Health & 127.0.0.1 Port Bindings",
        "passed": passed,
        "services_healthy": len(EXPECTED_SERVICES) if passed else None,
        "routers_running": 3 if passed else None,
        "loopback_ports_verified": EXPECTED_LOOPBACK_PORTS,
        "errors": errors,
    }


# =============================================================================
# Container-side helpers (run inside nautobot-cicd-ci-runner)
# =============================================================================

def _nb_session():
    import requests

    token = os.environ["NAUTOBOT_TOKEN"].strip()
    url = os.environ.get("NAUTOBOT_URL", "http://nautobot:8080").rstrip("/")
    sess = requests.Session()
    sess.headers.update({"Authorization": f"Token {token}", "Accept": "application/json"})
    return sess, url


def _gitea_auth() -> Tuple[str, str, str]:
    url = os.environ.get("GITEA_URL", "http://gitea:3000").rstrip("/")
    user = os.environ.get("GITEA_ADMIN_USER", "netops-admin")
    secret = os.environ.get("GITEA_TOKEN") or os.environ.get("GITEA_ADMIN_PASSWORD", "")
    return url, user, secret


def _device_creds() -> Tuple[str, str, str]:
    user = os.environ.get("DEVICE_USERNAME", "admin")
    pw = os.environ["DEVICE_PASSWORD"]
    sec = os.environ.get("DEVICE_ENABLE_SECRET", pw)
    return user, pw, sec


def _netmiko_exec(host: str, device_type: str, commands: List[str], config_cmds: Optional[List[str]] = None) -> Dict[str, str]:
    from netmiko import ConnectHandler

    user, pw, sec = _device_creds()
    params = {
        "device_type": device_type,
        "host": host,
        "username": user,
        "password": pw,
        "secret": sec,
        "timeout": 45,
        "conn_timeout": 30,
    }
    results: Dict[str, str] = {}
    with ConnectHandler(**params) as conn:
        if conn.check_enable_mode() is False:
            conn.enable()
        if config_cmds:
            results["_config_output"] = conn.send_config_set(config_cmds, cmd_verify=False)
            results["_save_output"] = conn.save_config()
        for cmd in commands:
            results[cmd] = conn.send_command(cmd, read_timeout=45)
    return results


def _run_nb_job(sess, nb_url: str, job_class_name: str, data: Optional[Dict[str, Any]] = None, timeout_s: int = 240) -> Dict[str, Any]:
    r = sess.get(f"{nb_url}/api/extras/jobs/", params={"limit": 200}, timeout=30)
    r.raise_for_status()
    jobs = [j for j in r.json().get("results", []) if j.get("job_class_name") == job_class_name]
    if not jobs:
        raise RuntimeError(f"Nautobot job {job_class_name} not found")
    job = jobs[0]
    run_r = sess.post(
        f"{nb_url}/api/extras/jobs/{job['id']}/run/",
        json={"data": data or {}},
        timeout=30,
    )
    run_r.raise_for_status()
    jr = run_r.json().get("job_result") or run_r.json()
    jr_id = jr["id"]

    deadline = time.time() + timeout_s
    final_status = "PENDING"
    while time.time() < deadline:
        st_r = sess.get(f"{nb_url}/api/extras/job-results/{jr_id}/", timeout=30)
        st_r.raise_for_status()
        st = st_r.json().get("status")
        val = st.get("value") if isinstance(st, dict) else st
        if val in ("SUCCESS", "FAILURE", "REVOKED"):
            final_status = val
            break
        time.sleep(2)

    logs_r = sess.get(f"{nb_url}/api/extras/job-logs/", params={"job_result": jr_id, "limit": 200}, timeout=30)
    logs = logs_r.json().get("results", []) if logs_r.ok else []
    return {
        "job": job["name"],
        "job_class": job_class_name,
        "job_result_id": jr_id,
        "status": final_status,
        "logs": [
            f"[{lg.get('log_level')}] {lg.get('grouping')}: {lg.get('message')}"
            for lg in logs
            if lg.get("log_level") in ("info", "warning", "failure", "error", "success")
        ],
    }


def _fetch_compliance(sess, nb_url: str) -> List[Dict[str, Any]]:
    r = sess.get(
        f"{nb_url}/api/plugins/golden-config/config-compliance/",
        params={"limit": 200, "depth": 1},
        timeout=30,
    )
    r.raise_for_status()
    rows: List[Dict[str, Any]] = []
    for row in r.json().get("results", []):
        rule = row.get("rule") or {}
        feat = rule.get("feature") if isinstance(rule, dict) else None
        feat_name = None
        if isinstance(feat, dict):
            feat_name = feat.get("name") or feat.get("display")
        if not feat_name and isinstance(rule, dict):
            disp = rule.get("display") or ""
            feat_name = disp.split(" - ", 1)[-1] if " - " in disp else disp
        rows.append(
            {
                "device": (row.get("device") or {}).get("name") or (row.get("device") or {}).get("display") or "unknown",
                "feature": str(feat_name or "unknown"),
                "compliance": bool(row.get("compliance")),
                "missing": row.get("missing") or "",
                "extra": row.get("extra") or "",
            }
        )
    rows.sort(key=lambda x: (x["device"] or "", x["feature"] or ""))
    return rows


def _format_compliance_table(rows: List[Dict[str, Any]]) -> str:
    compliant = sum(1 for r in rows if r["compliance"])
    out = [f"Compliance Summary: {compliant}/{len(rows)} feature checks compliant"]
    for r in rows:
        status = "COMPLIANT" if r["compliance"] else "NON-COMPLIANT"
        out.append(f"  {r['device']:14s} | {r['feature']:14s} | {status}")
        if not r["compliance"]:
            if r["missing"]:
                out.append(f"    missing: {r['missing'].strip()!r}")
            if r["extra"]:
                out.append(f"    extra:   {r['extra'].strip()!r}")
    return "\n".join(out)


def _wait_webhook_idle(timeout_s: int = 180) -> List[Dict[str, Any]]:
    import requests

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        r = requests.get("http://127.0.0.1:8086/runs", timeout=10)
        r.raise_for_status()
        runs = r.json().get("runs", [])
        if not any(run.get("status") == "running" for run in runs):
            return runs
        time.sleep(2)
    raise TimeoutError("Webhook server did not become idle in time")


# =============================================================================
# Container-side T2..T7
# =============================================================================

def run_t2_container() -> Dict[str, Any]:
    import requests

    sess, nb_url = _nb_session()
    gitea_url, _, _ = _gitea_auth()
    errors: List[str] = []
    lines = [f"# T2: Nautobot 3.2.9 Apps Status, Gitea Version & Webhook Health", f"Timestamp: {utc_now()}", ""]

    nb_status = sess.get(f"{nb_url}/api/status/", timeout=30).json()
    nb_ver = nb_status.get("nautobot-version")
    installed_apps = nb_status.get("installed-apps") or {}
    celery_workers = nb_status.get("celery-workers-running", 0)

    lines.append("## Nautobot /api/status/")
    lines.append(json.dumps(nb_status, indent=2))
    lines.append("")

    if nb_ver != "3.2.9":
        errors.append(f"Expected Nautobot 3.2.9, got {nb_ver}")
    if celery_workers < 1:
        errors.append(f"Expected celery-workers-running >= 1, got {celery_workers}")
    for app in EXPECTED_APPS:
        if app not in installed_apps:
            errors.append(f"Missing expected Nautobot app: {app}")

    gitea_r = requests.get(f"{gitea_url}/api/v1/version", timeout=15)
    gitea_ver = gitea_r.json().get("version") if gitea_r.ok else None
    lines.append("## Gitea /api/v1/version")
    lines.append(f"HTTP {gitea_r.status_code}: {gitea_r.text.strip()}")
    lines.append("")
    if not gitea_r.ok or not gitea_ver:
        errors.append(f"Gitea version check failed: HTTP {gitea_r.status_code}")

    wh_r = requests.get("http://127.0.0.1:8086/health", timeout=10)
    lines.append("## CI Webhook Receiver /health")
    lines.append(f"HTTP {wh_r.status_code}: {wh_r.text.strip()}")
    lines.append("")
    if not wh_r.ok or wh_r.json().get("status") != "ok":
        errors.append(f"Webhook health check failed: {wh_r.text}")

    passed = len(errors) == 0
    lines.append(f"## Result: {'PASS' if passed else 'FAIL'}")
    write_evidence("t2_apps_status.txt", "\n".join(lines) + "\n")
    return {
        "test": "T2",
        "name": "Nautobot 3.2.9 Apps & Gitea Version",
        "passed": passed,
        "nautobot_version": nb_ver,
        "installed_apps": {k: installed_apps.get(k) for k in EXPECTED_APPS},
        "celery_workers_running": celery_workers,
        "gitea_version": gitea_ver,
        "errors": errors,
    }


def run_t3_container() -> Dict[str, Any]:
    sess, nb_url = _nb_session()
    errors: List[str] = []
    lines = [f"# T3: Device Onboarding History & Live eBGP Verification", f"Timestamp: {utc_now()}", ""]

    # 1. Onboarding Job History
    jrs = sess.get(
        f"{nb_url}/api/extras/job-results/",
        params={"name": "Sync Devices From Network", "limit": 5},
        timeout=30,
    ).json().get("results", [])

    lines.append("## Nautobot Device Onboarding (SSOTSyncDevices) Job History")
    if not jrs:
        errors.append("No SSOTSyncDevices job result found")
    else:
        latest = jrs[0]
        st = latest.get("status")
        st_val = st.get("value") if isinstance(st, dict) else st
        lines.append(f"Latest JobResult: id={latest['id']} status={st_val} date_done={latest.get('date_done')}")
        if st_val != "SUCCESS":
            errors.append(f"Latest SSOTSyncDevices status was {st_val}, expected SUCCESS")
        logs = sess.get(
            f"{nb_url}/api/extras/job-logs/",
            params={"job_result": latest["id"], "limit": 200},
            timeout=30,
        ).json().get("results", [])
        info_logs = [
            f"  [{lg.get('log_level')}] {lg.get('grouping')}: {lg.get('message')}"
            for lg in logs
            if lg.get("log_level") in ("info", "warning", "error", "failure", "success")
        ]
        lines.extend(info_logs[:40])
    lines.append("")
    lines.append("Note on cisco-core1 onboarding: vrnetlab NATs management IP 172.30.30.13 to GigabitEthernet1 (10.0.0.15/24),")
    lines.append("so SSOTSyncDevices connects and detects IOS-XE 17.3.8a / CSR1000v, while seed_nautobot.py --include-devices")
    lines.append("registers cisco-core1 cleanly in Nautobot SoT alongside the auto-onboarded ceos-leaf1 and ceos-leaf2.")
    lines.append("")

    # 2. Nautobot Devices inventory
    devs = sess.get(f"{nb_url}/api/dcim/devices/", params={"depth": 1, "limit": 50}, timeout=30).json().get("results", [])
    lines.append("## Nautobot Device Inventory")
    dev_names = []
    for d in sorted(devs, key=lambda x: x["name"]):
        dev_names.append(d["name"])
        ip = (d.get("primary_ip4") or {}).get("address")
        plat = (d.get("platform") or {}).get("name")
        role = (d.get("role") or {}).get("name")
        lines.append(f"  {d['name']:14s} | platform={plat} | role={role} | primary_ip4={ip} | serial={d.get('serial')}")
    for expected_dev in ("ceos-leaf1", "ceos-leaf2", "cisco-core1"):
        if expected_dev not in dev_names:
            errors.append(f"Device {expected_dev} missing from Nautobot inventory")
    lines.append("")

    # 3. Live eBGP Established on all 3 routers
    bgp_targets = [
        ("ceos-leaf1", "172.30.30.11", "arista_eos", "show ip bgp summary", ["198.51.100.1", "198.51.100.5"]),
        ("ceos-leaf2", "172.30.30.12", "arista_eos", "show ip bgp summary", ["198.51.100.3", "198.51.100.4"]),
        ("cisco-core1", "172.30.30.13", "cisco_xe", "show bgp ipv4 unicast summary", ["198.51.100.0", "198.51.100.2"]),
    ]
    bgp_summary: Dict[str, Any] = {}
    lines.append("## Live eBGP Verification")
    for name, host, dtype, cmd, expected_peers in bgp_targets:
        out = _netmiko_exec(host, dtype, [cmd])[cmd]
        lines.append(f"### {name} ({host}) -> `{cmd}`")
        lines.append(out.strip())
        lines.append("")
        peers_up = []
        for peer in expected_peers:
            # Match peer line (cEOS puts Description before Neighbor IP; IOS-XE starts with Neighbor IP)
            m = re.search(rf"^.*\b{re.escape(peer)}\b.*$", out, re.M)
            if not m:
                errors.append(f"{name}: BGP peer {peer} not found")
                continue
            line = m.group(0)
            if re.search(r"\b(Idle|Active|Connect|OpenSent|OpenConfirm)\b", line, re.I):
                errors.append(f"{name}: BGP peer {peer} not Established: {line}")
            else:
                peers_up.append(peer)
        bgp_summary[name] = {"expected_peers": expected_peers, "established_peers": peers_up}

    passed = len(errors) == 0
    lines.append(f"## Result: {'PASS' if passed else 'FAIL'}")
    if errors:
        lines.extend([f"  - {e}" for e in errors])
    write_evidence("t3_onboarding_bgp.txt", "\n".join(lines) + "\n")
    return {
        "test": "T3",
        "name": "Device Onboarding History & Live eBGP",
        "passed": passed,
        "devices_in_nautobot": sorted(dev_names),
        "bgp": bgp_summary,
        "errors": errors,
    }


def run_t4_container() -> Dict[str, Any]:
    sess, nb_url = _nb_session()
    errors: List[str] = []
    lines = [f"# T4: Baseline Golden Config Backup + Intended + Compliance", f"Timestamp: {utc_now()}", ""]

    job_results = []
    for cls in ("BackupJob", "IntendedJob", "ComplianceJob"):
        res = _run_nb_job(sess, nb_url, cls)
        job_results.append({"job": res["job"], "status": res["status"], "job_result_id": res["job_result_id"]})
        lines.append(f"## Job: {res['job']} ({cls}) -> {res['status']}")
        if res["status"] != "SUCCESS":
            errors.append(f"Golden Config {cls} ended with {res['status']}")
        lines.extend(res["logs"][-10:])
        lines.append("")

    rows = _fetch_compliance(sess, nb_url)
    compliant = sum(1 for r in rows if r["compliance"])
    total = len(rows)
    lines.append("## Compliance Matrix")
    lines.append(_format_compliance_table(rows))
    lines.append("")

    if total != 20 or compliant != 20:
        errors.append(f"Expected 20/20 baseline compliance, got {compliant}/{total}")

    passed = len(errors) == 0
    lines.append(f"## Result: {'PASS' if passed else 'FAIL'}")
    write_evidence("t4_baseline_compliance.txt", "\n".join(lines) + "\n")
    return {
        "test": "T4",
        "name": "Baseline Golden Config Compliance",
        "passed": passed,
        "compliant": compliant,
        "total": total,
        "jobs": job_results,
        "errors": errors,
    }


def run_t5_container() -> Dict[str, Any]:
    import requests

    sess, nb_url = _nb_session()
    gitea_url, gitea_user, gitea_secret = _gitea_auth()
    errors: List[str] = []
    lines = [f"# T5: SoT Change -> Webhook -> CI/CD Pipeline -> Gitea PR -> Live Deploy -> Compliance", f"Timestamp: {utc_now()}", ""]

    # Ensure webhook server is idle before starting
    pre_runs = _wait_webhook_idle(timeout_s=180)
    pre_last_started = pre_runs[-1].get("started_at") if pre_runs else None

    # Record current baseline commit SHA from Gitea gc-intended
    c_resp = requests.get(
        f"{gitea_url}/api/v1/repos/netops/gc-intended/commits",
        params={"limit": 1},
        auth=(gitea_user, gitea_secret),
        timeout=15,
    )
    c_resp.raise_for_status()
    baseline_sha = c_resp.json()[0]["sha"]
    BASELINE_SHA_FILE.write_text(baseline_sha + "\n", encoding="utf-8")
    lines.append(f"Pre-change Gitea gc-intended baseline commit: {baseline_sha[:10]}")
    lines.append("")

    # Apply planned SoT demo change
    rc_seed, out_seed, err_seed = run_cmd(
        [sys.executable, "/workspace/testdata/seed_nautobot.py", "--apply-demo-change"],
        timeout=120,
    )
    lines.append("## Step 1: Apply SoT Demo Change (testdata/seed_nautobot.py --apply-demo-change)")
    lines.append(out_seed.strip())
    if err_seed.strip():
        lines.append("STDERR: " + err_seed.strip())
    lines.append("")
    if rc_seed != 0:
        errors.append(f"seed_nautobot.py --apply-demo-change exited {rc_seed}")

    # Wait for webhook to fire, debounce, and complete pipeline run
    lines.append("## Step 2: Nautobot Webhook -> CI/CD Pipeline Execution")
    deadline = time.time() + 240
    triggered_run: Optional[Dict[str, Any]] = None
    while time.time() < deadline:
        time.sleep(3)
        r = requests.get("http://127.0.0.1:8086/runs", timeout=10)
        runs = r.json().get("runs", [])
        if runs:
            latest = runs[-1]
            if latest.get("started_at") != pre_last_started and latest.get("status") in ("success", "failed"):
                # Also make sure no earlier triggered run is still running
                if not any(x.get("status") == "running" for x in runs):
                    triggered_run = latest
                    break

    if not triggered_run:
        errors.append("Timed out waiting for webhook-triggered CI/CD pipeline run")
    else:
        lines.append(f"Webhook run status: {triggered_run.get('status')} (rc={triggered_run.get('returncode')})")
        lines.append(f"Reason: {triggered_run.get('reason')}")
        lines.append(f"Started: {triggered_run.get('started_at')} | Finished: {triggered_run.get('finished_at')}")
        lines.append("--- Pipeline stdout tail ---")
        lines.append(triggered_run.get("stdout_tail", ""))
        if triggered_run.get("status") != "success":
            errors.append(f"Webhook pipeline run failed: {triggered_run.get('stderr_tail')}")
    lines.append("")

    # Fetch latest merged PR from Gitea netops/gc-intended
    prs_r = requests.get(
        f"{gitea_url}/api/v1/repos/netops/gc-intended/pulls",
        params={"state": "closed", "sort": "recentupdate", "limit": 3},
        auth=(gitea_user, gitea_secret),
        timeout=15,
    )
    pr_number = None
    pr_title = None
    pr_merged = False
    if prs_r.ok and prs_r.json():
        pr = prs_r.json()[0]
        pr_number = pr.get("number")
        pr_title = pr.get("title")
        pr_merged = bool(pr.get("merged"))
        lines.append(f"## Step 3: Gitea Pull Request #{pr_number}")
        lines.append(f"Title:  {pr_title}")
        lines.append(f"Merged: {pr_merged} | Head: {(pr.get('head') or {}).get('ref')} -> Base: {(pr.get('base') or {}).get('ref')}")
        comments_r = requests.get(
            f"{gitea_url}/api/v1/repos/netops/gc-intended/issues/{pr_number}/comments",
            auth=(gitea_user, gitea_secret),
            timeout=15,
        )
        if comments_r.ok and comments_r.json():
            lines.append("--- PR Diff & Lint Comment ---")
            lines.append(comments_r.json()[-1].get("body", ""))
        lines.append("")
    else:
        errors.append("Could not fetch Gitea PR for T5")

    # Verify live router CLI
    lines.append("## Step 4: Live Router CLI Verification")
    l1 = _netmiko_exec("172.30.30.11", "arista_eos", ["show vlan", "show running-config interfaces Ethernet2"])
    l2 = _netmiko_exec("172.30.30.12", "arista_eos", ["show vlan"])
    c1 = _netmiko_exec("172.30.30.13", "cisco_xe", ["show ip interface brief", "show running-config interface Loopback10"])

    lines.append("### ceos-leaf1: show vlan")
    lines.append(l1["show vlan"].strip())
    lines.append("### ceos-leaf1: show running-config interfaces Ethernet2")
    lines.append(l1["show running-config interfaces Ethernet2"].strip())
    lines.append("### ceos-leaf2: show vlan")
    lines.append(l2["show vlan"].strip())
    lines.append("### cisco-core1: show ip interface brief")
    lines.append(c1["show ip interface brief"].strip())
    lines.append("### cisco-core1: show running-config interface Loopback10")
    lines.append(c1["show running-config interface Loopback10"].strip())
    lines.append("")

    if "300" not in l1["show vlan"] or "LAB-CI-DEMO" not in l1["show vlan"]:
        errors.append("ceos-leaf1 missing VLAN 300 LAB-CI-DEMO after deploy")
    if "300" not in l2["show vlan"] or "LAB-CI-DEMO" not in l2["show vlan"]:
        errors.append("ceos-leaf2 missing VLAN 300 LAB-CI-DEMO after deploy")
    if "CI/CD Managed" not in l1["show running-config interfaces Ethernet2"]:
        errors.append("ceos-leaf1 Ethernet2 description not updated after deploy")
    if "Loopback10" not in c1["show ip interface brief"] or "203.0.113.250" not in c1["show ip interface brief"]:
        errors.append("cisco-core1 missing Loopback10 203.0.113.250 after deploy")

    # Verify post-deploy Golden Config compliance
    rows = _fetch_compliance(sess, nb_url)
    compliant = sum(1 for r in rows if r["compliance"])
    total = len(rows)
    lines.append("## Step 5: Post-Deploy Golden Config Compliance")
    lines.append(_format_compliance_table(rows))
    lines.append("")
    if total != 20 or compliant != 20:
        errors.append(f"Expected 20/20 post-deploy compliance, got {compliant}/{total}")

    passed = len(errors) == 0
    lines.append(f"## Result: {'PASS' if passed else 'FAIL'}")
    if errors:
        lines.extend([f"  - {e}" for e in errors])
    write_evidence("t5_sot_cicd_deploy.txt", "\n".join(lines) + "\n")
    return {
        "test": "T5",
        "name": "SoT Change -> Webhook -> CI/CD -> Live Deploy",
        "passed": passed,
        "baseline_sha": baseline_sha[:10],
        "pr_number": pr_number,
        "pr_merged": pr_merged,
        "post_deploy_compliant": compliant,
        "post_deploy_total": total,
        "errors": errors,
    }


def run_t6_container() -> Dict[str, Any]:
    sess, nb_url = _nb_session()
    errors: List[str] = []
    lines = [f"# T6: Manual Drift Injection -> Detection -> Golden Config Remediation", f"Timestamp: {utc_now()}", ""]

    # Step 1: Inject real out-of-band drift on ceos-leaf1 and cisco-core1
    lines.append("## Step 1: Inject Manual Out-of-Band Drift")
    l1_drift = _netmiko_exec(
        "172.30.30.11",
        "arista_eos",
        ["show running-config | include snmp-server|logging host"],
        config_cmds=[
            "no snmp-server community lab-ro-demo",
            "snmp-server community DRIFT-BAD ro",
            "logging host 192.0.2.250",
        ],
    )
    c1_drift = _netmiko_exec(
        "172.30.30.13",
        "cisco_xe",
        ["show running-config | include snmp-server|logging host"],
        config_cmds=[
            "no snmp-server community lab-ro-demo RO",
            "snmp-server community DRIFT-BAD RO",
        ],
    )
    lines.append("### ceos-leaf1 after drift injection:")
    lines.append(l1_drift["show running-config | include snmp-server|logging host"].strip())
    lines.append("### cisco-core1 after drift injection:")
    lines.append(c1_drift["show running-config | include snmp-server|logging host"].strip())
    lines.append("")

    # Step 2: Run BackupJob + ComplianceJob to detect drift
    lines.append("## Step 2: Golden Config Drift Detection (BackupJob + ComplianceJob)")
    for cls in ("BackupJob", "ComplianceJob"):
        res = _run_nb_job(sess, nb_url, cls)
        lines.append(f"Job {res['job']}: {res['status']}")
        if res["status"] != "SUCCESS":
            errors.append(f"Drift detection {cls} failed: {res['status']}")

    drift_rows = _fetch_compliance(sess, nb_url)
    drift_compliant = sum(1 for r in drift_rows if r["compliance"])
    drift_total = len(drift_rows)
    non_compliant_items = [r for r in drift_rows if not r["compliance"]]
    lines.append(_format_compliance_table(drift_rows))
    lines.append("")

    if drift_compliant >= drift_total:
        errors.append(f"Expected non-compliant features after drift injection, got {drift_compliant}/{drift_total}")

    # Step 3: Generate Remediation Config Plans via Nautobot Golden Config
    lines.append("## Step 3: Generate Golden Config Remediation Plans (GenerateConfigPlans)")
    devs = sess.get(f"{nb_url}/api/dcim/devices/", params={"limit": 50}, timeout=30).json().get("results", [])
    dev_ids = [d["id"] for d in devs if d["name"] in ("ceos-leaf1", "cisco-core1")]

    # Record existing plan IDs so we only approve/deploy newly generated ones
    existing_plans = {
        p["id"]
        for p in sess.get(f"{nb_url}/api/plugins/golden-config/config-plan/", params={"limit": 200}, timeout=30).json().get("results", [])
    }

    gen_res = _run_nb_job(
        sess,
        nb_url,
        "GenerateConfigPlans",
        data={"plan_type": "remediation", "device": dev_ids, "change_control_id": "LAB-DRIFT-REMED-001"},
    )
    lines.append(f"GenerateConfigPlans status: {gen_res['status']}")
    lines.extend(gen_res["logs"][-15:])
    lines.append("")
    if gen_res["status"] != "SUCCESS":
        errors.append(f"GenerateConfigPlans failed: {gen_res['status']}")

    all_plans = sess.get(
        f"{nb_url}/api/plugins/golden-config/config-plan/",
        params={"limit": 200, "depth": 1},
        timeout=30,
    ).json().get("results", [])
    new_plans = [p for p in all_plans if p["id"] not in existing_plans]
    lines.append(f"Generated {len(new_plans)} new ConfigPlan(s):")
    for p in new_plans:
        dname = (p.get("device") or {}).get("name")
        lines.append(f"--- ConfigPlan for {dname} (id={p['id']}, plan_type={p.get('plan_type')}) ---")
        lines.append((p.get("config_set") or "").strip())
    lines.append("")
    if not new_plans:
        errors.append("GenerateConfigPlans produced 0 new ConfigPlans")

    # Step 4: Approve ConfigPlans and Deploy via DeployConfigPlans
    lines.append("## Step 4: Approve & Deploy Remediation Config Plans (DeployConfigPlans)")
    statuses = sess.get(f"{nb_url}/api/extras/statuses/", params={"limit": 100}, timeout=30).json().get("results", [])
    approved_id = next((s["id"] for s in statuses if s["name"] == "Approved"), None)
    if not approved_id:
        errors.append("Could not find 'Approved' status in Nautobot")
    else:
        for p in new_plans:
            pr = sess.patch(
                f"{nb_url}/api/plugins/golden-config/config-plan/{p['id']}/",
                json={"status": approved_id},
                timeout=30,
            )
            if not pr.ok:
                errors.append(f"Failed to approve ConfigPlan {p['id']}: {pr.status_code} {pr.text}")
            else:
                lines.append(f"  Approved ConfigPlan {p['id']} ({(p.get('device') or {}).get('name')})")

    plan_ids = [p["id"] for p in new_plans]
    deploy_res = None
    if plan_ids:
        deploy_res = _run_nb_job(
            sess,
            nb_url,
            "DeployConfigPlans",
            data={"config_plan": plan_ids, "fail_job_on_task_failure": True},
        )
        lines.append(f"DeployConfigPlans status: {deploy_res['status']}")
        lines.extend(deploy_res["logs"][-20:])
        lines.append("")
        if deploy_res["status"] != "SUCCESS":
            errors.append(f"DeployConfigPlans ended with {deploy_res['status']}")

    # Step 5: Verify live router CLI after remediation
    lines.append("## Step 5: Live Router CLI Verification Post-Remediation")
    l1_post = _netmiko_exec("172.30.30.11", "arista_eos", ["show running-config | include snmp-server|logging host"])
    c1_post = _netmiko_exec("172.30.30.13", "cisco_xe", ["show running-config | include snmp-server|logging host"])
    l1_out = l1_post["show running-config | include snmp-server|logging host"].strip()
    c1_out = c1_post["show running-config | include snmp-server|logging host"].strip()
    lines.append("### ceos-leaf1 post-remediation:")
    lines.append(l1_out)
    lines.append("### cisco-core1 post-remediation:")
    lines.append(c1_out)
    lines.append("")

    if "DRIFT-BAD" in l1_out or "192.0.2.250" in l1_out or "lab-ro-demo" not in l1_out:
        errors.append(f"ceos-leaf1 drift not fully remediated: {l1_out}")
    if "DRIFT-BAD" in c1_out or "lab-ro-demo" not in c1_out:
        errors.append(f"cisco-core1 drift not fully remediated: {c1_out}")

    # Step 6: Re-run BackupJob + ComplianceJob -> verify 20/20 compliant
    lines.append("## Step 6: Post-Remediation Golden Config Compliance")
    for cls in ("BackupJob", "ComplianceJob"):
        res = _run_nb_job(sess, nb_url, cls)
        lines.append(f"Job {res['job']}: {res['status']}")
        if res["status"] != "SUCCESS":
            errors.append(f"Post-remediation {cls} failed: {res['status']}")

    post_rows = _fetch_compliance(sess, nb_url)
    post_compliant = sum(1 for r in post_rows if r["compliance"])
    post_total = len(post_rows)
    lines.append(_format_compliance_table(post_rows))
    lines.append("")
    if post_total != 20 or post_compliant != 20:
        errors.append(f"Expected 20/20 post-remediation compliance, got {post_compliant}/{post_total}")

    passed = len(errors) == 0
    lines.append(f"## Result: {'PASS' if passed else 'FAIL'}")
    if errors:
        lines.extend([f"  - {e}" for e in errors])
    write_evidence("t6_drift_remediation.txt", "\n".join(lines) + "\n")
    return {
        "test": "T6",
        "name": "Manual Drift Detection & Golden Config Remediation",
        "passed": passed,
        "drift_detected_compliant": drift_compliant,
        "drift_detected_total": drift_total,
        "non_compliant_features": [f"{r['device']}:{r['feature']}" for r in non_compliant_items],
        "plans_generated": len(new_plans),
        "deploy_status": deploy_res["status"] if deploy_res else None,
        "post_remediation_compliant": post_compliant,
        "post_remediation_total": post_total,
        "errors": errors,
    }


def run_t7_container() -> Dict[str, Any]:
    sess, nb_url = _nb_session()
    errors: List[str] = []
    lines = [f"# T7: Rollback via pipeline/rollback.py + SoT Revert + Final Compliance", f"Timestamp: {utc_now()}", ""]

    target_ref = "HEAD~1"
    if BASELINE_SHA_FILE.exists():
        saved = BASELINE_SHA_FILE.read_text(encoding="utf-8").strip()
        if saved:
            target_ref = saved

    lines.append(f"## Step 1: Execute pipeline/rollback.py --commit {target_ref[:10]}")
    rc_rb, out_rb, err_rb = run_cmd(
        [sys.executable, "/workspace/pipeline/rollback.py", "--commit", target_ref],
        timeout=240,
    )
    lines.append(out_rb.strip())
    if err_rb.strip():
        lines.append("STDERR: " + err_rb.strip())
    lines.append("")
    if rc_rb != 0:
        errors.append(f"pipeline/rollback.py exited {rc_rb}")

    pr_match = re.search(r"Rollback PR #(\d+)", out_rb)
    rollback_pr = int(pr_match.group(1)) if pr_match else None

    # Step 2: Verify live router CLI immediately after rollback
    lines.append("## Step 2: Live Router CLI Verification Post-Rollback")
    l1 = _netmiko_exec("172.30.30.11", "arista_eos", ["show vlan", "show running-config interfaces Ethernet2"])
    l2 = _netmiko_exec("172.30.30.12", "arista_eos", ["show vlan"])
    c1 = _netmiko_exec("172.30.30.13", "cisco_xe", ["show ip interface brief"])

    lines.append("### ceos-leaf1: show vlan")
    lines.append(l1["show vlan"].strip())
    lines.append("### ceos-leaf1: show running-config interfaces Ethernet2")
    lines.append(l1["show running-config interfaces Ethernet2"].strip())
    lines.append("### ceos-leaf2: show vlan")
    lines.append(l2["show vlan"].strip())
    lines.append("### cisco-core1: show ip interface brief")
    lines.append(c1["show ip interface brief"].strip())
    lines.append("")

    if "300" in l1["show vlan"] or "LAB-CI-DEMO" in l1["show vlan"]:
        errors.append("ceos-leaf1 still has VLAN 300 after rollback")
    if "300" in l2["show vlan"] or "LAB-CI-DEMO" in l2["show vlan"]:
        errors.append("ceos-leaf2 still has VLAN 300 after rollback")
    if "CI/CD Managed" in l1["show running-config interfaces Ethernet2"]:
        errors.append("ceos-leaf1 Ethernet2 description was not restored after rollback")
    if "Loopback10" in c1["show ip interface brief"]:
        errors.append("cisco-core1 still has Loopback10 after rollback")

    # Step 3: Revert Nautobot SoT so SoT and live devices stay in sync
    lines.append("## Step 3: Revert Nautobot SoT (testdata/seed_nautobot.py --revert-demo-change)")
    rc_rev, out_rev, err_rev = run_cmd(
        [sys.executable, "/workspace/testdata/seed_nautobot.py", "--revert-demo-change"],
        timeout=120,
    )
    lines.append(out_rev.strip())
    if err_rev.strip():
        lines.append("STDERR: " + err_rev.strip())
    lines.append("")
    if rc_rev != 0:
        errors.append(f"seed_nautobot.py --revert-demo-change exited {rc_rev}")

    # Allow any coalesced webhook run triggered by the SoT revert to finish cleanly
    time.sleep(6)
    _wait_webhook_idle(timeout_s=240)

    # Step 4: Final Golden Config Backup + Intended + Compliance
    lines.append("## Step 4: Final Golden Config Compliance (BackupJob + IntendedJob + ComplianceJob)")
    for cls in ("BackupJob", "IntendedJob", "ComplianceJob"):
        res = _run_nb_job(sess, nb_url, cls)
        lines.append(f"Job {res['job']}: {res['status']}")
        if res["status"] != "SUCCESS":
            errors.append(f"Final {cls} failed: {res['status']}")

    final_rows = _fetch_compliance(sess, nb_url)
    final_compliant = sum(1 for r in final_rows if r["compliance"])
    final_total = len(final_rows)
    lines.append(_format_compliance_table(final_rows))
    lines.append("")
    if final_total != 20 or final_compliant != 20:
        errors.append(f"Expected 20/20 final compliance after rollback, got {final_compliant}/{final_total}")

    passed = len(errors) == 0
    lines.append(f"## Result: {'PASS' if passed else 'FAIL'}")
    if errors:
        lines.extend([f"  - {e}" for e in errors])
    write_evidence("t7_rollback.txt", "\n".join(lines) + "\n")
    return {
        "test": "T7",
        "name": "Rollback + SoT Revert + Final Baseline Compliance",
        "passed": passed,
        "rollback_target_sha": target_ref[:10],
        "rollback_pr_number": rollback_pr,
        "final_compliant": final_compliant,
        "final_total": final_total,
        "errors": errors,
    }


CONTAINER_STEPS = {
    "t2": run_t2_container,
    "t3": run_t3_container,
    "t4": run_t4_container,
    "t5": run_t5_container,
    "t6": run_t6_container,
    "t7": run_t7_container,
}


def invoke_container_step(step: str) -> Dict[str, Any]:
    rc, out, err = run_cmd(
        [
            "docker",
            "exec",
            CONTAINER_NAME,
            "python3",
            "/workspace/tests/run_e2e_tests.py",
            "--container-step",
            step,
        ],
        cwd=REPO_ROOT,
        timeout=600,
    )
    if rc != 0:
        return {
            "test": step.upper(),
            "passed": False,
            "errors": [f"Container step {step} exited {rc}: {(err or out)[-500:]}"],
        }
    # Parse last JSON object printed by container step
    for line in reversed(out.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            return json.loads(line)
    return {"test": step.upper(), "passed": False, "errors": [f"No JSON result returned for {step}"]}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run end-to-end tests for the Nautobot 3.2.9 CI/CD lab.")
    parser.add_argument(
        "--only",
        help="Comma-separated subset of tests to run (e.g. t1,t2,t6). Default: t1,t2,t3,t4,t5,t6,t7",
    )
    parser.add_argument(
        "--container-step",
        choices=sorted(CONTAINER_STEPS.keys()),
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()

    if args.container_step:
        result = CONTAINER_STEPS[args.container_step]()
        print(json.dumps(result))
        return 0 if result.get("passed") else 1

    steps = ["t1", "t2", "t3", "t4", "t5", "t6", "t7"]
    if args.only:
        steps = [s.strip().lower() for s in args.only.split(",") if s.strip()]

    summary: Dict[str, Any] = {
        "timestamp": utc_now(),
        "host": "mydell1",
        "results": [],
    }

    all_passed = True
    for step in steps:
        print(f"=== Running {step.upper()} ===", flush=True)
        if step == "t1":
            res = run_t1_host()
        elif step in CONTAINER_STEPS:
            res = invoke_container_step(step)
        else:
            print(f"Unknown test step: {step}", file=sys.stderr)
            return 2

        summary["results"].append(res)
        status = "PASS" if res.get("passed") else "FAIL"
        print(f"=== {step.upper()}: {status} ===", flush=True)
        if not res.get("passed"):
            all_passed = False
            for e in res.get("errors", []):
                print(f"  ERROR: {e}", file=sys.stderr)

    summary["all_passed"] = all_passed
    summary["passed_count"] = sum(1 for r in summary["results"] if r.get("passed"))
    summary["total_count"] = len(summary["results"])
    write_evidence("summary.json", json.dumps(summary, indent=2) + "\n")

    print(f"\nE2E Suite Complete: {summary['passed_count']}/{summary['total_count']} passed.")
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
