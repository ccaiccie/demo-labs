"""Build the CML topology (YAML) for the underlay and control plane.

The edges are NOT in this file. They are added later, one by one, after
the Manager has generated a day-0 bootstrap for each of them. That is
the same order you would follow in real life: controllers first, then
"ship" each router with its bootstrap.
"""
from __future__ import annotations

import datetime as dt
import subprocess

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .config import ROOT

env = Environment(loader=FileSystemLoader(ROOT / "templates"), undefined=StrictUndefined,
                  keep_trailing_newline=True)


def sha512_hash(password: str) -> str:
    """Viptela OS stores passwords as SHA-512 crypt hashes ($6$...)."""
    return subprocess.check_output(["openssl", "passwd", "-6", password], text=True).strip()


# --------------------------------------------------------------------------
# Layout: x/y coordinates so the CML canvas looks like a network diagram
# --------------------------------------------------------------------------
POS = {
    "Manager01": (-400, -400), "Validator01": (-200, -400), "Controller01": (0, -400),
    "VPN0": (-200, -280), "Gateway": (-200, -160), "Internet": (-480, -160),
    "MGMT": (-640, -400), "INET": (-420, -20), "MPLS": (20, -20),
}
SITE_X = {"DC": -640, "BR1": -280, "BR2": 80, "BR3": 400}


def topology(cfg: dict, secrets, root_ca: str) -> str:
    u, m, c = cfg["underlay"], cfg["management"], cfg["controllers"]
    pw_hash = sha512_hash(secrets.mgr_pass)
    pw_time = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000+00:00")
    common = dict(org=cfg["organization"], validator_fqdn=cfg["validator_fqdn"],
                  validator_ip=c["validator"]["ip"], u=u, m=m, root_ca=root_ca.strip(),
                  pw_hash=pw_hash, pw_time=pw_time)
    ver = cfg["lab"]["version"].replace(".", "-")

    nodes, links = [], []

    def node(label, nd, ifaces, image=None, config=None, **extra):
        x, y = POS[label] if label in POS else extra.pop("xy")
        n = {"id": f"n{len(nodes)}", "label": label, "node_definition": nd, "x": x, "y": y,
             "tags": extra.pop("tags", []),
             "interfaces": [{"id": f"i{k}", "label": l, "slot": k, "type": "physical"}
                            for k, l in enumerate(ifaces)], **extra}
        if image:
            n["image_definition"] = image
        if config is not None:
            n["configuration"] = config
        nodes.append(n)
        return n

    def link(a, ai, b, bi):
        links.append({"id": f"l{len(links)}", "n1": a["id"], "i1": f"i{ai}",
                      "n2": b["id"], "i2": f"i{bi}"})

    def ctrl_cfg(key, personality, model, vpn0_if):
        return [{"name": "user-data", "content": env.get_template("controller.cloud-init.j2").render(
            c=c[key], personality=personality, model=model, vpn0_if=vpn0_if, **common)}]

    mgr = node("Manager01", "cat-sdwan-manager", ["eth0", "eth1", "eth2", "eth3"],
               image=f"cat-sdwan-manager-{ver}", cpus=c["manager"]["cpus"], ram=c["manager"]["ram"],
               config=ctrl_cfg("manager", "vmanage", "vmanage", "eth1"))
    val = node("Validator01", "cat-sdwan-validator", ["eth0", "ge0/0"],
               image=f"cat-sdwan-validator-{ver}", cpus=c["validator"]["cpus"], ram=c["validator"]["ram"],
               config=ctrl_cfg("validator", "vedge", "vedge-cloud", "ge0/0"))
    ctl = node("Controller01", "cat-sdwan-controller", ["eth0", "eth1", "eth2", "eth3"],
               image=f"cat-sdwan-controller-{ver}", cpus=c["controller"]["cpus"], ram=c["controller"]["ram"],
               config=ctrl_cfg("controller", "vsmart", "vsmart", "eth1"))

    sw = lambda label, n=16, **kw: node(label, "unmanaged_switch", [f"port{k}" for k in range(n)], **kw)
    vpn0 = sw("VPN0", 8)
    inet = sw("INET", 16)
    mpls = sw("MPLS", 16)
    gw = node("Gateway", "iol-xe", ["Ethernet0/0", "Ethernet0/1", "Ethernet0/2", "Ethernet0/3"],
              config=[{"name": "ios_config.txt", "content": env.get_template("gateway.ios.j2").render(**common)}])
    mgmt = node("MGMT", "external_connector", ["port"], config=[{"name": "default", "content": m["bridge"]}])
    internet = node("Internet", "external_connector", ["port"], config=[{"name": "default", "content": "NAT"}])

    link(mgr, 0, mgmt, 0)          # Manager eth0 (VPN 512) -> management bridge
    link(mgr, 1, vpn0, 0)          # Manager eth1 (VPN 0)
    link(val, 1, vpn0, 1)          # Validator ge0/0 (VPN 0)
    link(ctl, 1, vpn0, 2)          # Controller eth1 (VPN 0)
    link(gw, 0, vpn0, 3)           # Gateway e0/0 vrf vpn0
    link(gw, 1, inet, 0)           # Gateway e0/1 vrf inet
    link(gw, 2, mpls, 0)           # Gateway e0/2 vrf mpls
    link(gw, 3, internet, 0)       # Gateway e0/3 -> real Internet (NAT)

    # Per-site LAN switches and hosts. Edges will plug into these later.
    for s in cfg["sites"]:
        x = SITE_X[s["name"]]
        for k, vpn in enumerate(s["lans"]):
            lan = sw(f"{s['name']}-LAN{cfg['vpns'][vpn]['id']}", 8, xy=(x + 150 * k, 300))
            for j, h in enumerate(x for x in s["hosts"] if x["vpn"] == vpn):
                host = node(h["label"], "alpine", ["eth0"], image="alpine-base-3-23-3",
                            xy=(x + 150 * k, 420),
                            config=[{"name": "node.cfg",
                                     "content": env.get_template("host.sh.j2").render(h=h, s=s)}])
                link(host, 0, lan, 7 - j)

    annotations = [{
        "type": "text", "x1": -900, "y1": -480, "rotation": 0, "z_index": 0,
        "border_color": "#00000000", "border_style": "", "color": "#808080FF", "thickness": 1,
        "text_bold": False, "text_italic": False, "text_font": "monospace", "text_size": 11,
        "text_unit": "pt",
        "text_content": (f"VPN0 {u['controllers_net']}\nINET {u['inet_net']}\nMPLS {u['mpls_net']}\n"
                         f"Manager GUI https://{m['manager_ip']}"),
    }]
    for s in cfg["sites"]:
        annotations.append({**annotations[0], "x1": SITE_X[s["name"]], "y1": 470, "text_bold": True,
                            "text_content": f"{s['name']} (site {s['site_id']}, {s['role']})\n"
                                            + "\n".join(f"VPN{cfg['vpns'][v]['id']} {n}" for v, n in s["lans"].items())})

    topo = {"lab": {"title": cfg["lab"]["title"], "version": "0.3.0",
                    "description": "Catalyst SD-WAN lab - built by sdwan-cml (see README)",
                    "notes": "Built step by step by build.py"},
            "nodes": nodes, "links": links, "annotations": annotations}
    return yaml.safe_dump(topo, sort_keys=False, width=1000)
