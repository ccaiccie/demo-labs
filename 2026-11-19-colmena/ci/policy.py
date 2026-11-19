#!/usr/bin/env python3
"""Policy check for AI-proposed changes: compares data/*.json on this branch with main."""
import ipaddress, json, re, subprocess, sys

LAB_NET = ipaddress.ip_network("10.88.0.0/24")
PROTECTED = {"router1", "dns1", "monitor1"}
ALLOWED_PORTS = {53, 80, 443, 8080, 9090, 9100}

def load(ref, path):
    out = subprocess.run(["git", "show", f"{ref}:{path}"], capture_output=True, text=True, check=True).stdout
    return json.loads(out)

def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "main"
    errors, changed = [], set()
    old, new = load(base, "data/dns-records.json"), load("HEAD", "data/dns-records.json")
    for name, ip in new.items():
        if old.get(name) == ip:
            continue
        print(f"  dns: {name}.lab -> {ip}")
        changed.add("dns1")
        if name in PROTECTED:
            errors.append(f"{name} is an infrastructure record and cannot be changed by a request")
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,30}", name):
            errors.append(f"bad record name {name!r}")
        try:
            if ipaddress.ip_address(ip) not in LAB_NET:
                errors.append(f"{ip} is outside the lab network {LAB_NET}")
        except ValueError:
            errors.append(f"{ip!r} is not an IPv4 address")
    for name in old.keys() - new.keys():
        errors.append(f"removing record {name} needs a human review")
    old, new = load(base, "data/firewall.json"), load("HEAD", "data/firewall.json")
    for node, rules in new.items():
        if node not in old:
            errors.append(f"unknown node {node}")
            continue
        for proto in ("tcp", "udp"):
            for port in set(rules.get(proto, [])) - set(old[node].get(proto, [])):
                print(f"  firewall: open {proto}/{port} on {node}")
                changed.add(node)
                if port not in ALLOWED_PORTS:
                    errors.append(f"{proto}/{port} is not in the allowed port list {sorted(ALLOWED_PORTS)}")
    if len(changed) > 1:
        errors.append("a request may change only one node")
    if not changed and not errors:
        errors.append("no change found")
    for e in errors:
        print(f"  POLICY FAIL: {e}")
    print("  POLICY PASS" if not errors else "  POLICY REJECTED")
    sys.exit(1 if errors else 0)

main()
