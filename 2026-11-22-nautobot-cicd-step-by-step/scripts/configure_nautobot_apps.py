#!/usr/bin/env python3
"""
Configure Gitea repositories and Nautobot 3.2 apps for the Nautobot CI/CD lab:
- Gitea org 'netops' and repos: gc-templates, gc-intended, gc-backups, network-cicd
- Push templates/ to gc-templates and pipeline/ + templates/ to network-cicd
- Nautobot Secrets + SecretsGroups (LAB-DEVICE-CREDS, GITEA-GIT-CREDS) via environment-variable provider
- Nautobot Git Repositories (Templates, Intended, Backups) + sync
- Nautobot Saved GraphQL Query for Golden Config SoT aggregation
- GoldenConfigSetting, ComplianceFeature, ComplianceRule, RemediationSetting
- Assign LAB-DEVICE-CREDS to lab devices
- Register Nautobot Webhook pointing to http://ci-runner:8086/webhook/nautobot
"""

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urlunparse

import requests
import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent


def env_required(name: str, default: Optional[str] = None) -> str:
    val = os.environ.get(name, default)
    if not val:
        raise RuntimeError(f"Required environment variable {name} is not set.")
    return val


class GiteaClient:
    def __init__(self, base_url: str, user: str, password: Optional[str] = None, token: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.user = user
        self.password = password
        self.token = token
        self.session = requests.Session()
        if token:
            self.session.headers["Authorization"] = f"token {token}"
        elif password:
            self.session.auth = (user, password)
        self.session.headers["Content-Type"] = "application/json"

    def _req(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{self.base_url}/api/v1{path}"
        resp = self.session.request(method, url, timeout=30, **kwargs)
        return resp

    def ensure_org(self, org: str, full_name: str = "NetOps Automation") -> Dict[str, Any]:
        r = self._req("GET", f"/orgs/{org}")
        if r.status_code == 200:
            print(f"[gitea] Org '{org}' already exists")
            return r.json()
        r = self._req(
            "POST",
            "/orgs",
            json={"username": org, "full_name": full_name, "visibility": "public"},
        )
        r.raise_for_status()
        print(f"[gitea] Created org '{org}'")
        return r.json()

    def ensure_repo(self, org: str, name: str, description: str) -> Dict[str, Any]:
        r = self._req("GET", f"/repos/{org}/{name}")
        if r.status_code == 200:
            print(f"[gitea] Repo '{org}/{name}' already exists")
            return r.json()
        r = self._req(
            "POST",
            f"/orgs/{org}/repos",
            json={
                "name": name,
                "description": description,
                "private": False,
                "auto_init": True,
                "default_branch": "main",
            },
        )
        r.raise_for_status()
        print(f"[gitea] Created repo '{org}/{name}'")
        return r.json()


def push_directory_to_gitea(
    gitea_url: str,
    org: str,
    repo: str,
    user: str,
    secret: str,
    source_map: Dict[Path, str],
    commit_msg: str,
) -> None:
    """Clone repo from Gitea, sync files from source_map {src_path: dest_rel}, commit & push if changed."""
    proto, rest = gitea_url.rstrip("/").split("://", 1)
    auth_url = f"{proto}://{user}:{secret}@{rest}/{org}/{repo}.git"

    with tempfile.TemporaryDirectory(prefix=f"gitea-{repo}-") as tmpdir:
        tmp = Path(tmpdir)
        clone = subprocess.run(
            ["git", "clone", "--branch", "main", auth_url, str(tmp / "repo")],
            capture_output=True,
            text=True,
        )
        if clone.returncode != 0:
            # Repo might have empty main branch; clone without --branch
            subprocess.run(
                ["git", "clone", auth_url, str(tmp / "repo")],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "-C", str(tmp / "repo"), "checkout", "-B", "main"],
                check=True,
                capture_output=True,
                text=True,
            )

        repo_dir = tmp / "repo"
        subprocess.run(["git", "-C", str(repo_dir), "config", "user.name", "NetOps CI"], check=True)
        subprocess.run(["git", "-C", str(repo_dir), "config", "user.email", "netops@lab.internal"], check=True)

        for src, rel_dest in source_map.items():
            dest = repo_dir / rel_dest if rel_dest else repo_dir
            if src.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
                for item in src.rglob("*"):
                    if item.is_file() and "__pycache__" not in item.parts:
                        rel = item.relative_to(src)
                        target = dest / rel
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(item, target)
            elif src.is_file():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)

        subprocess.run(["git", "-C", str(repo_dir), "add", "-A"], check=True)
        status = subprocess.run(
            ["git", "-C", str(repo_dir), "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        )
        if not status.stdout.strip():
            print(f"[gitea] Repo '{org}/{repo}' already up to date")
            return

        subprocess.run(["git", "-C", str(repo_dir), "commit", "-m", commit_msg], check=True, capture_output=True, text=True)
        subprocess.run(["git", "-C", str(repo_dir), "push", "origin", "main"], check=True, capture_output=True, text=True)
        print(f"[gitea] Pushed updates to '{org}/{repo}' (main)")


class NautobotClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Token {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        r = self.session.get(f"{self.base_url}/api{path}", params=params, timeout=30)
        r.raise_for_status()
        return r.json()

    def post(self, path: str, payload: Dict[str, Any]) -> Any:
        r = self.session.post(f"{self.base_url}/api{path}", json=payload, timeout=60)
        if not r.ok:
            raise RuntimeError(f"POST {path} failed ({r.status_code}): {r.text}")
        return r.json()

    def patch(self, path: str, payload: Dict[str, Any]) -> Any:
        r = self.session.patch(f"{self.base_url}/api{path}", json=payload, timeout=60)
        if not r.ok:
            raise RuntimeError(f"PATCH {path} failed ({r.status_code}): {r.text}")
        return r.json()

    def ensure_by_name(self, path: str, name: str, payload: Dict[str, Any], name_field: str = "name") -> Dict[str, Any]:
        existing = self.get(path, params={name_field: name})
        results = existing.get("results", [])
        # Exact match check
        for obj in results:
            if obj.get(name_field) == name:
                updated = self.patch(f"{path}{obj['id']}/", payload)
                print(f"[nautobot] Updated {path} '{name}' ({obj['id'][:8]})")
                return updated
        created = self.post(path, payload)
        print(f"[nautobot] Created {path} '{name}' ({created['id'][:8]})")
        return created


GOLDEN_CONFIG_GRAPHQL_QUERY = """query ($device_id: ID!) {
  device(id: $device_id) {
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


def configure_secrets(nb: NautobotClient, gitea_secret_dir: str = "/opt/nautobot/git") -> Dict[str, Dict[str, Any]]:
    """Create environment-variable Secrets (devices) and text-file Secrets (Gitea) + SecretsGroups."""
    env_secret_specs = [
        ("DEVICE_USERNAME", "DEVICE_USERNAME", "Lab router SSH username"),
        ("DEVICE_PASSWORD", "DEVICE_PASSWORD", "Lab router SSH password"),
        ("DEVICE_ENABLE_SECRET", "DEVICE_ENABLE_SECRET", "Lab router enable secret"),
    ]
    secrets: Dict[str, Dict[str, Any]] = {}
    for name, env_var, desc in env_secret_specs:
        secrets[name] = nb.ensure_by_name(
            "/extras/secrets/",
            name,
            {
                "name": name,
                "provider": "environment-variable",
                "parameters": {"variable": env_var},
                "description": desc,
            },
        )

    file_secret_specs = [
        ("GITEA_USERNAME", f"{gitea_secret_dir}/.gitea_user", "Gitea HTTP username"),
        ("GITEA_TOKEN_SECRET", f"{gitea_secret_dir}/.gitea_token", "Gitea HTTP token"),
    ]
    for name, path_val, desc in file_secret_specs:
        secrets[name] = nb.ensure_by_name(
            "/extras/secrets/",
            name,
            {
                "name": name,
                "provider": "text-file",
                "parameters": {"path": path_val},
                "description": desc,
            },
        )

    dev_group = nb.ensure_by_name(
        "/extras/secrets-groups/",
        "LAB-DEVICE-CREDS",
        {"name": "LAB-DEVICE-CREDS", "description": "SSH/enable credentials for lab Arista and Cisco devices"},
    )
    git_group = nb.ensure_by_name(
        "/extras/secrets-groups/",
        "GITEA-GIT-CREDS",
        {"name": "GITEA-GIT-CREDS", "description": "HTTP credentials for local Gitea repositories"},
    )

    associations = [
        (dev_group["id"], secrets["DEVICE_USERNAME"]["id"], "Generic", "username"),
        (dev_group["id"], secrets["DEVICE_PASSWORD"]["id"], "Generic", "password"),
        (dev_group["id"], secrets["DEVICE_ENABLE_SECRET"]["id"], "Generic", "secret"),
        (git_group["id"], secrets["GITEA_USERNAME"]["id"], "HTTP(S)", "username"),
        (git_group["id"], secrets["GITEA_TOKEN_SECRET"]["id"], "HTTP(S)", "token"),
    ]
    existing_assocs = nb.get("/extras/secrets-groups-associations/", params={"limit": 200}).get("results", [])
    for group_id, secret_id, access_type, secret_type in associations:
        found = any(
            a["secrets_group"]["id"] == group_id
            and a["access_type"] == access_type
            and a["secret_type"] == secret_type
            for a in existing_assocs
        )
        if not found:
            nb.post(
                "/extras/secrets-groups-associations/",
                {
                    "secrets_group": group_id,
                    "secret": secret_id,
                    "access_type": access_type,
                    "secret_type": secret_type,
                },
            )
            print(f"[nautobot] Linked secret ({access_type}/{secret_type}) to group {group_id[:8]}")

    return {"device": dev_group, "git": git_group}


def configure_git_repos(
    nb: NautobotClient,
    gitea_internal_url: str,
    org: str,
    git_group_id: str,
) -> Dict[str, Dict[str, Any]]:
    repos_spec = [
        (
            "templates",
            "Golden Config Templates",
            f"{gitea_internal_url.rstrip('/')}/{org}/gc-templates.git",
            ["nautobot_golden_config.jinjatemplate"],
        ),
        (
            "intended",
            "Golden Config Intended",
            f"{gitea_internal_url.rstrip('/')}/{org}/gc-intended.git",
            ["nautobot_golden_config.intendedconfigs"],
        ),
        (
            "backups",
            "Golden Config Backups",
            f"{gitea_internal_url.rstrip('/')}/{org}/gc-backups.git",
            ["nautobot_golden_config.backupconfigs"],
        ),
    ]
    result: Dict[str, Dict[str, Any]] = {}
    for key, name, remote_url, provides in repos_spec:
        repo = nb.ensure_by_name(
            "/extras/git-repositories/",
            name,
            {
                "name": name,
                "remote_url": remote_url,
                "branch": "main",
                "secrets_group": git_group_id,
                "provided_contents": provides,
            },
        )
        result[key] = repo
        # Trigger sync
        try:
            nb.post(f"/extras/git-repositories/{repo['id']}/sync/", {})
            print(f"[nautobot] Triggered Git sync for '{name}'")
        except Exception as exc:
            print(f"[nautobot] Warning: Git sync trigger for '{name}' returned: {exc}")
    return result


def configure_golden_config(
    nb: NautobotClient,
    git_repos: Dict[str, Dict[str, Any]],
) -> None:
    # 1. Saved GraphQL query
    gql = nb.ensure_by_name(
        "/extras/graphql-queries/",
        "Golden Config Lab Query",
        {
            "name": "Golden Config Lab Query",
            "query": GOLDEN_CONFIG_GRAPHQL_QUERY,
        },
    )

    # 2. GoldenConfigSetting (update default or create 'Lab Golden Config')
    settings_list = nb.get("/plugins/golden-config/golden-config-settings/").get("results", [])
    gc_payload = {
        "name": "Lab Golden Config",
        "weight": 1000,
        "description": "Golden Config settings for Arista cEOS and Cisco lab devices",
        "backup_repository": git_repos["backups"]["id"],
        "backup_path_template": "{{ obj.location.name }}/{{ obj.name }}.cfg",
        "intended_repository": git_repos["intended"]["id"],
        "intended_path_template": "{{ obj.location.name }}/{{ obj.name }}.cfg",
        "jinja_repository": git_repos["templates"]["id"],
        "jinja_path_template": "main.j2",
        "backup_test_connectivity": False,
        "sot_agg_query": gql["id"],
        "enable_backup": True,
        "enable_intended": True,
        "enable_sotagg": True,
        "enable_compliance": True,
        "enable_plan": True,
        "enable_deploy": True,
    }
    if settings_list:
        target = settings_list[0]
        nb.patch(f"/plugins/golden-config/golden-config-settings/{target['id']}/", gc_payload)
        print(f"[nautobot] Updated GoldenConfigSetting '{target['name']}' -> 'Lab Golden Config'")
    else:
        nb.post("/plugins/golden-config/golden-config-settings/", gc_payload)
        print("[nautobot] Created GoldenConfigSetting 'Lab Golden Config'")

    # 3. Platforms lookup
    platforms_raw = nb.get("/dcim/platforms/", params={"limit": 100}).get("results", [])
    platforms_by_key: Dict[str, Dict[str, Any]] = {}
    for p in platforms_raw:
        if p.get("network_driver"):
            platforms_by_key[p["network_driver"].lower()] = p
        if p.get("name"):
            platforms_by_key[p["name"].lower()] = p

    # 4. ComplianceFeature and ComplianceRule from templates/compliance_features.yaml
    features_file = REPO_ROOT / "templates" / "compliance_features.yaml"
    spec = yaml.safe_load(features_file.read_text(encoding="utf-8"))
    existing_rules = nb.get("/plugins/golden-config/compliance-rule/", params={"limit": 200}).get("results", [])

    for feat in spec.get("features", []):
        cf = nb.ensure_by_name(
            "/plugins/golden-config/compliance-feature/",
            feat["name"],
            {
                "name": feat["name"],
                "slug": feat["slug"],
                "description": feat.get("description", ""),
            },
        )
        for plat_key, rule_cfg in feat.get("rules", {}).items():
            plat = platforms_by_key.get(plat_key.lower())
            if not plat:
                print(f"[nautobot] Skipping ComplianceRule {feat['name']}/{plat_key} (platform not in Nautobot)")
                continue
            rule_payload = {
                "feature": cf["id"],
                "platform": plat["id"],
                "description": f"{feat['name']} compliance for {plat['name']}",
                "config_ordered": rule_cfg.get("config_ordered", False),
                "config_remediation": True,
                "match_config": rule_cfg["match_config"].strip(),
                "config_type": rule_cfg.get("config_type", "cli"),
            }
            match = next(
                (
                    r
                    for r in existing_rules
                    if r["feature"]["id"] == cf["id"] and r["platform"]["id"] == plat["id"]
                ),
                None,
            )
            if match:
                nb.patch(f"/plugins/golden-config/compliance-rule/{match['id']}/", rule_payload)
                print(f"[nautobot] Updated ComplianceRule {feat['name']} / {plat['name']}")
            else:
                nb.post("/plugins/golden-config/compliance-rule/", rule_payload)
                print(f"[nautobot] Created ComplianceRule {feat['name']} / {plat['name']}")

    # 5. RemediationSetting per platform (HierConfig)
    existing_rem = nb.get("/plugins/golden-config/remediation-setting/", params={"limit": 100}).get("results", [])
    seen_plat_ids = set()
    for plat in platforms_raw:
        if plat["id"] in seen_plat_ids:
            continue
        seen_plat_ids.add(plat["id"])
        rem_payload = {
            "platform": plat["id"],
            "remediation_type": "hierconfig",
            "remediation_options": {},
        }
        match = next((r for r in existing_rem if r["platform"]["id"] == plat["id"]), None)
        if match:
            nb.patch(f"/plugins/golden-config/remediation-setting/{match['id']}/", rem_payload)
            print(f"[nautobot] Updated RemediationSetting for {plat['name']}")
        else:
            nb.post("/plugins/golden-config/remediation-setting/", rem_payload)
            print(f"[nautobot] Created RemediationSetting for {plat['name']}")


def assign_device_secrets_group(nb: NautobotClient, dev_group_id: str) -> None:
    devices = nb.get("/dcim/devices/", params={"limit": 100}).get("results", [])
    for dev in devices:
        current = dev.get("secrets_group")
        if current and current.get("id") == dev_group_id:
            continue
        nb.patch(f"/dcim/devices/{dev['id']}/", {"secrets_group": dev_group_id})
        print(f"[nautobot] Assigned LAB-DEVICE-CREDS to device '{dev['name']}'")


def configure_webhook(nb: NautobotClient, receiver_url: str) -> None:
    parsed = urlparse(receiver_url)
    if parsed.hostname and "." not in parsed.hostname:
        try:
            resolved_ip = socket.gethostbyname(parsed.hostname)
            netloc = f"{resolved_ip}:{parsed.port}" if parsed.port else resolved_ip
            receiver_url = urlunparse(parsed._replace(netloc=netloc))
            print(f"[nautobot] Resolved single-label webhook host '{parsed.hostname}' -> {receiver_url}")
        except OSError:
            pass
    payload = {
        "name": "ci-pipeline-sot-trigger",
        "content_types": [
            "ipam.vlan",
            "ipam.prefix",
            "ipam.ipaddress",
            "dcim.interface",
            "dcim.device",
        ],
        "enabled": True,
        "type_create": True,
        "type_update": True,
        "type_delete": True,
        "payload_url": receiver_url,
        "http_method": "POST",
        "http_content_type": "application/json",
        "ssl_verification": False,
    }
    nb.ensure_by_name("/extras/webhooks/", "ci-pipeline-sot-trigger", payload)


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure Gitea & Nautobot apps for the CI/CD lab.")
    parser.add_argument("--skip-gitea", action="store_true", help="Skip Gitea org/repo creation and git push")
    parser.add_argument("--skip-nautobot", action="store_true", help="Skip Nautobot app configuration")
    args = parser.parse_args()

    nautobot_url = os.environ.get("NAUTOBOT_URL", "http://127.0.0.1:8083")
    gitea_url = os.environ.get("GITEA_URL", "http://127.0.0.1:3002")
    gitea_internal_url = os.environ.get("GITEA_INTERNAL_URL", "http://gitea:3000")
    gitea_org = os.environ.get("GITEA_ORG", "netops")
    gitea_user = os.environ.get("GITEA_ADMIN_USER") or os.environ.get("GITEA_USER", "netops-admin")
    gitea_token = os.environ.get("GITEA_TOKEN")
    gitea_password = os.environ.get("GITEA_ADMIN_PASSWORD") or os.environ.get("GITEA_PASSWORD")
    webhook_url = os.environ.get("WEBHOOK_RECEIVER_URL", "http://ci-runner:8086/webhook/nautobot")

    if not args.skip_gitea:
        git_secret = gitea_token or gitea_password
        if not git_secret:
            raise RuntimeError("Set GITEA_TOKEN or GITEA_PASSWORD in the environment.")
        gitea = GiteaClient(gitea_url, gitea_user, password=gitea_password, token=gitea_token)
        gitea.ensure_org(gitea_org)
        gitea.ensure_repo(gitea_org, "gc-templates", "Nautobot Golden Config Jinja2 templates")
        gitea.ensure_repo(gitea_org, "gc-intended", "Nautobot Golden Config rendered intended configs")
        gitea.ensure_repo(gitea_org, "gc-backups", "Nautobot Golden Config device running-config backups")
        gitea.ensure_repo(gitea_org, "network-cicd", "Network CI/CD pipeline code and intended configs")

        push_directory_to_gitea(
            gitea_url,
            gitea_org,
            "gc-templates",
            gitea_user,
            git_secret,
            {REPO_ROOT / "templates": ""},
            "Sync Jinja2 intended-config templates and compliance features",
        )
        push_directory_to_gitea(
            gitea_url,
            gitea_org,
            "network-cicd",
            gitea_user,
            git_secret,
            {
                REPO_ROOT / "templates": "templates",
                REPO_ROOT / "pipeline": "pipeline",
            },
            "Sync CI/CD pipeline and templates",
        )

    if not args.skip_nautobot:
        nautobot_token = env_required("NAUTOBOT_TOKEN")
        nb = NautobotClient(nautobot_url, nautobot_token)
        groups = configure_secrets(nb)
        git_repos = configure_git_repos(nb, gitea_internal_url, gitea_org, groups["git"]["id"])
        configure_golden_config(nb, git_repos)
        assign_device_secrets_group(nb, groups["device"]["id"])
        configure_webhook(nb, webhook_url)

    print("[done] Nautobot apps & Gitea configuration complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
