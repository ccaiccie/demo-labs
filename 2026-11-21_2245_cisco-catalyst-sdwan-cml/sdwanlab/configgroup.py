"""Build the Configuration Group that every WAN edge in the lab uses.

How Catalyst SD-WAN 20.x organises device configuration
-------------------------------------------------------
  Configuration Group  "BRANCH-CG"
   |-- System profile     -> basic, AAA, BFD, OMP, global, logging
   |-- Transport profile  -> VPN 0 + Gi1 (INET) + Gi2 (MPLS)
   |-- Service profile    -> VPN 10 + Gi3 (VRRP)  /  VPN 20 + Gi4 (VRRP)
   `-- CLI profile        -> a couple of raw IOS-XE lines

Each "feature" inside a profile is called a *parcel* in the API. A value
in a parcel is always wrapped in an option object:

    {"optionType": "global",   "value": 1}            same for every device
    {"optionType": "variable", "value": "{{name}}"}   filled in per device
    {"optionType": "default"}                         use the factory default

Variables are what make ONE group serve all five routers: every edge
gets its own IP addresses, VRRP priority, host name and so on.
"""
from __future__ import annotations

import copy
import json

from .config import ROOT

PARCELS = ROOT / "templates" / "parcels"

G = lambda v: {"optionType": "global", "value": v}          # noqa: E731
V = lambda n: {"optionType": "variable", "value": "{{" + n + "}}"}  # noqa: E731
D = lambda v=None: {"optionType": "default", **({} if v is None else {"value": v})}  # noqa: E731


def base(name: str) -> dict:
    """GUI defaults for a feature, exported once from the Manager."""
    return copy.deepcopy(json.loads((PARCELS / f"{name}.json").read_text()))


# --------------------------------------------------------------------------
# System profile
# --------------------------------------------------------------------------
def system_parcels(cfg: dict, admin_password: str) -> dict[str, dict]:
    aaa = base("aaa")
    aaa["user"] = [{"name": G("admin"), "password": G(admin_password), "privilege": D("15")}]

    bfd = base("bfd")
    # How often BFD probes are summarised for app-aware routing (SLA checks)
    bfd["pollInterval"] = G(cfg["overlay"]["bfd_poll_interval_ms"])
    bfd["multiplier"] = G(cfg["overlay"]["bfd_multiplier"])

    basic = base("basic")
    basic["clock"]["timezone"] = G("America/Los_Angeles")

    omp = base("omp")
    # OMP is the SD-WAN routing protocol between edges and the Controller.
    # Advertise connected + static LAN routes into the overlay (the default).
    return {"basic": basic, "aaa": aaa, "bfd": bfd, "omp": omp,
            "global": base("global"), "logging": base("logging")}


# --------------------------------------------------------------------------
# Transport profile (VPN 0)
# --------------------------------------------------------------------------
def transport_vpn0(cfg: dict) -> dict:
    u = cfg["underlay"]
    vpn0 = base("wan_vpn")
    vpn0["dnsIpv4"] = {"primaryDnsAddressIpv4": G(u["gw_inet"]),
                       "secondaryDnsAddressIpv4": G(u["gw_mpls"])}
    # Two default routes: one towards each provider
    vpn0["ipv4Route"] = [{
        "prefix": {"ipAddress": G("0.0.0.0"), "subnetMask": G("0.0.0.0")},
        "gateway": G("nextHop"),
        "nextHop": [{"address": G(u["gw_inet"]), "distance": D(1)},
                    {"address": G(u["gw_mpls"]), "distance": D(1)}],
    }]
    return vpn0


def transport_if(cfg: dict, which: str) -> dict:
    """which = 'inet' (Gi1, biz-internet, NAT for DIA) or 'mpls' (Gi2)."""
    p = base("wan_vpn_interface_ethernet")
    ifname, color = {"inet": ("GigabitEthernet1", cfg["overlay"]["colors"]["inet"]),
                     "mpls": ("GigabitEthernet2", cfg["overlay"]["colors"]["mpls"])}[which]
    p["interfaceName"] = G(ifname)
    p["description"] = G(which.upper())
    p["intfIpAddress"] = {"static": {"staticIpV4AddressPrimary": {
        "ipAddress": V(f"{which}_ip"), "subnetMask": V(f"{which}_mask")},
        "staticIpV4AddressSecondary": []}}
    p["tunnelInterface"] = G(True)                 # this port builds SD-WAN tunnels
    p["tunnel"]["color"] = G(color)                # the colour names the transport
    p["tunnel"]["restrict"] = G(True)              # only build tunnels to the SAME colour
    p["encapsulation"] = [{"encap": G("ipsec"), "preference": D(), "weight": D(1)}]
    if which == "inet":
        p["nat"] = G(True)                         # NAT = needed for direct Internet access
    else:
        p["nat"] = D(False)
        p.pop("natAttributesIpv4", None)
    return p


# --------------------------------------------------------------------------
# Service profile (LAN side VPNs)
# --------------------------------------------------------------------------
def service_vpn(vpn_id: int, name: str) -> dict:
    p = base("lan_vpn")
    p["vpnId"] = G(vpn_id)
    p["name"] = G(name)
    p["ipv4Route"] = []        # no static routes; DIA for guests comes from policy
    return p


def service_if(vpn_key: str, ifname: str, vrrp_group: int) -> dict:
    p = base("lan_vpn_interface_ethernet")
    p["interfaceName"] = G(ifname)
    p["description"] = G(f"{vpn_key.upper()} LAN")
    p["intfIpAddress"] = {"static": {"staticIpV4AddressPrimary": {
        "ipAddress": V(f"{vpn_key}_ip"), "subnetMask": V(f"{vpn_key}_mask")},
        "staticIpV4AddressSecondary": []}}
    # VRRP: the hosts always use .1 as their gateway. With two routers the
    # higher priority one is active; trackOmp makes a router give up the
    # VIP if it loses its connection to the overlay.
    p["vrrp"] = [{"group_id": G(vrrp_group), "priority": V("vrrp_priority"),
                  "timer": D(1000), "trackOmp": G(True),
                  "ipAddress": V(f"{vpn_key}_vip"), "ipAddressSecondary": [],
                  "tlocPrefChange": D(False), "followDualRouterHAAvailability": D(True)}]
    return p


# --------------------------------------------------------------------------
# Put it all together
# --------------------------------------------------------------------------
def build(mgr, cfg: dict, admin_password: str, log=print) -> str:
    """Create (or reuse) every profile and parcel, then the group itself."""
    pre = "LAB"
    ids = {}

    log("System profile: basic, AAA, BFD, OMP, global, logging")
    ids["system"] = sysp = mgr.create_profile("system", f"{pre}-SYSTEM", "Common system settings")
    for parcel, data in system_parcels(cfg, admin_password).items():
        name = f"{pre}-{parcel}"
        if not mgr.find_parcel("system", sysp, parcel, name):
            mgr.create_parcel("system", sysp, parcel, {"name": name, "description": name, "data": data})

    log("Transport profile: VPN 0 with Gi1 (biz-internet) and Gi2 (mpls)")
    ids["transport"] = tp = mgr.create_profile("transport", f"{pre}-TRANSPORT", "VPN 0 - INET + MPLS")
    vpn0 = mgr.find_parcel("transport", tp, "wan/vpn", f"{pre}-VPN0") or mgr.create_parcel(
        "transport", tp, "wan/vpn", {"name": f"{pre}-VPN0", "description": "Transport VPN",
                                     "data": transport_vpn0(cfg)})
    for which in ("inet", "mpls"):
        name = f"{pre}-VPN0-{which.upper()}"
        if not mgr.find_parcel("transport", tp, f"wan/vpn/{vpn0}/interface/ethernet", name):
            mgr.create_parcel("transport", tp, f"wan/vpn/{vpn0}/interface/ethernet",
                              {"name": name, "description": name, "data": transport_if(cfg, which)})

    log("Service profile: VPN 10 (CORP, Gi3) and VPN 20 (GUEST, Gi4), both with VRRP")
    ids["service"] = sp = mgr.create_profile("service", f"{pre}-SERVICE", "LAN VPNs")
    for vpn_key, ifname in (("corp", "GigabitEthernet3"), ("guest", "GigabitEthernet4")):
        v = cfg["vpns"][vpn_key]
        vname = f"{pre}-VPN{v['id']}-{v['name']}"
        vid = mgr.find_parcel("service", sp, "lan/vpn", vname) or mgr.create_parcel(
            "service", sp, "lan/vpn", {"name": vname, "description": vname,
                                       "data": service_vpn(v["id"], v["name"])})
        iname = f"{vname}-LAN"
        if not mgr.find_parcel("service", sp, f"lan/vpn/{vid}/interface/ethernet", iname):
            mgr.create_parcel("service", sp, f"lan/vpn/{vid}/interface/ethernet",
                              {"name": iname, "description": iname,
                               "data": service_if(vpn_key, ifname, v["id"])})

    log("CLI profile: send the console to the serial port (so CML can show it)")
    ids["cli"] = cp = mgr.create_profile("cli", f"{pre}-CLI", "Raw CLI add-on")
    if not mgr.find_parcel("cli", cp, "config", f"{pre}-CLI"):
        mgr.create_parcel("cli", cp, "config", {"name": f"{pre}-CLI", "description": "console",
                                                "data": {"config": "platform console serial"}})

    log("Configuration group BRANCH-CG = system + transport + service + cli")
    return mgr.create_config_group("BRANCH-CG", "All WAN edges in the lab",
                                   [ids["system"], ids["transport"], ids["service"], ids["cli"]])


def device_variables(edge: dict, site: dict) -> dict:
    """The per-device values that fill in the {{variables}} above."""
    corp, guest = site["lan"]["corp"], site["lan"]["guest"]
    return {
        "host_name": edge["label"], "system_ip": edge["system_ip"], "site_id": edge["site_id"],
        "inet_ip": edge["inet_ip"], "inet_mask": "255.255.255.0",
        "mpls_ip": edge["mpls_ip"], "mpls_mask": "255.255.255.0",
        "corp_ip": edge["lan_ip"]["corp"], "corp_mask": corp["mask"], "corp_vip": corp["vip"],
        "guest_ip": edge["lan_ip"]["guest"], "guest_mask": guest["mask"], "guest_vip": guest["vip"],
        "vrrp_priority": edge["vrrp_priority"],
    }
