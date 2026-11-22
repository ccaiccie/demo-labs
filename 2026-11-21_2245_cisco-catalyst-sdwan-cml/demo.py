#!/usr/bin/env python3
"""Live demonstrations used in the video.

    python demo.py path        # which tunnel would BR1 use for ICMP to the DC?
    python demo.py degrade     # add 300 ms latency to the DC's MPLS cable
    python demo.py restore     # remove the impairment again
    python demo.py sla         # app-route (BFD) latency per tunnel, BR1-E1 -> DC
    python demo.py edge BR1-E1 "show sdwan omp routes vpn 10"
    python demo.py guest       # guest isolation + direct Internet access tests
"""
from __future__ import annotations

import sys

from sdwanlab.console import Console
from build import CFG, SEC, TITLE, cml, state

DC = next(e for s in CFG["sites"] if s["name"] == "DC" for e in s["edges"])


def edge(label: str, *cmds: str) -> str:
    con = Console(SEC.cml_host, SEC.cml_user, SEC.cml_pass)
    out = con.run(TITLE, label, ["terminal length 0", "terminal width 512", *cmds],
                  login=("admin", SEC.mgr_pass), timeout=60, prompt=r"#\s*$", enable=True)
    print(out)
    return out


def path():
    """service-path asks the data-plane: 'for this exact packet, which tunnel?'"""
    edge("BR1-E1", "show sdwan policy service-path vpn 10 interface GigabitEthernet3 "
                   "source-ip 10.20.10.100 dest-ip 10.10.10.100 protocol 1 all")


def sla():
    edge("BR1-E1", f"show sdwan app-route stats remote-system-ip {DC['system_ip']} | "
                   "include color|mean-latency|average-latency|loss")


GUEST_TESTS = [
    ("BR1-GUEST", "10.20.20.1",   "own gateway (VRRP VIP on BR1-E1)           -> works"),
    ("BR1-GUEST", "10.10.20.1",   "DC guest segment (hub route accepted)      -> works"),
    ("BR1-GUEST", "10.30.20.100", "BR2 guest (branch-to-branch rejected)      -> FAILS"),
    ("BR2-GUEST", "10.20.20.100", "BR1 guest (branch-to-branch rejected)      -> FAILS"),
    ("BR1-GUEST", "10.20.10.100", "corporate PC in VPN 10 (other VPN)         -> FAILS"),
    ("BR2-GUEST", "8.8.8.8",      "Internet, straight out of BR2's INET link  -> works"),
]


def guest():
    """VPN 20 isolation: a guest can reach its gateway, the DC guest segment
    and the Internet, but never another branch's guests or VPN 10."""
    con = Console(SEC.cml_host, SEC.cml_user, SEC.cml_pass)
    for host, dst, why in GUEST_TESTS:
        out = con.run(TITLE, host, [f"ping -c 2 -W 2 {dst}"], login=("cisco", "cisco"), timeout=20)
        loss = next((l for l in out.splitlines() if "packet loss" in l), "no reply")
        print(f"  {host:<10} -> {dst:<13} {loss.strip():<52} # {why}")


def mpls_link():
    c, lab = cml(), state()["lab"]
    return c, lab, c.link_between(lab, DC["label"], "MPLS")["id"]


def degrade(latency=300):
    c, lab, link = mpls_link()
    c.condition(lab, link, latency=latency)
    print(f"Added {latency} ms latency on the cable {DC['label']} Gi2 <-> MPLS. "
          "Every MPLS tunnel to the DC now breaks the 150 ms SLA.")


def restore():
    c, lab, link = mpls_link()
    c.condition(lab, link)
    print("Impairment removed - MPLS is healthy again.")


def ping(host: str, dst: str, count: int = 5):
    """Ping from one of the Alpine hosts, through the CML console."""
    con = Console(SEC.cml_host, SEC.cml_user, SEC.cml_pass)
    print(con.run(TITLE, host, [f"ping -c {count} -W 2 {dst}"], login=("cisco", "cisco"), timeout=40))


def power(label: str, on: int):
    """Power a router off (like pulling the plug) or on again. Its disk is kept."""
    c, lab = cml(), state()["lab"]
    node = next(n["id"] for n in c.nodes(lab) if n["label"] == label)
    (c.start_node if on else c.stop_node)(lab, node)
    print(f"{label} powered {'on' if on else 'off'}")


if __name__ == "__main__":
    cmd, *args = sys.argv[1:] or ["path"]
    if cmd == "edge":
        edge(args[0], *args[1:])
    elif cmd == "ping":
        ping(*args)
    elif cmd == "power":
        power(args[0], int(args[1]))
    else:
        globals()[cmd](*[int(a) for a in args])
