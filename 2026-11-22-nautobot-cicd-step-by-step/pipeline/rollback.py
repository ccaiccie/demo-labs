#!/usr/bin/env python3
"""
Rollback a pushed intended-config change from Gitea `netops/gc-intended`:
1. Checks out target commit (default: HEAD~1) from Gitea `gc-intended`
2. Creates a rollback branch + Pull Request in Gitea (with diff comment) and merges it
3. Deploys the restored intended configs to live Arista cEOS and Cisco routers
   (including `no vlan ...` / `no interface Loopback...` cleanup for removed objects)
4. Triggers Nautobot Golden Config Backup + Compliance to confirm clean state.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Tuple

from run_cicd import (
    dry_run_and_optional_deploy,
    env_or_fail,
    fetch_sot_devices,
    gitea_branch_pr_merge,
    lint_configs,
    trigger_golden_config_compliance,
)


def load_intended_from_commit(
    gitea_url: str,
    org: str,
    repo: str,
    user: str,
    secret: str,
    target_ref: str,
) -> Tuple[str, Dict[str, Tuple[str, str]]]:
    proto, rest = gitea_url.rstrip("/").split("://", 1)
    auth_url = f"{proto}://{user}:{secret}@{rest}/{org}/{repo}.git"

    with tempfile.TemporaryDirectory(prefix="cicd-rollback-") as tmpdir:
        repo_dir = Path(tmpdir) / "repo"
        subprocess.run(["git", "clone", "--branch", "main", auth_url, str(repo_dir)], check=True, capture_output=True, text=True)
        resolved_sha = subprocess.run(
            ["git", "-C", str(repo_dir), "rev-parse", target_ref],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        subprocess.run(["git", "-C", str(repo_dir), "checkout", resolved_sha], check=True, capture_output=True, text=True)

        rendered: Dict[str, Tuple[str, str]] = {}
        for cfg_file in repo_dir.rglob("*.cfg"):
            rel = cfg_file.relative_to(repo_dir).as_posix()
            dev_name = cfg_file.stem
            rendered[dev_name] = (rel, cfg_file.read_text(encoding="utf-8"))
        return resolved_sha, rendered


def main() -> int:
    parser = argparse.ArgumentParser(description="Rollback intended configs to a prior Gitea commit.")
    parser.add_argument("--commit", default="HEAD~1", help="Target Git ref/commit in gc-intended (default: HEAD~1)")
    parser.add_argument("--auto-merge", action="store_true", default=True, help="Auto-merge rollback PR (default: True)")
    parser.add_argument("--dry-run", action="store_true", help="Show rollback diff without deploying")
    parser.add_argument("--run-compliance", action="store_true", help="Run Nautobot Golden Config compliance after rollback")
    args = parser.parse_args()

    nautobot_url = os.environ.get("NAUTOBOT_URL", "http://127.0.0.1:8083")
    nautobot_token = env_or_fail("NAUTOBOT_TOKEN")
    gitea_url = os.environ.get("GITEA_URL", "http://127.0.0.1:3002")
    gitea_org = os.environ.get("GITEA_ORG", "netops")
    gitea_repo = os.environ.get("GITEA_INTENDED_REPO", "gc-intended")
    gitea_user = os.environ.get("GITEA_ADMIN_USER") or os.environ.get("GITEA_USER", "netops-admin")
    gitea_secret = os.environ.get("GITEA_TOKEN") or os.environ.get("GITEA_ADMIN_PASSWORD") or os.environ.get("GITEA_PASSWORD")
    if not gitea_secret:
        raise RuntimeError("GITEA_TOKEN or GITEA_ADMIN_PASSWORD must be set.")

    dev_user = os.environ.get("DEVICE_USERNAME") or os.environ.get("LAB_DEVICE_USERNAME", "admin")
    dev_pass = os.environ.get("DEVICE_PASSWORD") or os.environ.get("LAB_DEVICE_PASSWORD")
    if not dev_pass:
        raise RuntimeError("DEVICE_PASSWORD must be set.")
    dev_secret = os.environ.get("DEVICE_ENABLE_SECRET") or os.environ.get("LAB_DEVICE_SECRET", dev_pass)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    print(f"=== [Rollback 1] Loading intended configs from {gitea_org}/{gitea_repo}@{args.commit} ===")
    resolved_sha, rendered = load_intended_from_commit(gitea_url, gitea_org, gitea_repo, gitea_user, gitea_secret, args.commit)
    if not rendered:
        print(f"No .cfg files found at commit {resolved_sha}", file=sys.stderr)
        return 1
    print(f"  Loaded {len(rendered)} device config(s) from commit {resolved_sha[:10]}: {list(rendered.keys())}")

    lint_ok, lint_msgs = lint_configs(rendered)
    if not lint_ok:
        print(f"Rollback target failed lint: {lint_msgs}", file=sys.stderr)
        return 2

    devices = fetch_sot_devices(nautobot_url, nautobot_token, list(rendered.keys()))

    print("=== [Rollback 2] Computing dry-run diff against live devices ===")
    diff_res = dry_run_and_optional_deploy(devices, rendered, dev_user, dev_pass, dev_secret, deploy=False)
    for dev, res in diff_res.items():
        print(f"--- Rollback diff for {dev} ({res.get('host')}) ---")
        print(res.get("diff"))

    branch = f"rollback-{ts}"
    pr_title = f"Rollback ({ts}) to {resolved_sha[:10]}"
    pr_body = f"Automated rollback restoring intended configs from commit `{resolved_sha}`."
    comment_lines = [f"### Rollback Diff Report (target `{resolved_sha[:10]}`)", ""]
    for dev, res in diff_res.items():
        comment_lines.append(f"#### `{dev}`\n```diff\n{res.get('diff', '')[:3000]}\n```")

    print("=== [Rollback 3] Opening & merging rollback PR in Gitea ===")
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
        auto_merge=args.auto_merge and not args.dry_run,
    )
    print(f"  Rollback PR #{pr_info['pr_number']} ({pr_info['pr_url']}) merged={pr_info['merged']}")

    deploy_res = {}
    if not args.dry_run:
        print("=== [Rollback 4] Re-deploying prior intended configs to live devices ===")
        deploy_res = dry_run_and_optional_deploy(devices, rendered, dev_user, dev_pass, dev_secret, deploy=True)
        for dev, res in deploy_res.items():
            print(f"  Rolled back {dev} ({res.get('host')}): {res.get('command_count')} cmds")

    comp_res = {}
    if args.run_compliance and not args.dry_run:
        print("=== [Rollback 5] Running Nautobot Golden Config Compliance ===")
        comp_res = trigger_golden_config_compliance(nautobot_url, nautobot_token)
        for js in comp_res["jobs"]:
            print(f"  Job {js['job']}: {js['status']}")

    print(
        json.dumps(
            {
                "rollback_target_sha": resolved_sha,
                "pr": pr_info,
                "deploy": deploy_res,
                "compliance": comp_res,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
