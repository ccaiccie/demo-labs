#!/usr/bin/env python3
"""
FTD-through-FMC automation demo.
Run everything:      python3 demo.py
Run one step:        python3 demo.py --step 4
Recording mode:      DEMO_PAUSE=1 python3 demo.py   (waits for Enter before each step)
Every step is idempotent: re-running it finds what already exists instead of duplicating it.
"""
import argparse, time, yaml, paramiko
from fmc_client import FMC, load_secrets
from narrate import step, info, ok, warn

CFG = yaml.safe_load(open("lab.yaml"))
SEC = load_secrets()
fmc = None
def api():
    global fmc
    if fmc is None:
        info(f"Logging in to the FMC REST API at https://{CFG['fmc']['host']} ...")
        fmc = FMC(CFG["fmc"]["host"], CFG["fmc"]["username"], SEC["LAB_ADMIN_PW"])
        ok(f"Got an API token (domain {fmc.domain})")
    return fmc

def devices_by_name():
    return {d["name"]: d for d in api().get_all("devices/devicerecords")}

# ---------------------------------------------------------------------------
def s1_license():
    step(1, "Turn on the FMC evaluation license",
         "A brand-new FMC is unlicensed, and it will not accept firewalls until it has a license. "
         "For a lab we use the built-in 90-day evaluation mode, so no Cisco Smart Account is needed. "
         "This is one API call to the license endpoint.")
    f = api(); lic = f.get("/api/fmc_platform/v1/license/smartlicenses")["items"][0]
    info(f"Current license status: {lic['regStatus']}")
    if lic["regStatus"] in ("EVALUATION", "REGISTERED"):
        ok("Already licensed - nothing to do"); return
    f.post("/api/fmc_platform/v1/license/smartlicenses", {"registrationType": "EVALUATION"})
    lic = f.get("/api/fmc_platform/v1/license/smartlicenses")["items"][0]
    ok(f"License status is now {lic['regStatus']}")

def s2_objects():
    step(2, "Create the shared building blocks: zones, network objects and an access policy",
         "FMC config is object-based. Before touching any firewall we create the reusable pieces: "
         "two security zones (inside and outside) that interfaces will join, network objects for each "
         "inside LAN and the upstream gateway, and an empty Access Control Policy whose default action "
         "is BLOCK. A device must have an access policy assigned at the moment it is registered.")
    f = api()
    for z in CFG["zones"]:
        o, new = f.get_or_create("object/securityzones", {"type": "SecurityZone", "name": z["name"], "interfaceMode": "ROUTED"})
        ok(f"Security zone {z['name']} ({'created' if new else 'already exists'})")
    for d in CFG["devices"]:
        n = d["inside_network"]
        o, new = f.get_or_create("object/networks", {"type": "Network", "name": n["name"], "value": n["value"]})
        ok(f"Network object {n['name']} = {n['value']} ({'created' if new else 'exists'})")
    gws = {d["default_gateway"] for d in CFG["devices"]}
    for gw in gws:
        o, new = f.get_or_create("object/hosts", {"type": "Host", "name": "Outside-GW", "value": gw})
        ok(f"Host object Outside-GW = {gw} ({'created' if new else 'exists'})")
    body = {"type": "AccessPolicy", "name": CFG["access_policy"],
            "defaultAction": {"action": "BLOCK", "logBegin": True, "sendEventsToFMC": True}}
    o, new = f.get_or_create("policy/accesspolicies", body)
    ok(f"Access Control Policy {CFG['access_policy']} with default action BLOCK ({'created' if new else 'exists'})")

def ftd_cli(ip, commands, wait=6):
    """Open an SSH session to the FTD CLI and run commands at the '>' prompt."""
    c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(ip, username="admin", password=SEC["LAB_ADMIN_PW"], look_for_keys=False, allow_agent=False, timeout=30)
    ch = c.invoke_shell(width=200); time.sleep(3); ch.recv(65535); out = ""
    for cmd in commands:
        ch.send(cmd + "\n"); time.sleep(wait)
        while ch.recv_ready(): out += ch.recv(65535).decode(errors="replace")
    c.close(); return out.replace(SEC["LAB_REG_KEY"], "<reg-key>")

def s3_register():
    step(3, "Register both FTDs with FMC",
         "Registration is a two-sided handshake. On each FTD we run 'configure manager add' with the FMC "
         "address, a one-time registration key and a NAT ID. Then we tell FMC about the device through the "
         "API, using the same key and NAT ID, plus the access policy, the license tier and the performance "
         "tier. FMC connects to the FTD on TCP 8305, they swap certificates, and FMC pushes its first policy. "
         "This step takes several minutes per device.")
    f = api(); acp = f.find("policy/accesspolicies", CFG["access_policy"]); have = devices_by_name()
    for d in CFG["devices"]:
        if d["name"] in have: ok(f"{d['name']} is already registered"); continue
        info(f"SSH to {d['name']} ({d['mgmt_ip']}) and point it at FMC:")
        for attempt in range(20):
            out = ftd_cli(d["mgmt_ip"], [f"configure manager add {CFG['fmc']['host']} {SEC['LAB_REG_KEY']} {d['nat_id']}", "show managers"])
            if "successfully configured" in out or "already" in out.lower(): break
            warn(f"{d['name']} is not ready yet (still finishing a previous unregistration) - retrying in 30 seconds"); time.sleep(30)
        print(out.strip()[-700:])
        body = {"type": "Device", "name": d["name"], "hostName": d["mgmt_ip"], "regKey": SEC["LAB_REG_KEY"],
                "natID": d["nat_id"], "license_caps": ["ESSENTIALS"], "performanceTier": d["performance_tier"],
                "accessPolicy": {"id": acp["id"], "type": "AccessPolicy"}}
        info(f"Asking FMC to add {d['name']} ...")
        r = f.post("devices/devicerecords", body)
        task = r.get("metadata", {}).get("task", {}).get("id")
        if task:
            info(f"FMC started registration task {task}; checking every 15 seconds ...")
            f.wait_task(task, timeout=2400, label=f"register {d['name']}")
        ok(f"{d['name']} registered")
    for name, dev in devices_by_name().items():
        ok(f"FMC now manages {name}: model={dev.get('model')} version={dev.get('sw_version')}")

def s4_interfaces():
    step(4, "Configure the data interfaces",
         "Each FTD gets two routed interfaces. Ethernet0/0 is named 'outside', gets a static address "
         "on the 192.168.200.0/24 upstream network and joins outside-zone. Ethernet0/1 is named "
         "'inside', becomes the gateway for that firewall's LAN and joins inside-zone. In the API, that means "
         "reading each physical interface record, changing it and PUTting it back.")
    f = api(); devs = devices_by_name(); zones = {z["name"]: z for z in f.get_all("object/securityzones")}
    for d in CFG["devices"]:
        dev = devs[d["name"]]
        phys = {p["name"]: p for p in f.get_all(f"devices/devicerecords/{dev['id']}/physicalinterfaces")}
        for i in d["interfaces"]:
            p = phys[i["hw"]]
            body = {"type": "PhysicalInterface", "id": p["id"], "name": i["hw"], "ifname": i["ifname"], "enabled": True,
                    "mode": "NONE", "MTU": 1500, "securityZone": {"id": zones[i["zone"]]["id"], "type": "SecurityZone"},
                    "ipv4": {"static": {"address": i["ip"], "netmask": str(i["mask"])}}}
            f.put(f"devices/devicerecords/{dev['id']}/physicalinterfaces/{p['id']}", body)
            ok(f"{d['name']} {i['hw']} -> nameif '{i['ifname']}', {i['ip']}/{i['mask']}, zone {i['zone']}")

def s5_routes():
    step(5, "Add a default route on each FTD",
         "The firewalls need to know where the internet is. We add a static default route (any-ipv4) out the "
         "'outside' interface toward the upstream gateway 192.168.200.1, which NATs traffic onward.")
    f = api(); devs = devices_by_name()
    anyv4 = f.find("object/networks", "any-ipv4"); gw = f.find("object/hosts", "Outside-GW")
    for d in CFG["devices"]:
        dev = devs[d["name"]]; path = f"devices/devicerecords/{dev['id']}/routing/ipv4staticroutes"
        if any(r.get("interfaceName") == "outside" for r in f.get_all(path)):
            ok(f"{d['name']}: default route already present"); continue
        f.post(path, {"type": "IPv4StaticRoute", "interfaceName": "outside", "metricValue": 1,
                      "selectedNetworks": [{"type": "Network", "id": anyv4["id"]}],
                      "gateway": {"object": {"type": "Host", "id": gw["id"]}}})
        ok(f"{d['name']}: 0.0.0.0/0 via {d['default_gateway']} on outside")

def s6_rules():
    step(6, "Write the access control rules",
         "Access Control Policy rules are checked top-down. We add one rule that allows the inside LANs out to "
         "the outside zone, with connection logging turned on so the traffic shows up in FMC. Anything that "
         "doesn't match falls through to the policy's default action, BLOCK.")
    f = api(); acp = f.find("policy/accesspolicies", CFG["access_policy"])
    zones = {z["name"]: z for z in f.get_all("object/securityzones")}
    nets = [f.find("object/networks", d["inside_network"]["name"]) for d in CFG["devices"]]
    path = f"policy/accesspolicies/{acp['id']}/accessrules"
    if f.find(path, "Allow-Inside-to-Outside"): ok("Rule Allow-Inside-to-Outside already exists"); return
    f.post(path, {"type": "AccessRule", "name": "Allow-Inside-to-Outside", "action": "ALLOW", "enabled": True,
                  "sourceZones": {"objects": [{"id": zones["inside-zone"]["id"], "type": "SecurityZone"}]},
                  "destinationZones": {"objects": [{"id": zones["outside-zone"]["id"], "type": "SecurityZone"}]},
                  "sourceNetworks": {"objects": [{"id": n["id"], "type": "Network"} for n in nets]},
                  "logEnd": True, "sendEventsToFMC": True})
    ok("Rule 1: Allow-Inside-to-Outside (inside-zone -> outside-zone), logging at connection end")

def s7_nat():
    step(7, "Create NAT so the inside LANs can reach the internet",
         "Private 10.x addresses can't be routed upstream, so we create an FTD NAT policy with one dynamic "
         "auto-NAT rule per inside network. Each rule hides the LAN behind the firewall's own outside interface "
         "address (interface PAT). Then we assign the NAT policy to both firewalls.")
    f = api(); devs = devices_by_name(); zones = {z["name"]: z for z in f.get_all("object/securityzones")}
    nat, new = f.get_or_create("policy/ftdnatpolicies", {"type": "FTDNatPolicy", "name": CFG["nat_policy"]})
    ok(f"NAT policy {CFG['nat_policy']} ({'created' if new else 'exists'})")
    path = f"policy/ftdnatpolicies/{nat['id']}/autonatrules"; existing = f.get_all(path)
    for d in CFG["devices"]:
        net = f.find("object/networks", d["inside_network"]["name"])
        if any(r.get("originalNetwork", {}).get("id") == net["id"] for r in existing):
            ok(f"Auto-NAT for {net['name']} already present"); continue
        f.post(path, {"type": "FTDAutoNatRule", "natType": "DYNAMIC", "interfaceInTranslatedNetwork": True,
                      "originalNetwork": {"id": net["id"], "type": "Network"},
                      "sourceInterface": {"id": zones["inside-zone"]["id"], "type": "SecurityZone"},
                      "destinationInterface": {"id": zones["outside-zone"]["id"], "type": "SecurityZone"}})
        ok(f"Auto-NAT: {net['name']} -> outside interface (PAT)")
    f.post("assignment/policyassignments", {"type": "PolicyAssignment", "policy": {"type": "FTDNatPolicy", "id": nat["id"]},
           "targets": [{"id": devs[d["name"]]["id"], "type": "Device"} for d in CFG["devices"]]}) \
        if not f.find("assignment/policyassignments", CFG["nat_policy"]) else None
    ok("NAT policy assigned to ftd1 and ftd2")

def s8_deploy():
    step(8, "Deploy",
         "So far, everything only exists in FMC's database. Nothing changes on a firewall until you deploy. "
         "We wait until FMC reports every firewall ready, deploy all pending changes in one request, track "
         "the job, then check again until nothing is left pending.")
    f = api(); want = {d["name"] for d in CFG["devices"]}
    for rnd in range(1, 6):
        for _ in range(40):                      # wait until every device is either pending or fully deployed
            pend = f.get_all("deployment/deployabledevices"); names = {p["name"] for p in pend}
            states = {d["name"]: d.get("deploymentStatus") for d in f.get_all("devices/devicerecords")}
            if all(n in names or states.get(n) == "DEPLOYED" for n in want): break
            info("Waiting for FMC to finish preparing the devices ..."); time.sleep(15)
        if not pend: ok("No pending changes - all devices are in sync"); return
        ver = max(int(p["version"]) for p in pend); ids = [p["device"]["id"] for p in pend]
        info(f"Round {rnd}: deploying to {', '.join(sorted(names))}")
        r = f.post("deployment/deploymentrequests", {"type": "DeploymentRequest", "version": str(ver), "forceDeploy": False,
                   "ignoreWarning": True, "deviceList": ids})
        task = r["metadata"]["task"]["id"]; info(f"Deployment task {task} started; checking every 15 seconds ...")
        f.wait_task(task, timeout=2400, label="deployment"); ok(f"Deployment to {', '.join(sorted(names))} finished")
        time.sleep(20)
    warn("Devices still show pending changes after 5 rounds")

def s9_verify():
    step(9, "Prove it works: traffic from the test PCs",
         "Each firewall has an Ubuntu test PC on its inside LAN. We give each PC an address and point its "
         "default gateway at the firewall's inside interface. Then we ping and fetch a web page on the internet. "
         "If that works, the traffic went through the interfaces, the route, the access rule and NAT we just "
         "pushed. Then we check the FTD's NAT hit counters and connection table to see it from the firewall's side.")
    import subprocess
    pcs = [("Ubuntu-Test-1", "10.1.1.10/24", "10.1.1.1", "192.168.100.11"),
           ("Ubuntu-Test-2", "10.2.2.10/24", "10.2.2.1", "192.168.100.12")]
    for name, ip, gw, ftd in pcs:
        c = subprocess.run(["docker", "ps", "--filter", f"name=GNS3.{name}.", "--format", "{{.Names}}"],
                           capture_output=True, text=True).stdout.strip()
        if not c: warn(f"{name} container is not running - start it in GNS3"); continue
        sh = lambda cmd: subprocess.run(["docker", "exec", "--privileged", c, "sh", "-c", cmd], capture_output=True, text=True)
        sh(f"ip addr flush dev eth0; ip addr add {ip} dev eth0; ip link set eth0 up; ip route replace default via {gw}; "
           "echo nameserver 1.1.1.1 > /etc/resolv.conf")
        ok(f"{name}: {ip}, default gateway {gw}")
        r = sh("ping -c 3 -W 2 1.1.1.1 | tail -2"); print("     " + r.stdout.strip().replace("\n", "\n     "))
        r = sh("curl -s -o /dev/null -m 10 -w 'HTTP %{http_code}' https://www.cisco.com || (wget -q -T 10 -O /dev/null https://www.cisco.com && echo 'HTTP 200')")
        ok(f"{name}: HTTPS to www.cisco.com -> {r.stdout.strip() or r.stderr.strip()[:80]}")
        out = ftd_cli(ftd, ["show nat | include hits", "show conn count"], wait=5)
        for line in out.splitlines():
            if ("translate_hits" in line or "in use" in line) and "show" not in line: print("     FTD> " + line.strip())

STEPS = {1: s1_license, 2: s2_objects, 3: s3_register, 4: s4_interfaces, 5: s5_routes, 6: s6_rules, 7: s7_nat, 8: s8_deploy, 9: s9_verify}
if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--step", type=int); a = ap.parse_args()
    for n in ([a.step] if a.step else sorted(STEPS)): STEPS[n]()
    print("\nDone.")
