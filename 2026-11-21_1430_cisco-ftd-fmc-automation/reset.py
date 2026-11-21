#!/usr/bin/env python3
"""Wipe everything demo.py builds so the demo can be recorded from scratch."""
import time, subprocess
from demo import api, devices_by_name, ftd_cli, CFG
from narrate import info, ok, warn
f = api()
for name, dev in devices_by_name().items():
    info(f"Deleting device {name} from FMC ..."); f.req("DELETE", f"devices/devicerecords/{dev['id']}"); ok(f"{name} deleted")
for _ in range(40):
    if not devices_by_name(): break
    time.sleep(15)
for path, names in [("policy/ftdnatpolicies", [CFG["nat_policy"]]), ("policy/accesspolicies", [CFG["access_policy"]]),
                    ("object/networks", [d["inside_network"]["name"] for d in CFG["devices"]]),
                    ("object/hosts", ["Outside-GW"]), ("object/securityzones", [z["name"] for z in CFG["zones"]])]:
    for n in names:
        o = f.find(path, n)
        if o:
            for attempt in range(6):
                try: f.req("DELETE", f"{path}/{o['id']}"); ok(f"Deleted {path.split('/')[-1]} {n}"); break
                except RuntimeError as e: warn(f"retry {n}: {str(e)[:120]}"); time.sleep(20)
for d in CFG["devices"]:
    for attempt in range(30):
        out = ftd_cli(d["mgmt_ip"], ["configure manager delete", "show managers"], wait=8)
        if "No managers configured" in out or "not configured" in out.lower(): break
        info(f"{d['name']}: still unregistering, waiting ..."); time.sleep(20)
    ok(f"{d['name']}: no manager configured")
for pc in ["Ubuntu-Test-1", "Ubuntu-Test-2"]:
    c = subprocess.run(["docker", "ps", "--filter", f"name=GNS3.{pc}.", "--format", "{{.Names}}"], capture_output=True, text=True).stdout.strip()
    if c: subprocess.run(["docker", "exec", "--privileged", c, "sh", "-c", "ip addr flush dev eth0; ip route flush default"]); ok(f"{pc}: IP removed")
ok("Reset complete")
