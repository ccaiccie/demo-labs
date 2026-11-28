# ISE 802.1X and MAB with FTD Internet Egress — Cisco Modeling Labs

A complete wired-access lab built in **Cisco Modeling Labs (CML) 2.10**:

- **Cisco ISE 3.5** authenticates a computer with **802.1X** (PEAP/MSCHAPv2, user `employee1` → VLAN 10) and a Linux device with **MAC Authentication Bypass (MAB)** (→ VLAN 30).
- The access switch is a **Catalyst 9000v (UADP)** — the CML switch image whose 802.1X/MAB authenticator actually forms sessions (IOSvL2 and IOL-L2 accept the config but never start a session; a second, parked Catalyst 9000v Q200 node is included in the export as a stopped spare and can be deleted).
- A locally managed **Firepower Threat Defense (FTDv, FDM — no FMC)** is the gateway for all three VLANs (10 users / 20 services / 30 IoT), runs DHCP for VLANs 10 and 30, PATs egress to the internet, and enforces an **AD-backed captive portal** (Samba AD domain controller, LAB.LOCAL) before users can browse out.
- Verification is end to end: ISE authorization profiles place the VLANs, `show access-session` on the access switch proves both authentications, IoT is blocked from the internet but can reach the inside web server.

## Contents

| File | What it is |
|------|------------|
| `ise-ftd-cml-lab-guide.md` | The full step-by-step guide: topology, addressing, every FDM and ISE GUI step, switch configuration, endpoint setup, verification (Part 9 scorecard) and troubleshooting. |
| `ise-8021x-mab-ftd-egress-lab.yaml` | The exported CML topology (nodes, links and node configurations) — import it into your own CML to get the as-built lab. |
| `configs/acc-sw-c9k-full.txt` | The complete Catalyst 9000v access-switch configuration (AAA, RADIUS to ISE, IBNS 2.0 policy maps, dot1x/MAB ports). |
| `configs/core-sw-l2.txt` | The CORE-SW (IOSvL2) aggregation switch configuration. |
| `api/fdm-configure.sh` | The FTD configuration from the guide's Part 4 as FDM REST API calls: objects, AD realm, NAT, access rules, identity rule, deployment. |
| `api/ise-configure.sh` | The ISE configuration from Part 6 as REST API calls: ERS for devices, user, endpoint group/MAC and authorization profiles; the OpenAPI for the policy-set rules. |
| `api/README.md` | How the API scripts map to the guide, prerequisites, and scope notes. |
| `endpoints/` | Endpoint setup as scripts: PC1's 802.1X supplicant, LINUX1's MAB networking, WEB1's web server, ADMIN-PC's operator setup. |

## Requirements

- **Your own CML subscription/entitlement.** The topology export contains no Cisco images. You need your own licensed CML images for ISE 3.5, FTDv, and Catalyst 9000v (UADP) — they are not redistributable and are not included here.
- All credentials in the guide and topology are lab-invented values created for this lab only.

## Verification scorecard (as built)

| Flow | Result |
|------|--------|
| 802.1X — PC1 as `employee1`, ISE assigns VLAN 10 | ✅ Pass |
| MAB — LINUX1 by MAC, ISE assigns VLAN 30 | ✅ Pass |
| Captive portal — AD sign-in before internet egress | ✅ Pass |
| IoT VLAN blocked from the internet (IOT-BLOCK) | ✅ Pass |
| LINUX1 → WEB1 (HTTP) | ✅ Pass |
| Outside static NAT forward :8080 → WEB1 | ⚠️ Configuration verified end to end; on this FTD build the data plane drops traffic addressed to the firewall's own DHCP-assigned outside address ("self-addressed" divert in packet-tracer, no un-NAT phase). Workarounds — static outside address, or an explicit public-IP object instead of the `interface` keyword — are documented in the guide's Troubleshooting section. |
