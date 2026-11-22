"""Centralized policy with a Policy Group (SD-WAN Manager 20.x).

A Policy Group is to policy what a Configuration Group is to config:
a bundle of policy profiles that you attach to devices.

  Policy Group "LAB-PG"
   |-- Topology profile          -> Hub-and-spoke for VPN 20 (GUEST)
   `-- Application Priority profile
         `-- Traffic policy      -> VPN 10: ICMP must meet CRITICAL-SLA,
                                    prefer MPLS, fall back to the best path
                                 -> VPN 20: everything to the Internet
                                    goes out locally (DIA, NAT on Gi1)
  Policy objects (shared building blocks, in the policy-object profile):
     SLA class  CRITICAL-SLA   latency / loss / jitter limits
     Data prefix CORP-NETS     all VPN 10 LANs
     Data prefix GUEST-NETS / RFC1918
"""
from __future__ import annotations

from .configgroup import G

FP = "/dataservice/v1/feature-profile/sdwan"
REF = lambda i: {"refId": G(i)}   # noqa: E731  a pointer to a policy object



def vpn_ref(cfg: dict, key: str) -> str:
    """Policies point at a VPN by the NAME OF ITS FEATURE PARCEL in the
    service profile (e.g. LAB-VPN10-CORP), not by the VPN number and not by
    the 'name' field inside the parcel. configgroup.py builds that parcel
    name as LAB-VPN<id>-<name>, so we rebuild the same string here."""
    v = cfg["vpns"][key]
    return f"LAB-VPN{v['id']}-{v['name']}"

def _po_profile(mgr) -> str:
    """Policy objects live in a single profile created by the Manager."""
    return mgr.get(f"{FP}/policy-object")[0]["profileId"]


def _object(mgr, prof: str, kind: str, name: str, data: dict) -> str:
    for o in (mgr.get(f"{FP}/policy-object/{prof}/{kind}") or {}).get("data", []):
        if o["payload"]["name"] == name:          # exists: update it to match this code
            mgr.put(f"{FP}/policy-object/{prof}/{kind}/{o['parcelId']}",
                    {"name": name, "description": name, "data": data})
            return o["parcelId"]
    return mgr.post(f"{FP}/policy-object/{prof}/{kind}",
                    {"name": name, "description": name, "data": data})["parcelId"]


def prefix_list(nets: list[str]) -> dict:
    return {"entries": [{"ipv4Address": G(n.split("/")[0]),
                         "ipv4PrefixLength": G(int(n.split("/")[1]))} for n in nets]}


def build_objects(mgr, cfg: dict) -> dict:
    prof = _po_profile(mgr)
    sla = cfg["policy"]["sla"]
    ids = {
        "sla": _object(mgr, prof, "sla-class", sla["name"], {"entries": [{
            "latency": G(sla["latency_ms"]), "loss": G(sla["loss_pct"]), "jitter": G(sla["jitter_ms"]),
            # When NO tunnel meets the SLA, "fallback to best path" picks the
            # least-bad one. This says how to rank them: loss first, then
            # latency; tunnels within 1% loss / 10 ms of each other count as equal.
            "fallbackBestTunnel": {"criteria": G("loss-latency"),
                                   "lossVariance": G(1), "latencyVariance": G(10)},
        }]}),
        "corp": _object(mgr, prof, "data-prefix", "CORP-NETS",
                        prefix_list([s["lans"]["corp"] for s in cfg["sites"]])),
        "guest": _object(mgr, prof, "data-prefix", "GUEST-NETS",
                         prefix_list([s["lans"]["guest"] for s in cfg["sites"]])),
        "rfc1918": _object(mgr, prof, "data-prefix", "RFC1918",
                           prefix_list(["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"])),
    }
    return ids


def corp_aar(cfg: dict, obj: dict) -> dict:
    """VPN 10: critical traffic (ICMP here) must meet CRITICAL-SLA. Prefer
    MPLS; if MPLS breaks the SLA, move to any path that meets it; if none
    does, use the best one rather than dropping the traffic."""
    return {
        "dataDefaultAction": G("accept"),
        # Policy groups refer to a VPN by its NAME (as defined in the
        # configuration group), not by its number.
        "target": {"vpn": G([vpn_ref(cfg, "corp")]), "direction": G("service")},
        "sequences": [{
            "sequenceId": G(10), "sequenceName": G("CRITICAL-OVER-MPLS"),
            "baseAction": G("accept"), "sequenceIpType": G("ipv4"),
            "match": {"entries": [
                {"protocol": G(cfg["policy"]["critical_protocols"])},
                {"destinationDataPrefixList": REF(obj["corp"])},
            ]},
            "actions": [{"slaClass": [
                {"slaName": REF(obj["sla"])},
                {"preferredColor": G([cfg["policy"]["preferred_color"]])},
                {"fallbackToBestPath": G(True)},
            ]}],
        }],
    }


def guest_dia(cfg: dict, obj: dict) -> dict:
    """VPN 20: private destinations follow normal (overlay) routing, every
    other destination is NATed out of the local Internet link (DIA)."""
    return {
        "dataDefaultAction": G("accept"),
        "target": {"vpn": G([vpn_ref(cfg, "guest")]), "direction": G("service")},
        "sequences": [
            {"sequenceId": G(10), "sequenceName": G("PRIVATE-STAYS-IN-OVERLAY"),
             "baseAction": G("accept"), "sequenceIpType": G("ipv4"),
             "match": {"entries": [{"destinationDataPrefixList": REF(obj["rfc1918"])}]},
             "actions": []},
            {"sequenceId": G(20), "sequenceName": G("INTERNET-LOCAL-EXIT"),
             "baseAction": G("accept"), "sequenceIpType": G("ipv4"),
             "match": {"entries": [{"sourceDataPrefixList": REF(obj["guest"])}]},
             "actions": [{"nat": {"useVpn": G(True), "fallback": G(True)}}]},
        ],
    }


def site_uuids(mgr) -> dict[int, str]:
    """Topology parcels point at sites in the Network Hierarchy (by UUID),
    not at raw site IDs. A site appears there once a device with that
    site ID has been onboarded."""
    return {n["data"]["hierarchyId"]["siteId"]: n["uuid"]
            for n in mgr.get("/dataservice/v1/network-hierarchy")
            if n.get("data", {}).get("label") == "SITE"}


def hub_and_spoke(cfg: dict, sites: dict[int, str]) -> dict:
    """VPN 20 only: branches build tunnels to the DC, never to each other."""
    hub = next(s for s in cfg["sites"] if s["name"] == cfg["policy"]["hub_site"])
    spokes = [sites[s["site_id"]] for s in cfg["sites"] if s["role"] == "spoke"]
    return {
        "target": {"vpn": G([vpn_ref(cfg, "guest")])},
        "selectedHierarchyHubs": G([sites[hub["site_id"]]]),
        "spokes": [{"name": G("BRANCHES"), "spokeHierarchyUuid": G(spokes),
                    "hubSites": [{"hierarchyUuid": G([sites[hub["site_id"]]]), "preference": G(100)}]}],
    }


def guest_isolation(cfg: dict, sites: dict[int, str]) -> dict:
    """One custom control policy, applied OUTBOUND from the Controller to the
    branch sites (= what the Controller tells the branches):
      seq 10  VPN 20 route that came from the DC hub  -> accept
      seq 20  any other VPN 20 route                   -> reject
      default accept: VPN 10 routes and all TLOCs pass untouched, so the
      corporate VPN stays a full mesh and branch-to-branch tunnels stay up.
    Result: a branch guest can reach the DC guest segment, but never
    another branch's guest segment."""
    hub = next(s for s in cfg["sites"] if s["name"] == cfg["policy"]["hub_site"])
    spokes = [sites[s["site_id"]] for s in cfg["sites"] if s["role"] == "spoke"]
    guest = vpn_ref(cfg, "guest")
    return {
        # The schema wants an inbound AND an outbound site list. Inbound we name
        # the hub: its guest routes match seq 10 (accept), everything else is
        # default accept, so inbound changes nothing. Outbound = the branches.
        "target": {"vpn": G([guest]), "level": G("SITE"),
                   "inboundHierarchyUuid": G([sites[hub["site_id"]]]),
                   "outboundHierarchyUuid": G(spokes)},
        "defaultAction": G("accept"),
        "sequences": [
            {"sequenceId": G(10), "sequenceName": G("GUEST-FROM-HUB"), "baseAction": G("accept"),
             "sequenceType": G("route"), "sequenceIpType": G("ipv4"),
             "match": {"entries": [{"vpn": G([guest])}, {"hierarchyUuid": G([sites[hub["site_id"]]])}]},
             "actions": []},
            {"sequenceId": G(20), "sequenceName": G("GUEST-OTHER-BRANCHES"), "baseAction": G("reject"),
             "sequenceType": G("route"), "sequenceIpType": G("ipv4"),
             "match": {"entries": [{"vpn": G([guest])}]},
             "actions": []},
        ],
    }


def corp_mesh(cfg: dict, sites: dict[int, str]) -> dict:
    """VPN 10: every site may build tunnels to every other site (full mesh).
    Declaring it also tells the Manager which VPN name (CORP) maps to which
    VPN ID on the Controller - policy groups need that mapping."""
    return {"target": {"vpn": G([vpn_ref(cfg, "corp")])},
            "hierarchyUuid": G([sites[s["site_id"]] for s in cfg["sites"]])}


def _parcel(mgr, kind, prof, parcel, name, data):
    body = {"name": name, "description": name, "data": data}
    pid = mgr.find_parcel(kind, prof, parcel, name)
    if pid:                       # already there: update it to match this code
        mgr.put(f"{FP}/{kind}/{prof}/{parcel}/{pid}", body)
        return pid
    r = mgr.post(f"{FP}/{kind}/{prof}/{parcel}", body)
    return r.get("parcelId") or r.get("id")


def build(mgr, cfg: dict, log=print) -> str:
    log("Policy objects: SLA class CRITICAL-SLA, prefix lists CORP-NETS, GUEST-NETS, RFC1918")
    obj = build_objects(mgr, cfg)

    log("Application Priority profile: CORP-AAR (VPN 10) + GUEST-DIA (VPN 20)")
    ap = mgr.create_profile("application-priority", "LAB-APP-PRIORITY", "AAR + DIA")
    _parcel(mgr, "application-priority", ap, "traffic-policy", "CORP-AAR", corp_aar(cfg, obj))
    _parcel(mgr, "application-priority", ap, "traffic-policy", "GUEST-DIA", guest_dia(cfg, obj))

    pg = next((g["id"] for g in mgr.policy_groups() if g["name"] == "LAB-PG"), None)
    if not pg:
        log("Policy group LAB-PG = application priority + policy objects")
        pg = mgr.post("/dataservice/v1/policy-group", {
            "name": "LAB-PG", "description": "Lab centralized policy", "solution": "sdwan",
            "profiles": [{"id": ap}, {"id": _po_profile(mgr)}]})["id"]
    return pg


def build_topology(mgr, cfg: dict, log=print) -> str:
    """Topology (who builds tunnels to whom) is its own group in 20.18,
    because it is enforced by the Controller, not by the edges."""
    # VPN 10 needs NO topology parcel: with no control policy the Controller
    # reflects every TLOC to every site, which IS a full mesh. Adding an
    # explicit mesh parcel would apply a second control policy to the same
    # branch sites, and the Controller rejects overlapping site-lists.
    log("Topology profile: GUEST-ISOLATION custom control (VPN 20 branches only learn DC guest routes; VPN 10 stays full mesh)")
    tp = mgr.create_profile("topology", "LAB-TOPOLOGY", "Guest hub-and-spoke")
    sites = site_uuids(mgr)
    old = mgr.find_parcel("topology", tp, "mesh", "CORP-MESH")
    if old:                                  # left over from an earlier design
        mgr.delete(f"{FP}/topology/{tp}/mesh/{old}")
    # The built-in hub-and-spoke type rejects EVERYTHING else for the spokes
    # (VPN 10 routes and branch-to-branch TLOCs too), so we use a custom
    # control policy that only touches VPN 20.
    old = mgr.find_parcel("topology", tp, "hubspoke", "GUEST-HUB-SPOKE")
    if old:
        mgr.delete(f"{FP}/topology/{tp}/hubspoke/{old}")
    _parcel(mgr, "topology", tp, "custom-control", "GUEST-ISOLATION", guest_isolation(cfg, sites))
    tg = next((g["id"] for g in mgr.get("/dataservice/v1/topology-group") or []
               if g["name"] == "LAB-TOPOLOGY-GROUP"), None)
    if not tg:
        log("Topology group LAB-TOPOLOGY-GROUP")
        tg = mgr.post("/dataservice/v1/topology-group", {
            "name": "LAB-TOPOLOGY-GROUP", "description": "Guest hub-and-spoke", "solution": "sdwan",
            "profiles": [{"id": tp}, {"id": _po_profile(mgr)}]})["id"]
    return tg


def deploy(mgr, pg: str, uuids: list[str], log=print):
    mgr.put(f"/dataservice/v1/policy-group/{pg}/device/associate",
            {"devices": [{"id": u} for u in uuids]})
    task = mgr.post(f"/dataservice/v1/policy-group/{pg}/device/deploy",
                    {"devices": [{"id": u} for u in uuids]})
    tid = task.get("parentTaskId") or task.get("id")
    log(f"  deploy task {tid}")
    return mgr.wait_task(tid)
