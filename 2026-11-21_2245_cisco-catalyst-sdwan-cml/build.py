#!/usr/bin/env python3
"""Build the Catalyst SD-WAN lab on CML from nothing, one step at a time.

    python build.py            # run every step in order
    python build.py 5          # run only step 5
    python build.py 3-6        # run steps 3 to 6
    python build.py --list     # show the steps

Each step is safe to run again: it checks what already exists first.
"""
from __future__ import annotations

import json
import sys
import time

from sdwanlab import config, configgroup, pki, policy, render
from sdwanlab.cml import CML
from sdwanlab.manager import Manager, ManagerError

CFG = config.load()
SEC = config.secrets()
STATE_FILE = config.STATE / "ids.json"
TITLE = CFG["lab"]["title"]
MGR_IP = CFG["management"]["manager_ip"]


def log(msg: str):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def state() -> dict:
    return json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}


def save(**kw):
    s = state() | kw
    config.STATE.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(s, indent=2))


def cml() -> CML:
    return CML(SEC.cml_host, SEC.cml_user, SEC.cml_pass)


def mgr() -> Manager:
    return Manager(MGR_IP, SEC.mgr_user, SEC.mgr_pass).login()


# =========================================================================
# STEP 1 - our own certificate authority
# =========================================================================
def step1_pki():
    """Create the enterprise root CA that signs every controller certificate."""
    ca = pki.create_root_ca(CFG["organization"])
    log(f"Root CA ready: {pki.CA_CRT}  ({len(ca)} bytes)")


# =========================================================================
# STEP 2 - underlay + control plane in CML
# =========================================================================
def step2_topology():
    """Render the CML topology (controllers, gateway, switches, hosts) and start it."""
    c = cml()
    lab = c.find_lab(TITLE)
    if lab:
        log(f"Lab '{TITLE}' already exists ({lab})")
    else:
        yaml_text = render.topology(CFG, SEC, pki.CA_CRT.read_text())
        (config.STATE / "topology.yaml").write_text(yaml_text)
        # Safety check: a cloud-init file that is not valid YAML is silently
        # ignored by the VM, which then boots with factory defaults.
        import yaml
        for n in yaml.safe_load(yaml_text)["nodes"]:
            for f in n.get("configuration") or []:
                if isinstance(f, dict) and f["name"] == "user-data":
                    yaml.safe_load(f["content"])
        log("Rendered topology; every cloud-init file is valid YAML")
        lab = c.import_lab(TITLE, yaml_text)
        log(f"Imported lab '{TITLE}' -> {lab}  (saved a copy as state/topology.yaml)")
    save(lab=lab)
    c.start_lab(lab)
    log("Lab started. The Manager needs 15-30 minutes for its first boot.")


# =========================================================================
# STEP 3 - first-time Manager settings
# =========================================================================
def step3_manager_settings():
    """Organisation name, Validator FQDN, enterprise CA, data stream."""
    m = Manager(MGR_IP, SEC.mgr_user, SEC.mgr_pass)
    log(f"Waiting for the Manager at https://{MGR_IP} ...")
    m.wait_ready(log=log)
    log("Manager is answering the API")

    if not m.get_setting("organization").get("org"):
        m.setting("organization", {"org": CFG["organization"]})
    log(f"  Organization name  = {CFG['organization']}")
    m.setting("device", {"domainIp": CFG["validator_fqdn"], "port": "12346"})
    log(f"  Validator          = {CFG['validator_fqdn']}:12346")
    m.setting("certificate", {"certificateSigning": "enterprise"}, method="POST")
    m.setting("certificate/enterpriserootca", {"enterpriseRootCA": pki.CA_CRT.read_text()})
    log("  Controller certificate authorization = Enterprise Root CA (ours)")
    m.setting("vedgecloud", {"certificateauthority": "vmanage"})
    log("  WAN edge cloud certificates are signed by the Manager itself")
    m.setting("vmanagedatastream", {"enable": True, "ipType": "systemIp",
                                    "serverHostName": "systemIp", "vpn": 0})
    log("  Statistics data stream over VPN 0 (system IP)")

    # 20.18 shows a first-run wizard in the GUI; mark it as done.
    wf = m.get("/dataservice/workflow?type=ux_initial_setup").get("workflows", [])
    ctx = {"complete": True, "type": "none", "currentStep": 0, "stepsRemaining": 0,
           "version": 1, "navigate": True}
    if wf and not wf[0].get("userContext", {}).get("complete"):
        m.put("/dataservice/workflow", {"id": wf[0]["id"], "type": "ux_initial_setup",
                                         "activities": {"SAVE_ACTION": {"type": "ux_initial_setup",
                                                                        "userContext": ctx | {"id": wf[0]["id"]}}},
                                         "userContext": ctx | {"id": wf[0]["id"]}})
    elif not wf:
        wid = m.post("/dataservice/workflow", {"type": "ux_initial_setup", "userContext": {
            "currentStep": 1, "complete": False, "type": "express", "stepsRemaining": 7,
            "version": 1, "id": None, "navigate": True}})["id"]
        m.put("/dataservice/workflow", {"id": wid, "type": "ux_initial_setup",
                                         "activities": {"SAVE_ACTION": {"type": "ux_initial_setup",
                                                                        "userContext": ctx | {"id": wid}}},
                                         "userContext": ctx | {"id": wid}})
    log("  Initial setup wizard marked complete")


# =========================================================================
# STEP 4 - onboard the Validator and the Controller
# =========================================================================
def step4_controllers():
    """Add Validator + Controller to the Manager and give them certificates."""
    m = mgr()
    cc = CFG["controllers"]
    for key, personality in (("validator", "vbond"), ("controller", "vsmart")):
        ip = cc[key]["ip"]
        try:
            m.add_controller(ip, personality, "admin", SEC.mgr_pass)
            log(f"Added {cc[key]['label']} ({personality}) at {ip}")
        except ManagerError as e:
            if "already" not in str(e).lower():
                raise
            log(f"{cc[key]['label']} already added")

    for d in m.controllers():
        if d.get("serialNumber") != "No certificate installed" or not d.get("deviceIP"):
            continue
        ip = d["deviceIP"]
        log(f"Certificate for {d.get('host-name', ip)}: Manager generates a CSR ...")
        csr = m.generate_csr(ip)
        log("  ... we sign it with our root CA and install the certificate")
        m.wait_task(m.install_cert(pki.sign_csr(csr)), log=log)

    log("Waiting until every control component is reachable ...")
    end = time.time() + 900
    while time.time() < end:
        ctrl = m.controllers()
        bad = [d.get("host-name") or d.get("deviceIP") for d in ctrl
               if d.get("certInstallStatus") != "Installed"
               or d.get("reachability") not in ("reachable", None)]
        if not bad and len(ctrl) >= 3:
            break
        time.sleep(15)
    for d in m.controllers():
        log(f"  {d.get('host-name'):<13} {d.get('personality'):<8} {d.get('deviceIP'):<14} "
            f"cert={d.get('certInstallStatus')}  {d.get('reachability')}")

    # 20.18: the Controller is managed with "control component settings"
    vs = [d for d in m.controllers() if d.get("personality") == "vsmart"]
    uuids = [d["uuid"] for d in vs]
    # make sure the Manager has a fresh copy of the Controller's running config
    m.post("/dataservice/device/action/rediscover",
           {"action": "rediscover", "devices": [{"deviceIP": d["system-ip"]} for d in vs]})
    time.sleep(20)
    for u in uuids:
        m.post(f"/dataservice/v1/control-component/devices/{u}/settings/config-to-settings")
    m.post("/dataservice/v1/control-component/network-settings", {
        "dns": {}, "ntp": {"server": [{"name": "time.google.com", "vpnId": 0, "prefer": False}]},
        "aaa": {"authOrder": ["local"], "ciscoTacRoUser": True, "ciscoTacRwUser": True,
                "user": [{"name": "admin", "password": SEC.mgr_pass}], "accounting": False,
                "adminAuthOrder": False, "authFallback": False,
                "logs": {"auditDisable": False, "netconfDisable": False}},
        "banner": {"enableFeature": False}, "logging": {"enableFeature": False},
        "snmp": {"enableFeature": False},
        "controller": {"omp": {"shutdown": False,
                               "filterRoute": {"outbound": {"affinityGroupPreference": False, "tlocColor": False}},
                               "outboundPolicyCaching": True, "sendBackupPaths": False,
                               "discardRejected": False, "gracefulRestart": True,
                               "timers": {"holdTime": 300, "advertisementInterval": 1,
                                          "gracefulRestartTimer": 43200, "eorTimer": 300}},
                       "hubSpokeTopology": False},
        "security": {"protocol": "dtls"}})
    tid = m.post("/dataservice/v1/control-component/devices/settings/deploy",
                 {"devices": [{"id": u} for u in uuids]})["id"]
    m.wait_task(tid, log=log)
    log("Controller settings deployed (NTP, AAA, OMP timers)")


# =========================================================================
# STEP 5 - WAN edge list
# =========================================================================
def step5_serial_file():
    """Upload the signed list of edge chassis numbers we are allowed to use."""
    m = mgr()
    if len(m.wan_edges()) >= 30:
        log(f"WAN edge list already present ({len(m.wan_edges())} entries)")
        return
    m.upload_serial_file(config.ROOT / CFG["serial_file"])
    edges = m.wan_edges()
    log(f"Uploaded serial file: {len(edges)} C8000V chassis are now authorised")


# =========================================================================
# STEP 6 - configuration group
# =========================================================================
def step6_config_group():
    """Build the BRANCH-CG configuration group (system/transport/service/cli)."""
    m = mgr()
    cg = configgroup.build(m, CFG, SEC.mgr_pass, log=log)
    save(config_group=cg)
    log(f"BRANCH-CG = {cg}")


# =========================================================================
# STEP 7 - edges: assign, deploy, bootstrap, create in CML
# =========================================================================
EDGE_POS = {"DC-E1": (-640, 140), "BR1-E1": (-330, 140), "BR1-E2": (-170, 140),
            "BR2-E1": (80, 140), "BR3-E1": (400, 140)}


def step7_edges():
    """For each edge: pick a chassis, fill the variables, push, bootstrap, boot."""
    m, c, st = mgr(), cml(), state()
    lab, cg = st["lab"], st["config_group"]
    edges = config.all_edges(CFG)

    # 1. pick a chassis number (UUID) from the WAN edge list for each edge
    mapping = st.get("edges", {})
    free = [v["uuid"] for v in m.wan_edges()
            if v.get("deviceModel") == "vedge-C8000V" and v["uuid"] not in mapping.values()
            and not v.get("configGroupId") and v.get("certInstallStatus") is None]
    for e in edges:
        if e["label"] not in mapping:
            mapping[e["label"]] = free.pop(0)
    save(edges=mapping)
    for e in edges:
        log(f"  {e['label']:<7} -> chassis {mapping[e['label']]}")
    uuids = [mapping[e["label"]] for e in edges]

    # 2. associate them with the configuration group
    m.cg_associate(cg, uuids)
    log("Associated the 5 chassis with BRANCH-CG")

    # 3. per-device variables
    allowed = {k for entry in m.cg_variables_schema(cg) for v in entry.get("variables", [])
               for k in v.get("schema", {}).get("properties", {})}
    devs = []
    for e in edges:
        vals = configgroup.device_variables(e, config.site(CFG, e["site"]))
        vals |= {"pseudo_commit_timer": 300, "ipv6_strict_control": False}
        devs.append({"device-id": mapping[e["label"]],
                     "variables": [{"name": k, "value": v} for k, v in vals.items() if k in allowed]})
    m.cg_set_variables(cg, devs)
    log("Variables set (host name, system IP, site ID, interface IPs, VRRP)")

    # 4. deploy = render the final configuration for every device
    m.wait_task(m.cg_deploy(cg, uuids), log=log)
    log("Configuration group deployed (devices are offline, so config is pre-staged)")

    # 5. bootstrap file per edge, then create the router in CML
    nodes = {n["label"]: n for n in c.nodes(lab)}
    sw = {l: nodes[l]["id"] for l in nodes if nodes[l]["node_definition"] == "unmanaged_switch"}
    for e in edges:
        if e["label"] in nodes:
            log(f"{e['label']} already exists in CML")
            continue
        boot = m.bootstrap(mapping[e["label"]])
        (config.STATE / f"bootstrap-{e['label']}.cfg").write_text(boot)
        x, y = EDGE_POS[e["label"]]
        nid = c.add_node(lab, e["label"], "cat-sdwan-edge", x, y,
                         image=CFG["lab"]["edge_image"], config=boot)
        gi = {i["label"]: i["id"] for i in c.interfaces(lab, nid)}
        s = e["site"]
        c.connect(lab, gi["GigabitEthernet1"], c.free_port(lab, sw["INET"]))
        c.connect(lab, gi["GigabitEthernet2"], c.free_port(lab, sw["MPLS"]))
        c.connect(lab, gi["GigabitEthernet3"], c.free_port(lab, sw[f"{s}-LAN10"]))
        c.connect(lab, gi["GigabitEthernet4"], c.free_port(lab, sw[f"{s}-LAN20"]))
        c.start_node(lab, nid)
        log(f"{e['label']}: created with its bootstrap, cabled Gi1-INET Gi2-MPLS Gi3-LAN10 Gi4-LAN20, started")


# =========================================================================
# STEP 8 - wait for the edges to join the overlay
# =========================================================================
def step8_wait_edges():
    """Edges boot (~8 min), contact the Validator, get certs, join the overlay."""
    m, st = mgr(), state()
    want = set(st["edges"].values())
    end = time.time() + 3600
    while time.time() < end:
        ok = {v["uuid"] for v in m.wan_edges()
              if v["uuid"] in want and v.get("reachability") == "reachable"}
        log(f"  {len(ok)}/{len(want)} edges reachable")
        if ok == want:
            break
        time.sleep(30)
    for d in m.devices():
        if d.get("personality") == "vedge" and d.get("uuid") in want:
            log(f"  {d.get('host-name','?'):<7} sys-ip {d.get('system-ip','-'):<12} site {d.get('site-id','-'):<3} "
                f"control={d.get('controlConnections')} bfd={d.get('bfdSessionsUp')}/{d.get('bfdSessions')}")


# =========================================================================
# STEP 9 - centralized policy
# =========================================================================
def step9_policy():
    """Policy group (AAR + guest DIA) to the edges, topology group to the Controller."""
    m, st = mgr(), state()
    # 1. build (or update) the policy group content first, so the stored
    #    policy already uses the right VPN names before anything is deployed
    pg = policy.build(m, CFG, log=log)
    # 2. topology group -> Controller (VPN 10 mesh, VPN 20 guest isolation).
    #    The Controller's config also embeds LAB-PG, which is why step 1 is first.
    tg = policy.build_topology(m, CFG, log=log)
    r = m.post(f"/dataservice/v1/topology-group/{tg}/device/deploy", {"deactivateTopology": False})
    log(f"  topology deploy -> {r}")
    if isinstance(r, dict) and (r.get("parentTaskId") or r.get("id")):
        m.wait_task(r.get("parentTaskId") or r.get("id"), log=log)
    log("Topology group deployed to the Controller (VPN 10 full mesh, VPN 20 guest isolation)")
    # 3. push the traffic policies (AAR + DIA) to the edges
    policy.deploy(m, pg, list(st["edges"].values()), log=log)
    log("Policy group LAB-PG deployed to all edges")
    save(policy_group=pg, topology_group=tg)


STEPS = [step1_pki, step2_topology, step3_manager_settings, step4_controllers,
         step5_serial_file, step6_config_group, step7_edges, step8_wait_edges, step9_policy]


def main(argv):
    if "--list" in argv:
        for i, s in enumerate(STEPS, 1):
            print(f"{i}. {s.__doc__}")
        return
    sel = range(1, len(STEPS) + 1)
    if argv:
        a = argv[0]
        sel = range(int(a.split("-")[0]), int(a.split("-")[-1]) + 1)
    for i in sel:
        log(f"===== STEP {i}: {STEPS[i - 1].__doc__}")
        STEPS[i - 1]()


if __name__ == "__main__":
    main(sys.argv[1:])
