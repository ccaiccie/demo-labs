# Cisco Catalyst SD-WAN on CML – A to Z

A complete Cisco Catalyst SD-WAN lab on Cisco Modeling Labs (CML), built from an empty CML server with Python and the CML and SD-WAN Manager REST APIs. Every script is explained line by line in the video.

Video: [Cisco Catalyst SD-WAN on CML – A to Z: Full Python Build, Policies and Failover](https://youtu.be/-GWzq16rR8U)

## What gets built

| Component | Details |
|-----------|---------|
| Controllers | SD-WAN Manager, Controller and Validator 20.18 (`Manager01`, `Controller01`, `Validator01`, site 100) |
| Edges | 5 x Catalyst 8000V 17.18 in controller mode: `DC-E1` (hub), `BR1-E1` + `BR1-E2` (dual-router branch with VRRP), `BR2-E1`, `BR3-E1` |
| Underlay | One IOL `Gateway` router with three VRFs: `vpn0` (controllers, 172.16.0.0/24), `inet` (biz-internet colour, 172.16.1.0/24, NAT to the real Internet) and `mpls` (mpls colour, 172.16.2.0/24) |
| Service VPNs | VPN 10 `CORP` (full mesh, app-aware routing) and VPN 20 `GUEST` (guest isolation + direct Internet access) |
| Hosts | Alpine Linux PCs at every site (`DC-SRV`, `BR1-PC`, `BR1-GUEST`, `BR2-PC`, `BR2-GUEST`, `BR3-PC`) |
| Config model | Configuration Group `BRANCH-CG` (system, transport and service profiles) and Policy Group `LAB-PG` |
| Policy | `CORP-AAR` app-aware routing with `CRITICAL-SLA` (150 ms, 2 % loss, 50 ms jitter, prefer mpls), `GUEST-DIA` (NAT to the Internet for VPN 20), `GUEST-ISOLATION` custom control policy (no guest site-to-site routes) |
| Trust | A lab root CA created by `sdwanlab/pki.py` (enterprise root CA mode), and a WAN edge serial file |

## Files

| File | Purpose |
|------|---------|
| `lab.yaml` | The single source of truth: sites, addressing, VPNs, colours, BFD timers, SLA |
| `build.py` | The 9 build steps: `python build.py --list`, `python build.py`, `python build.py 5`, `python build.py 3-6` |
| `verify.py` | Read-only checks: control connections, BFD, OMP routes, end-to-end pings |
| `demo.py` | Live demos: `path`, `sla`, `degrade`, `restore`, `guest`, `ping <host> <ip>`, `power <label> 0/1`, `edge <label> "<command>"` |
| `reset.py` | Stop, wipe and delete the lab in CML |
| `sdwanlab/config.py` | Loads `lab.yaml` and the secrets, computes every derived value |
| `sdwanlab/cml.py` | CML REST API client (labs, nodes, links, start/stop) |
| `sdwanlab/manager.py` | SD-WAN Manager REST API client (login, settings, devices, certificates, config groups, tasks) |
| `sdwanlab/pki.py` | The lab root CA: create it, sign CSRs |
| `sdwanlab/render.py` | Renders the CML topology and the day-0 files from `templates/` |
| `sdwanlab/configgroup.py` | Feature profiles, parcels and `BRANCH-CG` |
| `sdwanlab/policy.py` | Policy objects, AAR, DIA, guest isolation, `LAB-PG` |
| `sdwanlab/console.py` | Runs commands on any node through the CML console server |
| `templates/` | Jinja2 day-0 templates (controller cloud-init, Gateway IOS, Alpine hosts) and exported parcel defaults |
| `docs/lessons-learned.md` | Real problems hit while building this lab, and how the code avoids them |

## Build steps

1. Root CA
2. CML topology: controllers, Gateway, switches, hosts
3. First-time Manager settings (organization, Validator, enterprise root CA)
4. Onboard the Validator and the Controller, sign their certificates
5. Upload the WAN edge list (serial file)
6. Configuration group `BRANCH-CG`
7. Edges: associate, variables, deploy, bootstrap, add to CML, boot
8. Wait for the edges to join (control connections and BFD)
9. Policy group `LAB-PG` and the topology group

Every step checks what already exists first, so it is safe to run again.

## Requirements

- CML 2.9 or later with the Catalyst SD-WAN reference images (Manager/Controller/Validator 20.18 and `cat-sdwan-edge` 17.18) and IOL. About 60 GB of RAM for the whole lab.
- CML external connector in `System Bridge` mode on 192.168.122.0/24 (change `management:` in `lab.yaml` for your network).
- A WAN edge serial file for organization `cml-sdwan-lab-tool` in `data/serialFile.viptela`. It is not included here. Use the one that comes with Cisco's CML SD-WAN lab tooling, or download your own from the Cisco Plug and Play portal and change `organization:` in `lab.yaml` to match.
- Python 3.10+ and `pip install -r requirements.txt`.

## Run it

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp lab.env.example lab.env      # fill in the CML and Manager credentials
python build.py --list
python build.py                 # about 60-90 minutes, mostly waiting for boots
python verify.py
python demo.py path             # which tunnel critical traffic uses
python demo.py degrade          # add 300 ms of delay on the DC MPLS cable, then: demo.py sla / path
python demo.py restore
python demo.py guest            # guest isolation and direct Internet access tests
python demo.py power BR1-E1 0   # VRRP failover test; power it back on with 1
python reset.py                 # delete everything
```

## What the tests showed in the recording

- 5 of 5 edges reachable, 3 control connections each, BFD 8/8 (6/6 on the dual-router branch).
- VPN 10 pings between all sites, 0 % loss after ARP.
- Degrading MPLS (600 ms measured mean latency) moved critical traffic to biz-internet ("local color preference ignored"), and back after `restore`.
- Guest isolation: branch guests cannot reach each other or VPN 10, but do reach the DC guest segment and the Internet (8.8.8.8) locally.
- Powering off `BR1-E1`: `BR1-E2` became VRRP master in about 3 seconds, `BR1-PC` kept 0 % loss, and `BR1-E1` took the master role back after rejoining (about 7 minutes to boot).

Credentials are read from `~/cml-secrets.env` or `lab.env`, which are never committed.
