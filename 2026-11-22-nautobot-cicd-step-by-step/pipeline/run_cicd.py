#!/usr/bin/env python3
"""
Nautobot SoT-driven CI/CD Pipeline for Arista cEOS and Cisco IOS-XE/IOS.

Stages:
  1. Fetch SoT data from Nautobot GraphQL API
  2. Render intended configs using Git-backed Jinja2 templates
  3. Lint & Validate (syntax, RFC 5737 / lab IP checks, prohibited config, BGP ASN, VLAN IDs)
  4. Dry-run Diff against live routers over SSH (Netmiko)
  5. Git Branch & Pull Request in Gitea (with lint + diff PR comment, optional --auto-merge)
  6. Deploy config changes to live devices & write memory (when --deploy is set)
  7. Post-deploy Nautobot Golden Config Compliance check (Backup + Intended + Compliance)
"""

import argparse
import difflib
import ipaddress
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import jinja2
import requests
from netmiko import ConnectHandler


REPO_ROOT = Path(__file__).resolve().parent.parent

ALLOWED_NETWORKS = [
    ipaddress.ip_network("192.0.2.0/24"),      # RFC 5737 TEST-NET-1
    ipaddress.ip_network("198.51.100.0/24"),   # RFC 5737 TEST-NET-2
    ipaddress.ip_network("203.0.113.0/24"),    # RFC 5737 TEST-NET-3
    ipaddress.ip_network("172.30.30.0/24"),    # Lab management
]

PROHIBITED_PATTERNS = [
    (re.compile(r"(?i)^\s*snmp-server\s+community\s+(public|private)\b", re.M), "Default SNMP community (public/private)"),
    (re.compile(r"(?i)^\s*ip\s+http\s+server\b", re.M), "Unencrypted HTTP server enabled"),
    (re.compile(r"(?i)^\s*transport\s+input\s+.*\btelnet\b", re.M), "Telnet enabled"),
    (re.compile(r"(?i)^\s*permit\s+ip\s+any\s+any\b", re.M), "Overly permissive ACL"),
]

IPV4_RE = re.compile(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b")

SOT_GRAPHQL_QUERY = """
query {
  devices {
    id
    name
    config_context
    platform {
      name
      network_driver
      napalm_driver
    }
    location {
      name
      vlans {
        vid
        name
        status {
          name
        }
      }
    }
    role {
      name
    }
    primary_ip4 {
      address
    }
    interfaces {
      name
      description
      enabled
      ip_addresses {
        address
      }
    }
  }
  vlans {
    vid
    name
    status {
      name
    }
  }
}
"""


def env_or_fail(name: str, default: Optional[str] = None) -> str:
    val = os.environ.get(name, default)
    if not val:
        raise RuntimeError(f"Required environment variable {name} is not set.")
    return val


def is_valid_netmask(ip_str: str) -> bool:
    try:
        ip = ipaddress.IPv4Address(ip_str)
        # Valid netmask in binary is contiguous 1s followed by contiguous 0s
        bits = f"{int(ip):032b}"
        return "01" not in bits and bits.startswith("1")
    except ValueError:
        return False


def fetch_sot_devices(nautobot_url: str, token: str, device_filter: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    resp = requests.post(
        f"{nautobot_url.rstrip('/')}/api/graphql/",
        headers={"Authorization": f"Token {token}", "Content-Type": "application/json"},
        json={"query": SOT_GRAPHQL_QUERY},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("errors"):
        raise RuntimeError(f"Nautobot GraphQL error: {json.dumps(data['errors'])}")
    devices = data.get("data", {}).get("devices", [])
    global_vlans = data.get("data", {}).get("vlans", [])
    for d in devices:
        d["vlans"] = global_vlans
    if device_filter:
        wanted = set(device_filter)
        devices = [d for d in devices if d["name"] in wanted]
    return sorted(devices, key=lambda d: d["name"])


def render_configs(devices: List[Dict[str, Any]], templates_dir: Path) -> Dict[str, Tuple[str, str]]:
    """Return {device_name: (rel_path, rendered_cfg)}."""
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(templates_dir)),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    tmpl = env.get_template("main.j2")
    rendered: Dict[str, Tuple[str, str]] = {}
    for dev in devices:
        loc_name = (dev.get("location") or {}).get("name", "Lab-DC1")
        cfg = tmpl.render(**dev)
        # Normalize multiple blank lines
        cfg = re.sub(r"\n{3,}", "\n\n", cfg).strip() + "\n"
        rel_path = f"{loc_name}/{dev['name']}.cfg"
        rendered[dev["name"]] = (rel_path, cfg)
    return rendered


def lint_configs(rendered: Dict[str, Tuple[str, str]]) -> Tuple[bool, List[str]]:
    """Validate rendered configs; returns (passed, messages)."""
    errors: List[str] = []
    notes: List[str] = []

    for dev_name, (_rel, cfg) in rendered.items():
        if not cfg.strip():
            errors.append(f"[{dev_name}] Rendered config is empty")
            continue
        if f"hostname {dev_name}" not in cfg:
            errors.append(f"[{dev_name}] Missing 'hostname {dev_name}'")
        if not cfg.rstrip().endswith("end"):
            errors.append(f"[{dev_name}] Config does not terminate with 'end'")

        for pat, desc in PROHIBITED_PATTERNS:
            if pat.search(cfg):
                errors.append(f"[{dev_name}] Prohibited config found: {desc}")

        # Validate IPv4 addresses are RFC 5737, lab mgmt, or valid subnet masks
        for match in IPV4_RE.finditer(cfg):
            ip_str = match.group(1)
            if is_valid_netmask(ip_str):
                continue
            try:
                addr = ipaddress.IPv4Address(ip_str)
            except ValueError:
                errors.append(f"[{dev_name}] Invalid IPv4 address: {ip_str}")
                continue
            if not any(addr in net for net in ALLOWED_NETWORKS):
                errors.append(f"[{dev_name}] Non-RFC5737/non-lab IP detected: {ip_str}")

        # Validate BGP ASNs
        for asn_m in re.finditer(r"(?:router bgp|remote-as)\s+(\d+)", cfg):
            asn = int(asn_m.group(1))
            if not (64512 <= asn <= 65534):
                errors.append(f"[{dev_name}] BGP ASN {asn} outside private lab range 64512-65534")

        # Validate VLAN IDs
        for vlan_m in re.finditer(r"^vlan\s+(\d+)\s*$", cfg, re.M):
            vid = int(vlan_m.group(1))
            if vid < 1 or vid > 4094 or (1002 <= vid <= 1005):
                errors.append(f"[{dev_name}] Invalid or reserved VLAN ID: {vid}")

        notes.append(f"[{dev_name}] Lint OK ({len(cfg.splitlines())} lines)")

    if errors:
        return False, errors
    return True, notes


def netmiko_device_type(platform: Optional[Dict[str, Any]]) -> str:
    driver = ((platform or {}).get("network_driver") or (platform or {}).get("name") or "").lower()
    if "arista" in driver or driver == "eos":
        return "arista_eos"
    if "cisco_xe" in driver or "iosxe" in driver:
        return "cisco_xe"
    return "cisco_ios"


def extract_managed_sections(running_cfg: str, dev_type: str) -> str:
    """Extract only the sections managed by our Jinja templates for clean diff comparison."""
    lines = running_cfg.splitlines()
    out: List[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if any(
            line.startswith(prefix)
            for prefix in (
                "hostname ",
                "ip domain-name ",
                "ip domain name ",
                "ntp server ",
                "logging host ",
                "snmp-server community ",
            )
        ):
            out.append(line)
            i += 1
            continue

        if (
            (dev_type == "arista_eos" and re.match(r"^vlan\s+\d+", line))
            or re.match(r"^interface\s+(Ethernet|Loopback|GigabitEthernet[2-9]|GigabitEthernet0/[1-9])", line)
            or line.startswith("router bgp ")
        ):
            out.append(line)
            i += 1
            while i < len(lines) and (lines[i].startswith(" ") or lines[i].startswith("\t")):
                out.append(lines[i])
                i += 1
            out.append("!")
            continue

        i += 1
    return "\n".join(out) + "\n"


def compute_config_commands(intended_cfg: str, running_cfg: str, dev_type: str) -> List[str]:
    """
    Build the exact CLI command list to converge the device to intended_cfg,
    including 'no ...' removals for VLANs, Loopbacks (except Loopback0), NTP, syslog, SNMP
    that were present in running_cfg but removed from intended_cfg (essential for rollback!).
    """
    commands: List[str] = []

    # 1. Detect removals (live managed items not in intended)
    intended_vlans = set(re.findall(r"^vlan\s+(\d+)\s*$", intended_cfg, re.M))
    running_vlans = set(re.findall(r"^vlan\s+(\d+)\s*$", running_cfg, re.M))
    if dev_type == "arista_eos":
        for vid in sorted(running_vlans - intended_vlans, key=int):
            if int(vid) >= 10:  # Never touch default VLAN 1
                commands.append(f"no vlan {vid}")

    intended_loopbacks = set(re.findall(r"^interface\s+(Loopback\d+)\s*$", intended_cfg, re.M))
    running_loopbacks = set(re.findall(r"^interface\s+(Loopback\d+)\s*$", running_cfg, re.M))
    for lo in sorted(running_loopbacks - intended_loopbacks):
        if lo != "Loopback0":
            commands.append(f"no interface {lo}")

    intended_ntp = set(re.findall(r"^ntp server\s+(\S+)", intended_cfg, re.M))
    running_ntp = set(re.findall(r"^ntp server\s+(\S+)", running_cfg, re.M))
    for srv in sorted(running_ntp - intended_ntp):
        commands.append(f"no ntp server {srv}")

    intended_log = set(re.findall(r"^logging host\s+(\S+)", intended_cfg, re.M))
    running_log = set(re.findall(r"^logging host\s+(\S+)", running_cfg, re.M))
    for srv in sorted(running_log - intended_log):
        commands.append(f"no logging host {srv}")

    intended_snmp = set(re.findall(r"^snmp-server community\s+(\S+)", intended_cfg, re.M))
    running_snmp = set(re.findall(r"^snmp-server community\s+(\S+)", running_cfg, re.M))
    for comm in sorted(running_snmp - intended_snmp):
        commands.append(f"no snmp-server community {comm}")

    # 2. Apply intended config lines (skip comments and trailing 'end')
    for line in intended_cfg.splitlines():
        s = line.strip()
        if not s or s == "!" or s == "end":
            continue
        commands.append(line)

    return commands


def dry_run_and_optional_deploy(
    devices: List[Dict[str, Any]],
    rendered: Dict[str, Tuple[str, str]],
    username: str,
    password: str,
    secret: str,
    deploy: bool = False,
) -> Dict[str, Dict[str, Any]]:
    results: Dict[str, Dict[str, Any]] = {}
    for dev in devices:
        name = dev["name"]
        primary_ip = (dev.get("primary_ip4") or {}).get("address", "")
        host = primary_ip.split("/")[0]
        if not host:
            results[name] = {"error": "No primary_ip4 assigned in Nautobot"}
            continue
        dev_type = netmiko_device_type(dev.get("platform"))
        _rel, intended_cfg = rendered[name]

        conn_params = {
            "device_type": dev_type,
            "host": host,
            "username": username,
            "password": password,
            "secret": secret,
            "conn_timeout": 20,
            "fast_cli": False,
        }
        with ConnectHandler(**conn_params) as conn:
            conn.enable()
            running_cfg = conn.send_command("show running-config")
            live_managed = extract_managed_sections(running_cfg, dev_type)
            diff_lines = list(
                difflib.unified_diff(
                    live_managed.splitlines(),
                    intended_cfg.splitlines(),
                    fromfile=f"live/{name}.cfg",
                    tofile=f"intended/{name}.cfg",
                    lineterm="",
                )
            )
            commands = compute_config_commands(intended_cfg, running_cfg, dev_type)
            deploy_output = ""
            if deploy:
                deploy_output = conn.send_config_set(commands, cmd_verify=False)
                save_out = conn.save_config()
                deploy_output += "\n" + save_out

            results[name] = {
                "host": host,
                "device_type": dev_type,
                "diff": "\n".join(diff_lines) if diff_lines else "(no diff)",
                "command_count": len(commands),
                "deployed": deploy,
                "deploy_output_tail": "\n".join(deploy_output.splitlines()[-12:]) if deploy_output else "",
            }
    return results


def gitea_branch_pr_merge(
    gitea_url: str,
    org: str,
    repo: str,
    user: str,
    token_or_pass: str,
    rendered: Dict[str, Tuple[str, str]],
    branch_name: str,
    pr_title: str,
    pr_body: str,
    comment_body: str,
    auto_merge: bool = False,
) -> Dict[str, Any]:
    proto, rest = gitea_url.rstrip("/").split("://", 1)
    auth_url = f"{proto}://{user}:{token_or_pass}@{rest}/{org}/{repo}.git"

    with tempfile.TemporaryDirectory(prefix="cicd-git-") as tmpdir:
        repo_dir = Path(tmpdir) / "repo"
        subprocess.run(["git", "clone", "--branch", "main", auth_url, str(repo_dir)], check=True, capture_output=True, text=True)
        subprocess.run(["git", "-C", str(repo_dir), "config", "user.name", "NetOps CI Pipeline"], check=True)
        subprocess.run(["git", "-C", str(repo_dir), "config", "user.email", "ci@lab.internal"], check=True)
        subprocess.run(["git", "-C", str(repo_dir), "checkout", "-b", branch_name], check=True, capture_output=True, text=True)

        for _dev, (rel_path, cfg) in rendered.items():
            target = repo_dir / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(cfg, encoding="utf-8")

        subprocess.run(["git", "-C", str(repo_dir), "add", "-A"], check=True)
        status = subprocess.run(["git", "-C", str(repo_dir), "status", "--porcelain"], check=True, capture_output=True, text=True)
        if not status.stdout.strip():
            # Create an empty commit if no file diff so the PR / audit trail still works cleanly when requested
            subprocess.run(
                ["git", "-C", str(repo_dir), "commit", "--allow-empty", "-m", f"{pr_title} (no config delta)"],
                check=True,
                capture_output=True,
                text=True,
            )
        else:
            subprocess.run(
                ["git", "-C", str(repo_dir), "commit", "-m", pr_title],
                check=True,
                capture_output=True,
                text=True,
            )
        commit_sha = subprocess.run(
            ["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        subprocess.run(["git", "-C", str(repo_dir), "push", "-u", "origin", branch_name], check=True, capture_output=True, text=True)

    # Open PR via Gitea API
    headers = {"Content-Type": "application/json"}
    auth = None
    if os.environ.get("GITEA_TOKEN"):
        headers["Authorization"] = f"token {token_or_pass}"
    else:
        auth = (user, token_or_pass)

    pr_resp = requests.post(
        f"{gitea_url.rstrip('/')}/api/v1/repos/{org}/{repo}/pulls",
        headers=headers,
        auth=auth,
        json={"title": pr_title, "body": pr_body, "head": branch_name, "base": "main"},
        timeout=30,
    )
    pr_resp.raise_for_status()
    pr = pr_resp.json()
    pr_number = pr["number"]

    # Post lint + diff summary comment
    requests.post(
        f"{gitea_url.rstrip('/')}/api/v1/repos/{org}/{repo}/issues/{pr_number}/comments",
        headers=headers,
        auth=auth,
        json={"body": comment_body},
        timeout=30,
    ).raise_for_status()

    merged = False
    if auto_merge:
        merge_resp = None
        for attempt in range(6):
            time.sleep(1.5)
            merge_resp = requests.post(
                f"{gitea_url.rstrip('/')}/api/v1/repos/{org}/{repo}/pulls/{pr_number}/merge",
                headers=headers,
                auth=auth,
                json={"Do": "merge", "MergeTitleField": f"Merge PR #{pr_number}: {pr_title}"},
                timeout=30,
            )
            if merge_resp.status_code in (200, 204):
                merged = True
                break
            if merge_resp.status_code != 405:
                break
        if not merged and merge_resp is not None:
            raise RuntimeError(f"Gitea merge PR #{pr_number} failed ({merge_resp.status_code}): {merge_resp.text}")

    return {
        "branch": branch_name,
        "commit": commit_sha,
        "pr_number": pr_number,
        "pr_url": pr.get("html_url"),
        "merged": merged,
    }


def trigger_golden_config_compliance(nautobot_url: str, token: str, timeout_s: int = 180) -> Dict[str, Any]:
    """Trigger Nautobot Golden Config Backup + Intended + Compliance jobs and poll until done."""
    session = requests.Session()
    session.headers.update({"Authorization": f"Token {token}", "Content-Type": "application/json"})

    jobs = session.get(f"{nautobot_url.rstrip('/')}/api/extras/jobs/", params={"limit": 200}, timeout=30).json().get("results", [])
    job_by_class = {j.get("job_class_name"): j for j in jobs}

    # Prefer running Backup -> Intended -> Compliance in sequence so we get fresh state
    sequence = ["BackupJob", "IntendedJob", "ComplianceJob"]
    # Fallback to AllGoldenConfig if individual jobs have different names
    run_jobs = [job_by_class[c] for c in sequence if c in job_by_class]
    if not run_jobs and "AllGoldenConfig" in job_by_class:
        run_jobs = [job_by_class["AllGoldenConfig"]]

    job_statuses: List[Dict[str, Any]] = []
    for job in run_jobs:
        # Ensure job is enabled
        if not job.get("enabled"):
            session.patch(f"{nautobot_url.rstrip('/')}/api/extras/jobs/{job['id']}/", json={"enabled": True}, timeout=30)
        run_resp = session.post(
            f"{nautobot_url.rstrip('/')}/api/extras/jobs/{job['id']}/run/",
            json={"data": {}},
            timeout=30,
        )
        if not run_resp.ok:
            job_statuses.append({"job": job["name"], "status": f"ERROR({run_resp.status_code})", "detail": run_resp.text[:200]})
            continue
        jr = run_resp.json().get("job_result", {})
        jr_id = jr.get("id")
        deadline = time.time() + timeout_s
        final_status = "PENDING"
        while time.time() < deadline and jr_id:
            poll = session.get(f"{nautobot_url.rstrip('/')}/api/extras/job-results/{jr_id}/", timeout=30).json()
            final_status = poll.get("status", {}).get("value", poll.get("status", "UNKNOWN"))
            if str(final_status).upper() in ("SUCCESS", "FAILURE", "REVOKED", "ERROR"):
                break
            time.sleep(3)
        job_statuses.append({"job": job["name"], "job_result_id": jr_id, "status": final_status})

    # Fetch compliance summary
    comp_resp = session.get(
        f"{nautobot_url.rstrip('/')}/api/plugins/golden-config/config-compliance/",
        params={"limit": 200, "depth": 1},
        timeout=30,
    )
    compliance_rows: List[Dict[str, Any]] = []
    if comp_resp.ok:
        for row in comp_resp.json().get("results", []):
            rule = row.get("rule") or {}
            feat = rule.get("feature") if isinstance(rule, dict) else None
            feat_name = feat.get("name") if isinstance(feat, dict) else str(feat)
            compliance_rows.append(
                {
                    "device": (row.get("device") or {}).get("name"),
                    "feature": feat_name,
                    "compliance": row.get("compliance"),
                }
            )
    return {"jobs": job_statuses, "compliance": compliance_rows}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Nautobot SoT-driven CI/CD pipeline.")
    parser.add_argument("--devices", nargs="*", help="Optional device names to target")
    parser.add_argument("--reason", default="Manual CI/CD pipeline run", help="Trigger reason / PR description")
    parser.add_argument("--auto-merge", action="store_true", help="Automatically merge the Gitea Pull Request")
    parser.add_argument("--deploy", action="store_true", help="Deploy intended configs to live devices")
    parser.add_argument("--dry-run", action="store_true", help="Run dry-run diff only (never deploys)")
    parser.add_argument("--skip-gitea", action="store_true", help="Skip Gitea branch/PR creation")
    parser.add_argument("--skip-devices", action="store_true", help="Skip live device SSH diff/deploy")
    parser.add_argument("--run-compliance", action="store_true", help="Trigger Nautobot Golden Config compliance after deploy")
    parser.add_argument("--templates-dir", default=str(REPO_ROOT / "templates"), help="Path to Jinja2 templates")
    args = parser.parse_args()

    nautobot_url = os.environ.get("NAUTOBOT_URL", "http://127.0.0.1:8083")
    nautobot_token = env_or_fail("NAUTOBOT_TOKEN")
    gitea_url = os.environ.get("GITEA_URL", "http://127.0.0.1:3002")
    gitea_org = os.environ.get("GITEA_ORG", "netops")
    gitea_repo = os.environ.get("GITEA_INTENDED_REPO", "gc-intended")
    gitea_user = os.environ.get("GITEA_ADMIN_USER") or os.environ.get("GITEA_USER", "netops-admin")
    gitea_secret = os.environ.get("GITEA_TOKEN") or os.environ.get("GITEA_ADMIN_PASSWORD") or os.environ.get("GITEA_PASSWORD")

    dev_user = os.environ.get("DEVICE_USERNAME") or os.environ.get("LAB_DEVICE_USERNAME", "admin")
    dev_pass = os.environ.get("DEVICE_PASSWORD") or os.environ.get("LAB_DEVICE_PASSWORD")
    dev_secret = os.environ.get("DEVICE_ENABLE_SECRET") or os.environ.get("LAB_DEVICE_SECRET", dev_pass or "")

    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    summary: Dict[str, Any] = {"timestamp": ts, "reason": args.reason, "stages": {}}

    print(f"=== [Stage 1] Fetching SoT from {nautobot_url} ===")
    devices = fetch_sot_devices(nautobot_url, nautobot_token, args.devices)
    print(f"Fetched {len(devices)} device(s): {[d['name'] for d in devices]}")
    summary["stages"]["fetch_sot"] = [d["name"] for d in devices]

    print("=== [Stage 2] Rendering Jinja2 intended configs ===")
    rendered = render_configs(devices, Path(args.templates_dir))
    for dev, (rel, cfg) in rendered.items():
        print(f"  Rendered {rel} ({len(cfg.splitlines())} lines)")
    summary["stages"]["render"] = {k: v[0] for k, v in rendered.items()}

    print("=== [Stage 3] Linting & validating intended configs ===")
    lint_ok, lint_msgs = lint_configs(rendered)
    for m in lint_msgs:
        print(f"  {m}")
    summary["stages"]["lint"] = {"passed": lint_ok, "messages": lint_msgs}
    if not lint_ok:
        print("LINT FAILED — aborting pipeline before PR/deploy!", file=sys.stderr)
        print(json.dumps(summary, indent=2))
        return 2

    diff_results: Dict[str, Dict[str, Any]] = {}
    if not args.skip_devices:
        if not dev_pass:
            raise RuntimeError("LAB_DEVICE_PASSWORD must be set to connect to live devices.")
        print("=== [Stage 4] Dry-run diff against live devices ===")
        diff_results = dry_run_and_optional_deploy(devices, rendered, dev_user, dev_pass, dev_secret, deploy=False)
        for dev, res in diff_results.items():
            print(f"--- Diff for {dev} ({res.get('host')}) ---")
            print(res.get("diff", res.get("error")))
        summary["stages"]["dry_run_diff"] = diff_results

    if not args.skip_gitea:
        if not gitea_secret:
            raise RuntimeError("GITEA_TOKEN or GITEA_PASSWORD must be set for Gitea PR stage.")
        print("=== [Stage 5] Git branch & Pull Request in Gitea ===")
        branch = f"sot-change-{ts}"
        pr_title = f"SoT Change ({ts}): {args.reason[:60]}"
        pr_body = f"Automated intended-config update triggered by Nautobot SoT.\n\nReason: {args.reason}"
        comment_lines = ["### CI Lint & Dry-Run Diff Report", "", "**Lint**: PASSED"]
        for m in lint_msgs:
            comment_lines.append(f"- {m}")
        if diff_results:
            comment_lines.append("\n**Dry-Run Diffs**:")
            for dev, res in diff_results.items():
                comment_lines.append(f"\n#### `{dev}` (`{res.get('host')}`)\n```diff\n{res.get('diff', '')[:3000]}\n```")
        pr_info = gitea_branch_pr_merge(
            gitea_url,
            gitea_org,
            gitea_repo,
            gitea_user,
            gitea_secret,
            rendered,
            branch,
            pr_title,
            pr_body,
            "\n".join(comment_lines),
            auto_merge=args.auto_merge,
        )
        print(f"  PR #{pr_info['pr_number']} ({pr_info['pr_url']}) merged={pr_info['merged']} commit={pr_info['commit'][:10]}")
        summary["stages"]["gitea_pr"] = pr_info

    if args.deploy and not args.dry_run and not args.skip_devices:
        print("=== [Stage 6] Deploying intended configs to live devices ===")
        deploy_results = dry_run_and_optional_deploy(devices, rendered, dev_user, dev_pass, dev_secret, deploy=True)
        for dev, res in deploy_results.items():
            print(f"  Deployed to {dev} ({res.get('host')}): {res.get('command_count')} cmds")
        summary["stages"]["deploy"] = deploy_results

    if args.run_compliance:
        print("=== [Stage 7] Triggering Nautobot Golden Config Compliance ===")
        comp = trigger_golden_config_compliance(nautobot_url, nautobot_token)
        for js in comp["jobs"]:
            print(f"  Job {js['job']}: {js['status']}")
        compliant_cnt = sum(1 for r in comp["compliance"] if r.get("compliance") is True)
        total_cnt = len(comp["compliance"])
        print(f"  Compliance summary: {compliant_cnt}/{total_cnt} feature checks compliant")
        summary["stages"]["compliance"] = comp

    print("=== Pipeline Complete ===")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
