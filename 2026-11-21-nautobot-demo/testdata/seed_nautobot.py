#!/usr/bin/env python3
"""Idempotent Nautobot 3.2.9 fixture seeder for the NetOps demo lab.

Reads structured RFC 5737 / lab.internal fixtures from `testdata/lab_fixtures.json`
and populates Nautobot via its REST API. Safe to run repeatedly.

Environment variables (also loaded from repo-root `.env` if present):
  NAUTOBOT_URL    Base URL (default: http://127.0.0.1:8081)
  NAUTOBOT_TOKEN  API token (falls back to NAUTOBOT_SUPERUSER_API_TOKEN)
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import requests


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FIXTURES_PATH = Path(__file__).resolve().parent / "lab_fixtures.json"


def load_dotenv(env_path: Path) -> dict[str, str]:
    """Parse simple KEY=VALUE lines from a .env file without external dependencies."""
    values: dict[str, str] = {}
    if not env_path.is_file():
        return values
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key:
            values[key] = val
    return values


def resolve_connection() -> tuple[str, str]:
    """Resolve Nautobot URL and API token from env vars or repo `.env`."""
    dotenv = load_dotenv(REPO_ROOT / ".env")
    url = (
        os.environ.get("NAUTOBOT_URL")
        or dotenv.get("NAUTOBOT_URL")
        or "http://127.0.0.1:8081"
    ).rstrip("/")
    token = (
        os.environ.get("NAUTOBOT_TOKEN")
        or os.environ.get("NAUTOBOT_SUPERUSER_API_TOKEN")
        or dotenv.get("NAUTOBOT_TOKEN")
        or dotenv.get("NAUTOBOT_SUPERUSER_API_TOKEN")
        or ""
    ).strip()
    if not token:
        raise RuntimeError(
            "No Nautobot API token found. Set NAUTOBOT_TOKEN or "
            "NAUTOBOT_SUPERUSER_API_TOKEN in environment or .env."
        )
    return url, token


class NautobotClient:
    """Thin idempotent REST API client for Nautobot 3.x."""

    def __init__(self, base_url: str, token: str, timeout: int = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Token {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )
        self.stats: dict[str, dict[str, int]] = defaultdict(
            lambda: {"created": 0, "existing": 0, "updated": 0}
        )

    def _url(self, endpoint: str) -> str:
        endpoint = endpoint.strip("/")
        return f"{self.base_url}/api/{endpoint}/"

    def request(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
        allow_404: bool = False,
    ) -> Any:
        url = self._url(endpoint)
        resp = self.session.request(
            method,
            url,
            params=params,
            json=payload,
            timeout=self.timeout,
        )
        if allow_404 and resp.status_code == 404:
            return None
        if not resp.ok:
            # Never log Authorization headers or token values.
            body = resp.text[:600]
            raise RuntimeError(
                f"{method} {url} failed with HTTP {resp.status_code}: {body}"
            )
        if resp.status_code == 204 or not resp.text:
            return {}
        return resp.json()

    def list_objects(
        self, endpoint: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        query = dict(params or {})
        query.setdefault("limit", 250)
        data = self.request("GET", endpoint, params=query)
        return data.get("results", [])

    def find_exact(
        self,
        endpoint: str,
        match_fields: dict[str, Any],
        query_params: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        results = self.list_objects(endpoint, params=query_params or match_fields)
        for item in results:
            matched = True
            for key, expected in match_fields.items():
                actual = item.get(key)
                if isinstance(actual, dict) and "id" in actual:
                    actual_val = actual["id"]
                else:
                    actual_val = actual
                if actual_val != expected:
                    matched = False
                    break
            if matched:
                return item
        return None

    def get_or_create(
        self,
        label: str,
        endpoint: str,
        match_fields: dict[str, Any],
        payload: dict[str, Any],
        query_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        existing = self.find_exact(endpoint, match_fields, query_params=query_params)
        if existing is not None:
            self.stats[label]["existing"] += 1
            return existing
        created = self.request("POST", endpoint, payload=payload)
        self.stats[label]["created"] += 1
        return created

    def patch_object(
        self, label: str, endpoint: str, obj_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        updated = self.request("PATCH", f"{endpoint.strip('/')}/{obj_id}", payload=payload)
        self.stats[label]["updated"] += 1
        return updated


def ensure_location_assignment(
    client: NautobotClient,
    label: str,
    assignment_endpoint: str,
    parent_endpoint: str,
    parent_field: str,
    parent_id: str,
    location_id: str,
) -> None:
    """Attach a Prefix or VLAN to a Location using Nautobot 3.x M2M assignment endpoints."""
    probe = client.request(
        "GET",
        assignment_endpoint,
        params={parent_field: parent_id, "location": location_id},
        allow_404=True,
    )
    if probe is not None:
        results = probe.get("results", [])
        for row in results:
            p_val = row.get(parent_field)
            l_val = row.get("location")
            p_id = p_val["id"] if isinstance(p_val, dict) else p_val
            l_id = l_val["id"] if isinstance(l_val, dict) else l_val
            if p_id == parent_id and l_id == location_id:
                client.stats[label]["existing"] += 1
                return
        client.request(
            "POST",
            assignment_endpoint,
            payload={parent_field: parent_id, "location": location_id},
        )
        client.stats[label]["created"] += 1
        return

    # Fallback for single-FK location field if assignment endpoint is absent.
    client.patch_object(label, parent_endpoint, parent_id, {"location": location_id})


def seed(fixtures_path: Path = DEFAULT_FIXTURES_PATH) -> int:
    url, token = resolve_connection()
    fixtures = json.loads(fixtures_path.read_text(encoding="utf-8"))
    client = NautobotClient(url, token)

    print(f"Seeding Nautobot at {url} from {fixtures_path.name} ...")

    # Verify API connectivity and resolve built-in Status & Namespace
    status_active = client.find_exact("extras/statuses", {"name": "Active"})
    if not status_active:
        raise RuntimeError("Built-in Status 'Active' not found in Nautobot.")
    active_status_id = status_active["id"]

    ns_global = client.find_exact("ipam/namespaces", {"name": "Global"})
    if not ns_global:
        raise RuntimeError("Built-in Namespace 'Global' not found in Nautobot.")
    global_ns_id = ns_global["id"]

    # 1. Location Types
    location_types: dict[str, str] = {}
    for lt in fixtures["location_types"]:
        payload: dict[str, Any] = {
            "name": lt["name"],
            "description": lt.get("description", ""),
            "nestable": lt.get("nestable", False),
            "content_types": lt.get("content_types", []),
        }
        if lt.get("parent"):
            payload["parent"] = location_types[lt["parent"]]
        obj = client.get_or_create(
            "location_types",
            "dcim/location-types",
            {"name": lt["name"]},
            payload,
        )
        location_types[lt["name"]] = obj["id"]

    # 2. Locations
    locations: dict[str, str] = {}
    for loc in fixtures["locations"]:
        payload = {
            "name": loc["name"],
            "location_type": location_types[loc["location_type"]],
            "status": active_status_id,
            "description": loc.get("description", ""),
        }
        if loc.get("parent"):
            payload["parent"] = locations[loc["parent"]]
        if loc.get("facility"):
            payload["facility"] = loc["facility"]
        obj = client.get_or_create(
            "locations",
            "dcim/locations",
            {"name": loc["name"]},
            payload,
        )
        locations[loc["name"]] = obj["id"]

    # 3. Manufacturers
    manufacturers: dict[str, str] = {}
    for mfg in fixtures["manufacturers"]:
        obj = client.get_or_create(
            "manufacturers",
            "dcim/manufacturers",
            {"name": mfg["name"]},
            {"name": mfg["name"], "description": mfg.get("description", "")},
        )
        manufacturers[mfg["name"]] = obj["id"]

    # 4. Platforms
    platforms: dict[str, str] = {}
    for plat in fixtures["platforms"]:
        payload = {
            "name": plat["name"],
            "manufacturer": manufacturers[plat["manufacturer"]],
            "network_driver": plat.get("network_driver", ""),
            "description": plat.get("description", ""),
        }
        obj = client.get_or_create(
            "platforms",
            "dcim/platforms",
            {"name": plat["name"]},
            payload,
        )
        platforms[plat["name"]] = obj["id"]

    # 5. Device Types
    device_types: dict[str, str] = {}
    for dt in fixtures["device_types"]:
        payload = {
            "model": dt["model"],
            "manufacturer": manufacturers[dt["manufacturer"]],
            "u_height": dt.get("u_height", 1),
            "is_full_depth": dt.get("is_full_depth", False),
            "part_number": dt.get("part_number", ""),
            "comments": dt.get("comments", ""),
        }
        obj = client.get_or_create(
            "device_types",
            "dcim/device-types",
            {"model": dt["model"]},
            payload,
        )
        device_types[dt["model"]] = obj["id"]

    # 6. Roles
    roles: dict[str, str] = {}
    for role in fixtures["roles"]:
        payload = {
            "name": role["name"],
            "color": role.get("color", "9e9e9e"),
            "description": role.get("description", ""),
            "content_types": role.get("content_types", []),
        }
        obj = client.get_or_create(
            "roles",
            "extras/roles",
            {"name": role["name"]},
            payload,
        )
        roles[role["name"]] = obj["id"]

    # 7. Tags
    tags: dict[str, str] = {}
    for tag in fixtures["tags"]:
        payload = {
            "name": tag["name"],
            "color": tag.get("color", "9e9e9e"),
            "description": tag.get("description", ""),
            "content_types": tag.get("content_types", []),
        }
        obj = client.get_or_create(
            "tags",
            "extras/tags",
            {"name": tag["name"]},
            payload,
        )
        tags[tag["name"]] = obj["id"]

    # 8. Custom Fields & Select Choices
    for cf in fixtures["custom_fields"]:
        payload = {
            "key": cf["key"],
            "label": cf["label"],
            "type": cf["type"],
            "description": cf.get("description", ""),
            "required": cf.get("required", False),
            "content_types": cf.get("content_types", []),
        }
        cf_obj = client.get_or_create(
            "custom_fields",
            "extras/custom-fields",
            {"key": cf["key"]},
            payload,
            query_params={"label": cf["label"]},
        )
        if cf.get("choices"):
            for idx, choice_val in enumerate(cf["choices"], start=1):
                client.get_or_create(
                    "custom_field_choices",
                    "extras/custom-field-choices",
                    {"custom_field": cf_obj["id"], "value": choice_val},
                    {
                        "custom_field": cf_obj["id"],
                        "value": choice_val,
                        "weight": idx * 100,
                    },
                    query_params={"custom_field": cf_obj["id"]},
                )

    # 9. VLANs
    vlans: dict[str, str] = {}
    for vlan in fixtures["vlans"]:
        payload = {
            "vid": vlan["vid"],
            "name": vlan["name"],
            "status": active_status_id,
            "role": roles[vlan["role"]],
            "description": vlan.get("description", ""),
            "tags": [tags[t] for t in vlan.get("tags", [])],
        }
        obj = client.get_or_create(
            "vlans",
            "ipam/vlans",
            {"vid": vlan["vid"], "name": vlan["name"]},
            payload,
            query_params={"vid": vlan["vid"]},
        )
        vlans[vlan["name"]] = obj["id"]
        if vlan.get("location"):
            ensure_location_assignment(
                client,
                "vlan_locations",
                "ipam/vlan-location-assignments",
                "ipam/vlans",
                "vlan",
                obj["id"],
                locations[vlan["location"]],
            )

    # 10. Prefixes (strictly RFC 5737)
    for pfx in fixtures["prefixes"]:
        payload = {
            "prefix": pfx["prefix"],
            "namespace": global_ns_id,
            "type": pfx.get("type", "network"),
            "status": active_status_id,
            "role": roles[pfx["role"]],
            "description": pfx.get("description", ""),
            "custom_fields": pfx.get("custom_fields", {}),
            "tags": [tags[t] for t in pfx.get("tags", [])],
        }
        if pfx.get("vlan"):
            payload["vlan"] = vlans[pfx["vlan"]]
        obj = client.get_or_create(
            "prefixes",
            "ipam/prefixes",
            {"prefix": pfx["prefix"]},
            payload,
            query_params={"prefix": pfx["prefix"], "namespace": global_ns_id},
        )
        if pfx.get("location"):
            ensure_location_assignment(
                client,
                "prefix_locations",
                "ipam/prefix-location-assignments",
                "ipam/prefixes",
                "prefix",
                obj["id"],
                locations[pfx["location"]],
            )

    # 11. Devices, Interfaces, IP Addresses, IP-to-Interface & Primary IPv4
    for dev in fixtures["devices"]:
        dev_payload = {
            "name": dev["name"],
            "device_type": device_types[dev["device_type"]],
            "role": roles[dev["role"]],
            "platform": platforms[dev["platform"]],
            "location": locations[dev["location"]],
            "status": active_status_id,
            "serial": dev.get("serial", ""),
            "comments": dev.get("comments", ""),
            "custom_fields": dev.get("custom_fields", {}),
            "tags": [tags[t] for t in dev.get("tags", [])],
        }
        dev_obj = client.get_or_create(
            "devices",
            "dcim/devices",
            {"name": dev["name"]},
            dev_payload,
        )
        dev_id = dev_obj["id"]
        primary_ip4_id: str | None = None

        for iface in dev.get("interfaces", []):
            iface_payload = {
                "device": dev_id,
                "name": iface["name"],
                "type": iface["type"],
                "status": active_status_id,
                "enabled": iface.get("enabled", True),
                "description": iface.get("description", ""),
            }
            iface_obj = client.get_or_create(
                "interfaces",
                "dcim/interfaces",
                {"device": dev_id, "name": iface["name"]},
                iface_payload,
                query_params={"device_id": dev_id, "name": iface["name"]},
            )
            iface_id = iface_obj["id"]

            if iface.get("ip_address"):
                ip_addr = iface["ip_address"]
                ip_payload = {
                    "address": ip_addr,
                    "namespace": global_ns_id,
                    "status": active_status_id,
                    "type": "host",
                    "dns_name": dev["name"] if iface.get("is_primary_ip4") else "",
                    "description": f"{dev['name']} {iface['name']}",
                    "tags": [tags["managed-by-nautobot"]],
                }
                ip_obj = client.get_or_create(
                    "ip_addresses",
                    "ipam/ip-addresses",
                    {"address": ip_addr},
                    ip_payload,
                    query_params={"address": ip_addr, "namespace": global_ns_id},
                )
                ip_id = ip_obj["id"]

                client.get_or_create(
                    "ip_to_interface",
                    "ipam/ip-address-to-interface",
                    {"ip_address": ip_id, "interface": iface_id},
                    {"ip_address": ip_id, "interface": iface_id},
                    query_params={"ip_address": ip_id, "interface": iface_id},
                )
                if iface.get("is_primary_ip4"):
                    primary_ip4_id = ip_id

        if primary_ip4_id:
            current_primary = dev_obj.get("primary_ip4")
            current_id = (
                current_primary["id"]
                if isinstance(current_primary, dict)
                else current_primary
            )
            if current_id != primary_ip4_id:
                client.patch_object(
                    "device_primary_ip4",
                    "dcim/devices",
                    dev_id,
                    {"primary_ip4": primary_ip4_id},
                )

    # 12. Circuits: Providers, Types, Circuits, Terminations
    providers: dict[str, str] = {}
    for prov in fixtures["circuit_providers"]:
        payload = {
            "name": prov["name"],
            "asn": prov.get("asn"),
            "account": prov.get("account", ""),
            "comments": prov.get("comments", ""),
        }
        obj = client.get_or_create(
            "circuit_providers",
            "circuits/providers",
            {"name": prov["name"]},
            payload,
        )
        providers[prov["name"]] = obj["id"]

    circuit_types: dict[str, str] = {}
    for ctype in fixtures["circuit_types"]:
        obj = client.get_or_create(
            "circuit_types",
            "circuits/circuit-types",
            {"name": ctype["name"]},
            {"name": ctype["name"], "description": ctype.get("description", "")},
        )
        circuit_types[ctype["name"]] = obj["id"]

    for ckt in fixtures["circuits"]:
        payload = {
            "cid": ckt["cid"],
            "provider": providers[ckt["provider"]],
            "circuit_type": circuit_types[ckt["circuit_type"]],
            "status": active_status_id,
            "commit_rate": ckt.get("commit_rate"),
            "description": ckt.get("description", ""),
            "tags": [tags[t] for t in ckt.get("tags", [])],
        }
        ckt_obj = client.get_or_create(
            "circuits",
            "circuits/circuits",
            {"cid": ckt["cid"]},
            payload,
        )
        ckt_id = ckt_obj["id"]
        for term in ckt.get("terminations", []):
            term_payload = {
                "circuit": ckt_id,
                "term_side": term["term_side"],
                "location": locations[term["location"]],
                "port_speed": term.get("port_speed"),
                "description": term.get("description", ""),
            }
            client.get_or_create(
                "circuit_terminations",
                "circuits/circuit-terminations",
                {"circuit": ckt_id, "term_side": term["term_side"]},
                term_payload,
                query_params={"circuit": ckt_id, "term_side": term["term_side"]},
            )

    # 13. Global Config Contexts
    for cc in fixtures["config_contexts"]:
        payload = {
            "name": cc["name"],
            "weight": cc.get("weight", 1000),
            "is_active": cc.get("is_active", True),
            "description": cc.get("description", ""),
            "data": cc["data"],
        }
        client.get_or_create(
            "config_contexts",
            "extras/config-contexts",
            {"name": cc["name"]},
            payload,
        )

    print("\nSeed summary:")
    print(f"{'Resource':<24} {'Created':>8} {'Existing':>10} {'Updated':>9}")
    print("-" * 55)
    for resource, counts in client.stats.items():
        print(
            f"{resource:<24} {counts['created']:>8} {counts['existing']:>10} {counts['updated']:>9}"
        )
    print("Seeding completed successfully.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(seed())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
