#!/usr/bin/env python3
"""
Idempotent Nautobot 3.2.x REST API seed script for the Nautobot CI/CD lab.

Usage:
  export NAUTOBOT_URL="http://127.0.0.1:8083"
  export NAUTOBOT_TOKEN="<token>"

  # 1) Seed foundation SoT objects (before Device Onboarding):
  python3 testdata/seed_nautobot.py

  # 2) After Device Onboarding discovers live devices, enrich them:
  python3 testdata/seed_nautobot.py --post-onboard

  # Alternative: seed everything including devices/interfaces/IPs directly:
  python3 testdata/seed_nautobot.py --include-devices

  # Apply or revert the planned SoT CI/CD demo change fixture:
  python3 testdata/seed_nautobot.py --apply-demo-change
  python3 testdata/seed_nautobot.py --revert-demo-change
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import requests
import yaml


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_FIXTURES = BASE_DIR / "fixtures.yaml"
DEFAULT_CONTEXT_FILE = BASE_DIR / "config_contexts" / "global_services.json"


class NautobotClient:
    def __init__(self, base_url: str, token: str, verify_ssl: bool = False) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}/api"
        self.session = requests.Session()
        self.session.verify = verify_ssl
        self.session.headers.update(
            {
                "Authorization": f"Token {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

    def _url(self, path: str) -> str:
        path = path.lstrip("/")
        if not path.endswith("/") and "?" not in path:
            path += "/"
        return f"{self.api_url}/{path}"

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = self._url(path)
        resp = self.session.request(method, url, timeout=30, **kwargs)
        if not resp.ok:
            raise RuntimeError(
                f"Nautobot API {method} {url} failed ({resp.status_code}): {resp.text}"
            )
        if resp.status_code == 204 or not resp.text:
            return None
        return resp.json()

    def get_list(self, path: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        data = self.request("GET", path, params=params or {})
        if isinstance(data, dict) and "results" in data:
            return data["results"]
        return data if isinstance(data, list) else []

    def get_one(self, path: str, params: dict[str, Any]) -> dict[str, Any] | None:
        results = self.get_list(path, params=params)
        return results[0] if results else None

    def ensure(
        self,
        path: str,
        lookup: dict[str, Any],
        payload: dict[str, Any],
        update_existing: bool = False,
        label: str = "",
    ) -> dict[str, Any]:
        existing = self.get_one(path, lookup)
        if existing:
            if update_existing:
                updated = self.request("PATCH", f"{path.rstrip('/')}/{existing['id']}/", json=payload)
                print(f"  [updated] {label or path}: {lookup}")
                return updated
            print(f"  [exists]  {label or path}: {lookup}")
            return existing
        created = self.request("POST", path, json=payload)
        print(f"  [created] {label or path}: {lookup}")
        return created


def seed_foundation(
    nb: NautobotClient,
    fixtures: dict[str, Any],
    global_ctx_data: dict[str, Any],
) -> dict[str, Any]:
    """Seed LocationTypes, Locations, Manufacturers, Platforms, Roles, DeviceTypes, VLANs, Prefixes, ConfigContexts."""
    ids: dict[str, Any] = {
        "location_types": {},
        "locations": {},
        "manufacturers": {},
        "platforms": {},
        "roles": {},
        "device_types": {},
        "vlans": {},
        "prefixes": {},
    }

    # Resolve Active status and Global namespace
    active_status = nb.get_one("extras/statuses/", {"name": "Active"})
    if not active_status:
        raise RuntimeError("Could not find 'Active' status in Nautobot")
    ids["status_active"] = active_status["id"]

    global_ns = nb.get_one("ipam/namespaces/", {"name": fixtures["metadata"]["namespace"]})
    if not global_ns:
        global_ns = nb.request("POST", "ipam/namespaces/", json={"name": fixtures["metadata"]["namespace"]})
    ids["namespace_global"] = global_ns["id"]

    print("1. Location Types & Locations")
    for lt in fixtures["location_types"]:
        existing = nb.get_one("dcim/location-types/", {"name": lt["name"]})
        if existing:
            merged_cts = sorted(set(existing.get("content_types", [])) | set(lt["content_types"]))
            if merged_cts != sorted(existing.get("content_types", [])):
                existing = nb.request(
                    "PATCH",
                    f"dcim/location-types/{existing['id']}/",
                    json={"content_types": merged_cts},
                )
                print(f"  [updated] LocationType {lt['name']} content_types")
            else:
                print(f"  [exists]  LocationType {lt['name']}")
            ids["location_types"][lt["name"]] = existing["id"]
        else:
            obj = nb.request(
                "POST",
                "dcim/location-types/",
                json={
                    "name": lt["name"],
                    "nestable": lt.get("nestable", False),
                    "content_types": lt["content_types"],
                },
            )
            print(f"  [created] LocationType {lt['name']}")
            ids["location_types"][lt["name"]] = obj["id"]

    for loc in fixtures["locations"]:
        obj = nb.ensure(
            "dcim/locations/",
            {"name": loc["name"]},
            {
                "name": loc["name"],
                "location_type": ids["location_types"][loc["location_type"]],
                "status": ids["status_active"],
                "description": loc.get("description", ""),
            },
            label="Location",
        )
        ids["locations"][loc["name"]] = obj["id"]

    print("2. Manufacturers & Platforms")
    for mfg in fixtures["manufacturers"]:
        obj = nb.ensure("dcim/manufacturers/", {"name": mfg["name"]}, {"name": mfg["name"]}, label="Manufacturer")
        ids["manufacturers"][mfg["name"]] = obj["id"]

    for plat in fixtures["platforms"]:
        payload = {
            "name": plat["name"],
            "manufacturer": ids["manufacturers"][plat["manufacturer"]],
            "network_driver": plat["network_driver"],
            "napalm_driver": plat["napalm_driver"],
            "description": plat.get("description", ""),
        }
        obj = nb.ensure(
            "dcim/platforms/",
            {"name": plat["name"]},
            payload,
            update_existing=True,
            label="Platform",
        )
        ids["platforms"][plat["name"]] = obj["id"]

    print("3. Roles & Device Types")
    for role in fixtures["roles"]:
        existing = nb.get_one("extras/roles/", {"name": role["name"]})
        if existing:
            merged_cts = sorted(set(existing.get("content_types", [])) | set(role["content_types"]))
            if merged_cts != sorted(existing.get("content_types", [])):
                existing = nb.request(
                    "PATCH",
                    f"extras/roles/{existing['id']}/",
                    json={"content_types": merged_cts},
                )
                print(f"  [updated] Role {role['name']} content_types")
            else:
                print(f"  [exists]  Role {role['name']}")
            ids["roles"][role["name"]] = existing["id"]
        else:
            obj = nb.request(
                "POST",
                "extras/roles/",
                json={
                    "name": role["name"],
                    "color": role.get("color", "2196f3"),
                    "description": role.get("description", ""),
                    "content_types": role["content_types"],
                },
            )
            print(f"  [created] Role {role['name']}")
            ids["roles"][role["name"]] = obj["id"]

    for dt in fixtures["device_types"]:
        obj = nb.ensure(
            "dcim/device-types/",
            {"model": dt["model"]},
            {
                "model": dt["model"],
                "manufacturer": ids["manufacturers"][dt["manufacturer"]],
                "u_height": dt.get("u_height", 1),
            },
            label="DeviceType",
        )
        ids["device_types"][dt["model"]] = obj["id"]

    print("4. Baseline VLANs")
    for vlan in fixtures["vlans"]:
        loc_id = ids["locations"][vlan["location"]]
        payload = {
            "vid": vlan["vid"],
            "name": vlan["name"],
            "status": ids["status_active"],
            "locations": [loc_id],
            "description": vlan.get("description", ""),
        }
        obj = nb.ensure(
            "ipam/vlans/",
            {"vid": vlan["vid"], "name": vlan["name"]},
            payload,
            update_existing=True,
            label="VLAN",
        )
        ids["vlans"][vlan["vid"]] = obj["id"]

    print("5. IPAM Prefixes")
    for pfx in fixtures["prefixes"]:
        loc_id = ids["locations"][pfx["location"]]
        payload: dict[str, Any] = {
            "prefix": pfx["prefix"],
            "namespace": ids["namespace_global"],
            "status": ids["status_active"],
            "type": pfx.get("type", "network"),
            "locations": [loc_id],
            "description": pfx.get("description", ""),
        }
        if "vlan_vid" in pfx and pfx["vlan_vid"] in ids["vlans"]:
            payload["vlan"] = ids["vlans"][pfx["vlan_vid"]]
        obj = nb.ensure(
            "ipam/prefixes/",
            {"prefix": pfx["prefix"], "namespace": fixtures["metadata"]["namespace"]},
            payload,
            update_existing=True,
            label="Prefix",
        )
        ids["prefixes"][pfx["prefix"]] = obj["id"]

    print("6. Global Config Context")
    lab_dc1_id = ids["locations"]["Lab-DC1"]
    nb.ensure(
        "extras/config-contexts/",
        {"name": "global-services"},
        {
            "name": "global-services",
            "weight": 1000,
            "description": "Global lab NTP, Syslog, SNMP, domain, and BGP routing map (RFC 5737)",
            "is_active": True,
            "locations": [lab_dc1_id],
            "data": global_ctx_data,
        },
        update_existing=True,
        label="ConfigContext",
    )

    return ids


def ensure_ip_and_attach(
    nb: NautobotClient,
    ids: dict[str, Any],
    namespace_name: str,
    iface_id: str,
    address: str,
    description: str = "",
) -> dict[str, Any]:
    ip_obj = nb.ensure(
        "ipam/ip-addresses/",
        {"address": address, "namespace": namespace_name},
        {
            "address": address,
            "namespace": ids["namespace_global"],
            "status": ids["status_active"],
            "description": description,
        },
        label="IPAddress",
    )
    existing_map = nb.get_one(
        "ipam/ip-address-to-interface/",
        {"ip_address": ip_obj["id"], "interface": iface_id},
    )
    if not existing_map:
        nb.request(
            "POST",
            "ipam/ip-address-to-interface/",
            json={"ip_address": ip_obj["id"], "interface": iface_id},
        )
        print(f"  [attached] IP {address} -> interface {iface_id[:8]}")
    return ip_obj


def seed_devices(
    nb: NautobotClient,
    fixtures: dict[str, Any],
    ids: dict[str, Any],
    cisco_platform: str,
    cisco_device_type: str,
    post_onboard_only: bool = False,
) -> None:
    """Seed or enrich devices, interfaces, IPs, primary_ip4, and per-device BGP local context."""
    mode = "Post-onboard device enrichment" if post_onboard_only else "Devices, Interfaces & IPs"
    print(f"7. {mode}")
    ns_name = fixtures["metadata"]["namespace"]
    bgp_map = fixtures.get("bgp", {})

    for dev in fixtures["devices"]:
        dev_name = dev["name"]
        platform_name = cisco_platform if dev_name == "cisco-core1" else dev["platform"]
        device_type_model = cisco_device_type if dev_name == "cisco-core1" else dev["device_type"]

        local_ctx = {"bgp": bgp_map[dev_name]} if dev_name in bgp_map else {}

        existing = nb.get_one("dcim/devices/", {"name": dev_name})
        if post_onboard_only and not existing:
            print(f"  [skip]    Device {dev_name} not found yet (run Device Onboarding first or use --include-devices)")
            continue

        if existing:
            patch_payload = {
                "role": ids["roles"][dev["role"]],
                "platform": ids["platforms"][platform_name],
                "location": ids["locations"][dev["location"]],
                "status": ids["status_active"],
                "local_config_context_data": local_ctx,
            }
            dev_obj = nb.request("PATCH", f"dcim/devices/{existing['id']}/", json=patch_payload)
            print(f"  [updated] Device {dev_name} (role={dev['role']}, platform={platform_name})")
        else:
            dev_obj = nb.request(
                "POST",
                "dcim/devices/",
                json={
                    "name": dev_name,
                    "device_type": ids["device_types"][device_type_model],
                    "role": ids["roles"][dev["role"]],
                    "platform": ids["platforms"][platform_name],
                    "location": ids["locations"][dev["location"]],
                    "status": ids["status_active"],
                    "local_config_context_data": local_ctx,
                },
            )
            print(f"  [created] Device {dev_name}")

        primary_ip_id = None
        for iface in dev.get("interfaces", []):
            iface_obj = nb.ensure(
                "dcim/interfaces/",
                {"device": dev_name, "name": iface["name"]},
                {
                    "device": dev_obj["id"],
                    "name": iface["name"],
                    "type": iface.get("type", "1000base-t"),
                    "status": ids["status_active"],
                    "mgmt_only": iface.get("mgmt_only", False),
                    "description": iface.get("description", ""),
                },
                update_existing=True,
                label=f"Interface {dev_name}:{iface['name']}",
            )
            if iface.get("ip_address"):
                ip_obj = ensure_ip_and_attach(
                    nb,
                    ids,
                    ns_name,
                    iface_obj["id"],
                    iface["ip_address"],
                    description=f"{dev_name} {iface['name']}",
                )
                if iface["ip_address"] == dev.get("mgmt_ip"):
                    primary_ip_id = ip_obj["id"]

        if primary_ip_id and (not dev_obj.get("primary_ip4") or dev_obj["primary_ip4"].get("id") != primary_ip_id):
            nb.request("PATCH", f"dcim/devices/{dev_obj['id']}/", json={"primary_ip4": primary_ip_id})
            print(f"  [updated] Device {dev_name} primary_ip4 -> {dev['mgmt_ip']}")


def apply_demo_change(nb: NautobotClient, fixtures: dict[str, Any], ids: dict[str, Any]) -> None:
    """Apply the planned SoT CI/CD demo change fixture."""
    print("Applying planned SoT CI/CD demo change fixture...")
    demo = fixtures["demo_change"]
    ns_name = fixtures["metadata"]["namespace"]

    vlan = demo["vlan"]
    loc_id = ids["locations"][vlan["location"]]
    vlan_obj = nb.ensure(
        "ipam/vlans/",
        {"vid": vlan["vid"], "name": vlan["name"]},
        {
            "vid": vlan["vid"],
            "name": vlan["name"],
            "status": ids["status_active"],
            "locations": [loc_id],
            "description": vlan.get("description", ""),
        },
        update_existing=True,
        label="Demo VLAN",
    )

    pfx = demo["prefix"]
    nb.ensure(
        "ipam/prefixes/",
        {"prefix": pfx["prefix"], "namespace": ns_name},
        {
            "prefix": pfx["prefix"],
            "namespace": ids["namespace_global"],
            "status": ids["status_active"],
            "type": pfx.get("type", "network"),
            "locations": [loc_id],
            "vlan": vlan_obj["id"],
            "description": pfx.get("description", ""),
        },
        update_existing=True,
        label="Demo Prefix",
    )

    for upd in demo.get("interface_updates", []):
        iface = nb.get_one("dcim/interfaces/", {"device": upd["device"], "name": upd["interface"]})
        if iface:
            nb.request(
                "PATCH",
                f"dcim/interfaces/{iface['id']}/",
                json={"description": upd["description"]},
            )
            print(f"  [updated] {upd['device']}:{upd['interface']} description -> {upd['description']}")
        else:
            print(f"  [warn]    Interface {upd['device']}:{upd['interface']} not found")

    for new_if in demo.get("new_interfaces", []):
        dev = nb.get_one("dcim/devices/", {"name": new_if["device"]})
        if not dev:
            print(f"  [warn]    Device {new_if['device']} not found")
            continue
        iface_obj = nb.ensure(
            "dcim/interfaces/",
            {"device": new_if["device"], "name": new_if["name"]},
            {
                "device": dev["id"],
                "name": new_if["name"],
                "type": new_if.get("type", "virtual"),
                "status": ids["status_active"],
                "description": new_if.get("description", ""),
            },
            update_existing=True,
            label=f"Demo Interface {new_if['device']}:{new_if['name']}",
        )
        if new_if.get("ip_address"):
            ensure_ip_and_attach(
                nb,
                ids,
                ns_name,
                iface_obj["id"],
                new_if["ip_address"],
                description=new_if.get("description", ""),
            )


def revert_demo_change(nb: NautobotClient, fixtures: dict[str, Any]) -> None:
    """Revert the planned SoT CI/CD demo change fixture."""
    print("Reverting planned SoT CI/CD demo change fixture...")
    demo = fixtures["demo_change"]
    ns_name = fixtures["metadata"]["namespace"]

    pfx = nb.get_one("ipam/prefixes/", {"prefix": demo["prefix"]["prefix"], "namespace": ns_name})
    if pfx:
        nb.request("DELETE", f"ipam/prefixes/{pfx['id']}/")
        print(f"  [deleted] Prefix {demo['prefix']['prefix']}")

    vlan = nb.get_one("ipam/vlans/", {"vid": demo["vlan"]["vid"], "name": demo["vlan"]["name"]})
    if vlan:
        nb.request("DELETE", f"ipam/vlans/{vlan['id']}/")
        print(f"  [deleted] VLAN {demo['vlan']['vid']} {demo['vlan']['name']}")

    for new_if in demo.get("new_interfaces", []):
        if new_if.get("ip_address"):
            ip_obj = nb.get_one("ipam/ip-addresses/", {"address": new_if["ip_address"], "namespace": ns_name})
            if ip_obj:
                nb.request("DELETE", f"ipam/ip-addresses/{ip_obj['id']}/")
                print(f"  [deleted] IP {new_if['ip_address']}")
        iface = nb.get_one("dcim/interfaces/", {"device": new_if["device"], "name": new_if["name"]})
        if iface:
            nb.request("DELETE", f"dcim/interfaces/{iface['id']}/")
            print(f"  [deleted] Interface {new_if['device']}:{new_if['name']}")

    # Restore baseline description for updated interfaces
    baseline_desc: dict[tuple[str, str], str] = {}
    for dev in fixtures["devices"]:
        for iface in dev.get("interfaces", []):
            baseline_desc[(dev["name"], iface["name"])] = iface.get("description", "")

    for upd in demo.get("interface_updates", []):
        iface = nb.get_one("dcim/interfaces/", {"device": upd["device"], "name": upd["interface"]})
        if iface:
            orig = baseline_desc.get((upd["device"], upd["interface"]), "")
            nb.request("PATCH", f"dcim/interfaces/{iface['id']}/", json={"description": orig})
            print(f"  [restored] {upd['device']}:{upd['interface']} description -> {orig}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed Nautobot 3.2 SoT fixtures for the CI/CD lab.")
    parser.add_argument("--url", default=os.environ.get("NAUTOBOT_URL", "http://127.0.0.1:8083"))
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--context-file", type=Path, default=DEFAULT_CONTEXT_FILE)
    parser.add_argument("--include-devices", action="store_true", help="Also seed devices, interfaces, and IPs")
    parser.add_argument(
        "--post-onboard",
        action="store_true",
        help="Enrich already-onboarded devices with roles, platforms, interface descriptions, IPs, and BGP context",
    )
    parser.add_argument("--apply-demo-change", action="store_true", help="Apply the planned SoT CI/CD demo change")
    parser.add_argument("--revert-demo-change", action="store_true", help="Revert the planned SoT CI/CD demo change")
    parser.add_argument(
        "--cisco-platform",
        default=os.environ.get("CISCO_PLATFORM", "cisco_xe"),
        choices=["cisco_xe", "cisco_ios"],
        help="Platform for cisco-core1 (default: cisco_xe)",
    )
    parser.add_argument(
        "--cisco-device-type",
        default=os.environ.get("CISCO_DEVICE_TYPE", "CSR1000v"),
        help="DeviceType model for cisco-core1 (default: CSR1000v)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = (os.environ.get("NAUTOBOT_TOKEN") or os.environ.get("NAUTOBOT_SUPERUSER_API_TOKEN") or "").strip()
    if not token:
        print("ERROR: NAUTOBOT_TOKEN (or NAUTOBOT_SUPERUSER_API_TOKEN) environment variable is required.", file=sys.stderr)
        return 2

    with args.fixtures.open("r", encoding="utf-8") as fh:
        fixtures = yaml.safe_load(fh)
    with args.context_file.open("r", encoding="utf-8") as fh:
        global_ctx_data = json.load(fh)

    nb = NautobotClient(args.url, token)

    if args.revert_demo_change:
        revert_demo_change(nb, fixtures)
        print("Done.")
        return 0

    ids = seed_foundation(nb, fixtures, global_ctx_data)

    if args.include_devices:
        seed_devices(nb, fixtures, ids, args.cisco_platform, args.cisco_device_type, post_onboard_only=False)
    elif args.post_onboard:
        seed_devices(nb, fixtures, ids, args.cisco_platform, args.cisco_device_type, post_onboard_only=True)

    if args.apply_demo_change:
        apply_demo_change(nb, fixtures, ids)

    print("Nautobot seeding complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
