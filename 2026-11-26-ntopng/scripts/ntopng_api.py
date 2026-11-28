#!/usr/bin/env python3
"""Tiny ntopng REST helper (standard library only).

Reads NTOPNG_URL, NTOPNG_ADMIN_USER and NTOPNG_ADMIN_PASSWORD from the environment.
Usage: ntopng_api.py summary | flows [N] | hosts [N] | l7 | alerts [MINUTES]
Each sub-command is a thin wrapper over one REST v2 call; the equivalent curl is in the README.
"""
import base64, json, os, sys, time, urllib.request
from collections import Counter

URL = os.environ.get("NTOPNG_URL", "http://127.0.0.1:3010")
AUTH = base64.b64encode(f"{os.environ['NTOPNG_ADMIN_USER']}:{os.environ['NTOPNG_ADMIN_PASSWORD']}".encode()).decode()

def get(path):
    req = urllib.request.Request(f"{URL}/lua/rest/v2/{path}", headers={"Authorization": f"Basic {AUTH}"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)["rsp"]

def summary():
    d = get("get/interface/data.lua?ifid=0")
    print(f"packets        {d['packets']}")
    print(f"flows (live)   {d['num_flows']}")
    print(f"hosts          {d['num_hosts']} ({d['num_local_hosts']} local)")
    print(f"alerted flows  {d['alerted_flows']}")
    print(f"download       {d['throughput']['download']['bps']/1e6:.2f} Mbit/s")

def flows(n=8):
    rows = get("get/flow/active.lua?ifid=0&currentPage=1&perPage=200")["data"]
    rows.sort(key=lambda r: r["bytes"], reverse=True)
    print(f"{'CLIENT':<16}{'SERVER':<18}{'PORT':<6}{'L7':<17}{'BYTES':>10}")
    for r in rows[:n]:
        print(f"{r['client']['ip']:<16}{r['server']['ip']:<18}{r['server']['port']:<6}{r['protocol']['l7']:<17}{r['bytes']:>10}")

def hosts(n=8):
    rows = get("get/host/active.lua?ifid=0&currentPage=1&perPage=200")["data"]
    rows.sort(key=lambda r: r["bytes"]["total"], reverse=True)
    print(f"{'HOST':<18}{'FLOWS':>6}{'BYTES':>12}  LOCAL")
    for r in rows[:n]:
        print(f"{r['ip']:<18}{r['num_flows']['total']:>6}{r['bytes']['total']:>12}  {r['is_localhost']}")

def l7():
    for r in get("get/interface/l7/stats.lua?ifid=0&ndpistats_mode=count"):
        print(f"{r['label']:<18}{r['value']}")

def alerts(minutes=30):
    now = int(time.time())
    rows = get(f"get/flow/alert/list.lua?ifid=0&status=any&epoch_begin={now-minutes*60}&epoch_end={now+60}&currentPage=1&perPage=3000")["records"]
    c = Counter((r["alert_name"], r["cli_ip"]["ip"]) for r in rows)
    print(f"{'ALERT':<40}{'CLIENT':<16}{'COUNT':>6}")
    for (name, ip), k in c.most_common(8):
        print(f"{name:<40}{ip:<16}{k:>6}")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "summary"
    arg = int(sys.argv[2]) if len(sys.argv) > 2 else None
    {"summary": summary, "flows": flows, "hosts": hosts, "l7": l7, "alerts": alerts}[cmd](*([arg] if arg else []))
