#!/usr/bin/env python3
"""Prove the overlay works, using the same data the Manager GUI shows.

    python verify.py            # control plane, data plane, routes, pings
    python verify.py pings      # only the host-to-host tests

Everything here is read-only.
"""
from __future__ import annotations

import sys

from sdwanlab import config
from sdwanlab.console import Console
from build import CFG, SEC, TITLE, mgr, log


def control_plane(m):
    print("\n== Devices (Monitor > Devices) ==")
    print(f"{'host':<13}{'type':<10}{'system-ip':<14}{'site':<6}{'state':<12}{'control'}")
    for d in sorted(m.devices(), key=lambda d: d["system-ip"]):
        print(f"{d['host-name']:<13}{d['personality']:<10}{d['system-ip']:<14}{d['site-id']:<6}"
              f"{d.get('reachability',''):<12}{d.get('controlConnections','-')}")

    for e in config.all_edges(CFG):
        ip = e["system_ip"]
        print(f"\n== {e['label']} ({ip}) ==")
        print("  control connections (DTLS to Validator / Controller / Manager):")
        for c in m.rt("control/connections", ip):
            print(f"    {c['peer-type']:<8} {c['system-ip']:<14} via {c['local-color']:<13} {c['state']}")
        print("  BFD sessions (IPsec tunnels to the other edges):")
        for b in m.rt("bfd/sessions", ip):
            print(f"    -> {b['system-ip']:<13} {b['local-color']:>12} -> {b['color']:<13} {b['state']}")
        routes = m.rt("omp/routes/received", ip)
        print(f"  OMP routes received from the Controller: {len(routes)}")
        for r in routes[:12]:
            print(f"    vpn {r['vpn-id']:<3} {r['prefix']:<16} from {r.get('originator','?'):<13}"
                  f" tloc {r.get('color','')}  {r.get('status','')}")


PINGS = [
    ("BR1-PC", "10.10.10.100", "branch 1 -> data-centre server (VPN 10)"),
    ("BR2-PC", "10.20.10.100", "branch 2 -> branch 1 PC, direct spoke-to-spoke (VPN 10)"),
    ("BR3-PC", "10.30.10.100", "branch 3 -> branch 2 PC (VPN 10)"),
    ("BR1-GUEST", "10.20.10.100", "guest -> corporate PC: must FAIL, different VPN"),
    ("BR1-GUEST", "1.1.1.1", "guest -> Internet (direct Internet access)"),
]


def pings():
    con = Console(SEC.cml_host, SEC.cml_user, SEC.cml_pass)
    print("\n== Host tests (through the CML console) ==")
    for host, dst, why in PINGS:
        out = con.run(TITLE, host, [f"ping -c 3 -W 2 {dst}"], login=("cisco", "cisco"), timeout=20)
        loss = next((l for l in out.splitlines() if "packet loss" in l), "no reply")
        print(f"  {host:<10} ping {dst:<14} {loss.strip():<55} # {why}")


if __name__ == "__main__":
    if sys.argv[1:] == ["pings"]:
        pings()
    else:
        control_plane(mgr())
        pings()
