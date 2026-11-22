"""Load lab.yaml and the secrets, and compute every derived value.

Everything else in the project imports `load()` from here, so there is
exactly one place where addresses are worked out.
"""
from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent          # project folder
STATE = ROOT / "state"                                 # generated files (CA, IDs, logs)


def _host(net: str, host: str | int) -> str:
    """'172.16.1.0/24' + '.21' (or 21) -> '172.16.1.21'"""
    n = ipaddress.ip_network(net)
    return str(n.network_address + int(str(host).lstrip(".")))


@dataclass
class Secrets:
    cml_host: str
    cml_user: str
    cml_pass: str
    mgr_user: str
    mgr_pass: str


def secrets() -> Secrets:
    """Credentials never live in the repo. They come from two files that
    only the lab owner can read: ~/cml-secrets.env and lab.env."""
    env: dict[str, str] = {}
    for f in (Path.home() / "cml-secrets.env", ROOT / "lab.env"):
        if f.exists():
            for line in f.read_text().splitlines():
                line = line.strip().removeprefix("export ").strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    env[k] = v.strip().strip('"').strip("'")
    env.update({k: v for k, v in os.environ.items() if k in env or k.startswith(("CML_", "MANAGER_"))})
    return Secrets(env["CML_HOST"], env["CML_USER"], env["CML_PASS"],
                   env.get("MANAGER_USER", "admin"), env["MANAGER_PASSWORD"])


def load() -> dict:
    """Read lab.yaml and add computed fields (full IPs, masks, VRRP VIPs)."""
    cfg = yaml.safe_load((ROOT / "lab.yaml").read_text())
    u = cfg["underlay"]
    gw = u["gateway_host"]
    u["gw_vpn0"] = _host(u["controllers_net"], gw)
    u["gw_inet"] = _host(u["inet_net"], gw)
    u["gw_mpls"] = _host(u["mpls_net"], gw)
    for net in ("controllers_net", "inet_net", "mpls_net"):
        u[net + "_mask"] = str(ipaddress.ip_network(u[net]).netmask)

    for site in cfg["sites"]:
        for vpn, net in site["lans"].items():
            n = ipaddress.ip_network(net)
            site.setdefault("lan", {})[vpn] = {
                "net": net, "network": str(n.network_address), "mask": str(n.netmask),
                "prefixlen": n.prefixlen, "vip": _host(net, 1),
            }
        for e in site["edges"]:
            e["site"] = site["name"]
            e["site_id"] = site["site_id"]
            e["inet_ip"] = _host(u["inet_net"], e["inet"])
            e["mpls_ip"] = _host(u["mpls_net"], e["mpls"])
            e["lan_ip"] = {vpn: _host(net, e["lan_host"]) for vpn, net in site["lans"].items()}
        for h in site["hosts"]:
            lan = site["lan"][h["vpn"]]
            h["ip"] = _host(lan["net"], h["host"])
            h["prefixlen"] = lan["prefixlen"]
            h["gateway"] = lan["vip"]
    return cfg


def all_edges(cfg: dict) -> list[dict]:
    return [e for s in cfg["sites"] for e in s["edges"]]


def site(cfg: dict, name: str) -> dict:
    return next(s for s in cfg["sites"] if s["name"] == name)
