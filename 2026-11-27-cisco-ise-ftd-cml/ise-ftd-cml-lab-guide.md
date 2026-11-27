# Cisco ISE 802.1X & MAB with FTD Internet Egress — CML Lab Guide

Build a complete wired-access lab in Cisco Modeling Labs (CML): Cisco ISE 3.5 authenticates a
computer with 802.1X and a Linux device with MAC Authentication Bypass (MAB) through two
switches, and a locally managed Cisco FTD provides internet egress with static NAT
port-forwards and user authentication (captive portal) before anyone can browse out.

## What you will build

- **ISE 3.5** — RADIUS server for the switches; one 802.1X policy (internal user) and one MAB
  policy (endpoint MAC), landing devices in **different VLANs** so the two methods are easy to
  tell apart in the ISE Live Log.
- **FTDv 10.0, locally managed (FDM)** — edge firewall: dynamic PAT for egress, a **static NAT
  port-forward** (outside TCP/8080 → inside web server TCP/80), DHCP for the user/IoT VLANs,
  and an **identity rule**: inside users must sign in on a captive portal before internet access.
- **Two switches** — CORE-SW (IOSvL2; aggregation, ISE/server/admin attached) and ACC-SW
  (**Catalyst 9000v**; access layer: the 802.1X port and the MAB port — see the platform
  warning in Prerequisites for why the access switch must be the 9000v).
- **A Samba Active Directory DC (AD-DC1)** — FDM captive-portal authentication only works
  against an AD/LDAP realm, so the lab includes a small LAB.LOCAL domain controller that
  holds the portal user account.
- **Endpoints** — an Ubuntu desktop as the 802.1X supplicant PC, an Alpine Linux device with no
  supplicant (MAB), an nginx web server (port-forward target), and an admin PC used to drive the
  ISE and FDM web GUIs.

## Topology

```
                 CML NAT (internet)
                       |
                  [ INTERNET ]            external connector
                       | Gi0/0 (outside, DHCP)
                     [ FTD ]  Gi0/1 = 802.1Q trunk (VLAN 10/20/30 gateways)
                       | Gi0/1            Mgmt0/0 → VLAN 20 (FDM GUI)
                       | Gi0/0 trunk
                   [ CORE-SW ]---- Gi0/2 ---- [ ISE ]        10.10.20.10 (VLAN 20)
                       |  \------- Gi1/0 ---- [ WEB1 ]       10.10.20.20 (VLAN 20)
                       |  \------- Gi1/1 ---- [ ADMIN-PC ]   10.10.20.50 (VLAN 20)
                       | Gi0/1 trunk
                   [ ACC-SW ]  (Catalyst 9000v)
                       | Gi1/0/2 (802.1X) ---- [ PC1 ]         → VLAN 10 after auth
                       | Gi1/0/3 (MAB)    ---- [ LINUX1 ]      → VLAN 30 after auth
                       | Gi1/0/4 (VLAN 20) --- [ AD-DC1 ]      10.10.20.60 (Samba AD)
```

## IP addressing

| Segment | Subnet | Gateway (FTD) | Notes |
|---|---|---|---|
| VLAN 10 USERS | 10.10.10.0/24 | 10.10.10.1 | DHCP pool 10.10.10.100–200 from FTD |
| VLAN 20 SERVICES | 10.10.20.0/24 | 10.10.20.1 | Static addressing (table below) |
| VLAN 30 IOT-MAB | 10.10.30.0/24 | 10.10.30.1 | DHCP pool 10.10.30.100–200 from FTD |

| Device | Address |
|---|---|
| ISE (ise1) | 10.10.20.10/24 |
| CORE-SW SVI VLAN 20 | 10.10.20.2/24 |
| ACC-SW SVI VLAN 20 | 10.10.20.3/24 |
| FTD management (FDM) | 10.10.20.5/24 |
| WEB1 (nginx) | 10.10.20.20/24 |
| ADMIN-PC | 10.10.20.50/24 |
| AD-DC1 (Samba AD DC, LAB.LOCAL) | 10.10.20.60/24 |
| PC1 (802.1X) | DHCP (VLAN 10) |
| LINUX1 (MAB) | DHCP (VLAN 30) |

Lab credentials (change them in your own build): ISE **GUI** admin `admin / LabISE-2027!`
(see the forced first-login password reset in Part 5 — the GUI password changes; the ISE
**CLI** admin stays `admin / LabISE-2026!`), FTD admin `admin / LabFTD-2026!`, RADIUS shared
secret `LabRadius-2026`, 802.1X user `employee1 / Employee-2026!`, captive-portal user
`webuser / WebUser-2026!` (an AD account on AD-DC1), Samba AD Administrator
`Administrator / LabAdmin-2026!`. The desktop nodes (ADMIN-PC, PC1, AD-DC1) use the stock
image login `ubuntu / ubuntu`; LINUX1 (Alpine) uses `cisco / cisco`.
LINUX1 MAC address (pinned in CML): `52:54:00:10:30:01`. PC1 MAC: `52:54:00:10:10:01`.

## Prerequisites

- CML 2.10 (the lab was built on CML 2.10.0) with a valid CML subscription — the Cisco images
  are **not** redistributable; you need your own CML entitlement for the reference platforms.
- Reference platform images: ISE 3.5.0.527 (refplat ISE pack), FTDv 10.0.0, IOSvL2 (CORE-SW
  only), **Catalyst 9000v UADP (cat9000v-uadp, IOS XE 17.18.02) for ACC-SW**, Ubuntu
  24.04 Desktop, Alpine, nginx, external connector.
- ⚠️ **Switch platform matters**: do not use IOSvL2 or IOL-L2 XE for the access switch.
  Both accept the full 802.1X/MAB configuration but never start an authentication session
  in CML — no session forms, and the RADIUS server sees zero requests (verified with full
  debugs and a force-authorized control test; the IOSvL2 authenticator is a silent no-op).
  The Catalyst 9000v is the CML switch image with a working port authenticator.
- Host sizing used here: CML VM 32 vCPU / 128 GB RAM. ISE is the heavy node (16 GB RAM);
  the ISE node CPU count was lowered to 8 for this lab.

---

## Part 1 — Build the topology in CML

> Shortcut: this repo also ships the exported topology
> (`ise-8021x-mab-ftd-egress-lab.yaml`, exported from the working lab). Importing it into
> CML creates the nodes, links and node configurations in one step; you still supply the
> licensed images from your own CML subscription and then follow Parts 2–9 to configure
> the devices. The parked **ACC-SW-Q200** node in the export is a stopped spare (see the
> Q200 note in Troubleshooting) and can be deleted.

1. Create a lab named **ISE 802.1X and MAB with FTD Internet Egress**.
2. Add the nodes and images from the table below.
3. Connect the links exactly as listed. For the FTD, slot order matters: slot 0 =
   Management0/0, slot 2 = GigabitEthernet0/0 (outside), slot 3 = GigabitEthernet0/1 (inside).
4. On PC1's and LINUX1's interfaces, set the pinned MAC addresses from the table above
   (CML requires MACs inside its 52:54:00 OUI).
5. Set the INTERNET node's configuration to **NAT**.
6. Edit WEB1's `boot.sh` configuration file to:

   ```sh
   ip address add dev eth0 10.10.20.20/24
   ip link set dev eth0 up
   ip route add default via 10.10.20.1
   echo "READY" >/dev/console
   exit 0
   ```

| Node | Definition / image | Links |
|---|---|---|
| INTERNET | external_connector | port → FTD Gi0/0 |
| FTD | ftdv / ftdv-10-0-0 | Gi0/0 → INTERNET; Gi0/1 → CORE Gi0/0; Mgmt0/0 → CORE Gi0/3 |
| CORE-SW | iosvl2 / iosvl2-2020 | Gi0/0 → FTD; Gi0/1 → ACC Gi1/0/1; Gi0/2 → ISE; Gi0/3 → FTD Mgmt; Gi1/0 → WEB1; Gi1/1 → ADMIN-PC |
| ACC-SW | cat9000v-uadp / cat9000v-uadp-17-18-02 (12 vCPU / 32 GB — see the sizing note in Troubleshooting) | Gi1/0/1 → CORE; Gi1/0/2 → PC1; Gi1/0/3 → LINUX1; Gi1/0/4 → AD-DC1 |
| ISE | ise / ise-3-5-0-527 | eth0 → CORE Gi0/2 |
| WEB1 | nginx | eth0 → CORE Gi1/0 |
| ADMIN-PC | ubuntu2404-desktop | eth0 → CORE Gi1/1 |
| PC1 | ubuntu2404-desktop | eth0 → ACC Gi1/0/2 |
| LINUX1 | alpine | eth0 → ACC Gi1/0/3 |
| AD-DC1 | ubuntu2404-desktop | eth0 → ACC Gi1/0/4 |

Start order used in this guide (keeps host load sane): ISE first (longest boot), then the
switches, then FTD + ADMIN-PC, endpoints last.

## Part 2 — Switch base configuration (both switches)

Apply on CORE-SW (console). This creates the VLANs, the trunks to the FTD and ACC-SW, and the
VLAN 20 access ports for ISE, FTD management, WEB1 and ADMIN-PC.

```
enable
configure terminal
hostname CORE-SW
vlan 10
 name USERS
vlan 20
 name SERVICES
vlan 30
 name IOT-MAB
interface GigabitEthernet0/0
 description TRUNK-TO-FTD-INSIDE
 switchport trunk encapsulation dot1q
 switchport mode trunk
 switchport trunk allowed vlan 10,20,30
 no shutdown
interface GigabitEthernet0/1
 description TRUNK-TO-ACC-SW
 switchport trunk encapsulation dot1q
 switchport mode trunk
 switchport trunk allowed vlan 10,20,30
 no shutdown
interface GigabitEthernet0/2
 description ISE
 switchport mode access
 switchport access vlan 20
 spanning-tree portfast
 no shutdown
interface GigabitEthernet0/3
 description FTD-MANAGEMENT
 switchport mode access
 switchport access vlan 20
 spanning-tree portfast
 no shutdown
interface GigabitEthernet1/0
 description WEB1-SERVER
 switchport mode access
 switchport access vlan 20
 spanning-tree portfast
 no shutdown
interface GigabitEthernet1/1
 description ADMIN-PC
 switchport mode access
 switchport access vlan 20
 spanning-tree portfast
 no shutdown
interface Vlan20
 ip address 10.10.20.2 255.255.255.0
 no shutdown
ip default-gateway 10.10.20.1
end
write memory
```

Apply on ACC-SW (the Catalyst 9000v — IOS XE syntax, no `switchport trunk encapsulation`
command):

```
enable
configure terminal
hostname ACC-SW
vlan 10
 name USERS
vlan 20
 name SERVICES
vlan 30
 name IOT-MAB
interface GigabitEthernet1/0/1
 description TRUNK-TO-CORE-SW
 switchport mode trunk
 switchport trunk allowed vlan 10,20,30
 no shutdown
interface GigabitEthernet1/0/2
 description PC1-8021X
 switchport mode access
 switchport access vlan 10
 spanning-tree portfast
 no shutdown
interface GigabitEthernet1/0/3
 description LINUX1-MAB
 switchport mode access
 switchport access vlan 30
 spanning-tree portfast
 no shutdown
interface GigabitEthernet1/0/4
 description AD-DC1
 switchport mode access
 switchport access vlan 20
 spanning-tree portfast
 no shutdown
interface Vlan20
 ip address 10.10.20.3 255.255.255.0
 no shutdown
ip default-gateway 10.10.20.1
end
write memory
```

(The AAA/802.1X port configuration is added in Part 7, after ISE is ready.)

## Part 3 — FTD day-0 config, first boot, and FDM setup

The CML FTDv does **not** use the generic `admin / Admin123` first login. It takes its
initial setup from a JSON **day0-config** in the node's Config tab — fill it in *before*
starting the node. (As shipped, the day0-config has `AdminPassword: Cisc01@3`, a placeholder
hostname, and blank IP fields; started like that, the FTD boots unconfigured and those
defaults are what the console login expects.)

1. In CML, open the FTD node → **Config** and set the `day0-config` to:
   - `Hostname`: `ftd1`
   - `AdminPassword`: this guide uses `LabFTD-2026!`
   - `IPv4Mode`: `manual`, `IPv4Addr`: `10.10.20.5`, `IPv4Mask`: `255.255.255.0`,
     `IPv4Gw`: `10.10.20.1`
   - `DNS1`: `8.8.8.8`
   - `EULA`: `accept`, `FirewallMode`: `routed`, `ManageLocally`: `Yes` (FDM)
   - If the node was already started once, stop it and use **Wipe Disks** first — the
     config can only be edited while the node is in the DEFINED state, and day-0 applies
     on first boot.
2. Start the FTD and wait for the first boot to finish (tens of minutes on a busy host;
   the console sits at a login prompt while services come up). Log in on the console as
   `admin` with the day0 password.
3. On ADMIN-PC, set a static address (Settings → Network → Wired → IPv4 manual):
   `10.10.20.50/24`, gateway `10.10.20.1`, DNS `8.8.8.8`.
4. From ADMIN-PC's browser open `https://10.10.20.5` and sign in to FDM with the same
   admin credentials. Complete the initial setup wizard (smart licensing can stay in
   evaluation mode for the lab).

## Part 4 — FTD configuration in FDM

### Interfaces and routing
1. **Device → Interfaces**: enable **GigabitEthernet0/0**, name it `outside`, IPv4 = **DHCP**
   (it receives an address from the CML NAT connector — this is the lab's internet uplink).
   Make sure the CML **INTERNET connector node itself is started** — CML does not auto-start
   it, and without it the outside interface never gets a lease.
2. Enable **GigabitEthernet0/1** and leave the physical interface itself unnumbered and
   unnamed (a clean trunk parent). Add subinterfaces (FDM rejects dots in names — use
   hyphens):
   - `inside-trunk-10` → VLAN 10, static `10.10.10.1/24`
   - `inside-trunk-20` → VLAN 20, static `10.10.20.1/24`
   - `inside-trunk-30` → VLAN 30, static `10.10.30.1/24`
3. **Objects → Security Zones**: `inside_zone` = inside-trunk-10 + inside-trunk-20;
   `iot_zone` = inside-trunk-30; `outside_zone` = outside.
4. Confirm the default route learned via DHCP on outside (Routing page). Deploy this base
   configuration before continuing (the DHCP step below needs deployed interfaces).

### DHCP servers (so authenticated endpoints get addresses)
**Device Summary → System Settings → DHCP Server / Relay** (route
`#/system-settings/dhcp/servers`): add a server on each subinterface:
- inside-trunk-10: pool `10.10.10.100–10.10.10.200`
- inside-trunk-30: pool `10.10.30.100–10.10.30.200`

On the page's **Configuration** tab: turn **Enable Auto Configuration OFF** and set Primary
DNS = `8.8.8.8`. (There is deliberately no DHCP pool for VLAN 20 — its devices are static.)

> ⚠️ On FTD 10.0.0 the DHCP-server **Add** can hang indefinitely after the factory DHCP
> server has been removed (the dialog spins forever and nothing is staged). A device
> reboot clears the wedged management plane; the identical adds then complete immediately.

### NAT
**Device → NAT** (manual rules, *Before Auto NAT Rules*):
1. `PAT-VLAN10` — Dynamic: source interface inside-trunk-10 → destination interface
   outside, translated source = **Interface** (PAT to the outside address).
2. `PAT-VLAN20` — Dynamic: same pattern for inside-trunk-20.
3. `WEB1-8080` — **Static**: original destination = outside interface, TCP **8080** →
   translated destination **WEB1 10.10.20.20**, TCP **80**. This publishes the inside web
   server to the "internet" side.

There is no PAT rule for VLAN 30 — the IoT segment is blocked from egress by policy anyway.
(The factory manual rule `InsideOutsideNatRule` ends up re-pointed outside→outside during
the interface cleanup; it is inert for lab flows and can be left in place.)

Also create the network object **USERS-NET** = `10.10.10.0/24` (Objects → Networks) — the
access-control and identity rules use it.

### The domain controller (AD-DC1) — needed for the captive portal
⭐ **Design fact**: FDM captive-portal (active) authentication works **only against an
AD/LDAP realm** — the identity rule's source picker does not offer the FTD local user
database. This lab therefore includes a small Samba Active Directory DC:

1. AD-DC1 is an Ubuntu 24.04 desktop node on ACC-SW Gi1/0/4 (access VLAN 20). Give it a
   static address with NetworkManager: `10.10.20.60/24`, gateway `10.10.20.1`, DNS
   `8.8.8.8` (it will become its own resolver after provisioning).
2. Install the packages (the lab NAT gives it internet access):
   `sudo apt install -y samba krb5-config winbind`. If apt reports the dpkg lock is held
   by unattended-upgrades, stop and mask that service first.
3. Provision the domain:
   ```sh
   sudo systemctl stop smbd nmbd winbind
   sudo systemctl disable smbd nmbd winbind
   sudo mv /etc/samba/smb.conf /etc/samba/smb.conf.orig
   sudo samba-tool domain provision --domain=LAB --realm=LAB.LOCAL \
     --server-role=dc --dns-backend=SAMBA_INTERNAL --adminpass=LabAdmin-2026!
   sudo cp /var/lib/samba/private/krb5.conf /etc/krb5.conf
   ```
4. **DNS fix**: Samba's DNS will not answer on IPv4 while systemd-resolved's stub listener
   holds 127.0.0.53:53. Create `/etc/systemd/resolved.conf.d/no-stub.conf` with
   `DNSStubListener=no`, set `dns forwarder = 8.8.8.8` in `/etc/samba/smb.conf`, then
   restart systemd-resolved and enable/start `samba-ad-dc`, and point the DC's own
   resolver at 127.0.0.1. Verify with `kinit Administrator@LAB.LOCAL` and an SRV query
   for `_kerberos._udp.lab.local`.
5. **Relax LDAP strong authentication** (lab simplification): FDM binds with a cleartext
   simple bind, which Samba rejects by default (LDAP error 8, "stronger authentication
   required"). Add `ldap server require strong auth = no` under `[global]` in
   `/etc/samba/smb.conf` and restart `samba-ad-dc`.
6. Create the portal user and turn off password expiry for both accounts (in a guest
   terminal, run `set +H` first so the shell does not history-expand the `!`):
   ```sh
   sudo samba-tool user create webuser WebUser-2026!
   sudo samba-tool user setexpiry webuser --noexpiry
   sudo samba-tool user setexpiry Administrator --noexpiry
   ```

### AD realm in FDM
**Objects → Identity Sources → Add** (AD realm `LAB-AD`):
- Directory Username `Administrator@LAB.LOCAL`, Password `LabAdmin-2026!`
- Base DN `DC=lab,DC=local`, AD Primary Domain `LAB.LOCAL`
- Directory server `10.10.20.60`, port 389, encryption **None**, interface = management
- Press **Test** — expect "Connection to realm is successful." (If it fails with an LDAP
  strong-auth error, step 5 above was missed.)

(An FTD *local* user named `webuser` also exists under Device → Users, but local users are
only usable for RA VPN — the captive portal authenticates against the AD realm above.)

### Access control + identity (the egress login)
**Policies → Access Control** (default action: Block):
1. `EGRESS-AUTH` — Allow: source zone inside_zone + network USERS-NET → destination zone
   outside_zone, applications HTTP/HTTPS.
2. `Inside_Outside` — Trust (the factory rule, kept).
3. `IOT-BLOCK` — Block: source zone iot_zone → destination zone outside_zone (the MAB/IoT
   VLAN may not browse the internet; it can still reach WEB1 inside).
4. `INSIDE-WEB1` — Allow: source zone inside_zone → destination zone inside_zone,
   destination WEB1, HTTP.
5. `OUTSIDE-WEB1` — Allow: source zone outside_zone → destination zone inside_zone,
   destination WEB1, HTTP (the access rule that pairs with the static NAT forward).
6. `IOT-WEB1` — Allow: source zone iot_zone → destination zone inside_zone, destination
   WEB1, HTTP (its own rule, added after INSIDE-WEB1, so the IoT VLAN can reach the web
   server while IOT-BLOCK still denies it the internet).

**Policies → Identity** (direct route `#/policy/identity`): enable the identity policy,
default action = Passive Authentication, and add rule `CAPTIVE-PORTAL`:
- Action **Active Authentication**, identity source **LAB-AD**, type **HTTP Response Page**
- Fall back as guest: OFF; server certificate: DefaultWebserverCertificate
- Source: inside_zone + USERS-NET → Destination: outside_zone, any

Deploy the configuration (top-right **Deploy** button) and wait for the deploy to finish.
Users in VLAN 10 who have not authenticated are redirected to the FTD login page; after
signing in as `webuser` (the AD account), their HTTP/HTTPS egress is allowed.

Test from the "internet" side later (Part 9): browse to the FTD outside address on TCP/8080
and confirm WEB1's nginx page answers — that is the static NAT forward working. (On this
build that one data-plane check is blocked by the FTD's handling of its DHCP-assigned
outside address — see Part 9 item 6 and the last Troubleshooting entry before concluding
your NAT rule is wrong.)

## Part 5 — ISE initial setup (console wizard)

1. Open the ISE console and wait for the setup prompt (first boot is slow; the application
   services take several more minutes after the wizard finishes).
2. Answer the wizard:
   - Hostname: `ise1`
   - IP address: `10.10.20.10`, netmask `255.255.255.0`, default gateway `10.10.20.1`
   - DNS domain: `lab.local`, primary DNS: `8.8.8.8`
   - NTP server: `time.google.com` (or your preferred source)
   - Timezone: your local zone
   - Admin username: `admin`, password: `LabISE-2026!`
3. Wait until `show application status ise` (from the ISE CLI) reports the application server
   **running**, then browse to `https://10.10.20.10` from ADMIN-PC and sign in.

Notes from this build:
- The setup runs on the node's **VGA/VNC console**, not the serial console — a serial log
  that stops at "Press <Enter> to continue" does not mean setup is stuck.
- After "Application bundle (ISE) installed successfully", the database priming phase runs
  **silently for up to an hour** on nested storage. Judge progress by the node's CPU/disk
  activity in the CML workbench, not by console output.
- An interrupted install does **not** resume: if `show application status ise` says
  "% Application ise is not installed", wipe the node's disks and run setup fresh.
- A fresh install can fail at **NTP synchronization** if lab egress is not warm yet —
  verify NTP (UDP 123) egress through the FTD before starting a re-install.
- ⭐ **First GUI login forces a password reset**, and the reset **rejects the current
  password** while reporting the misleading error "Critical Error (1) — Incorrect username
  or password". Pick a *different* password: this build's GUI admin password became
  **`LabISE-2027!`**. The ISE **CLI** admin password is separate and stays `LabISE-2026!`.
- After the reset you land on the dashboard in 90-day Evaluation Mode — fine for the lab.
  (Administration → System → Deployment opens an "Information" dialog on a standalone
  node; that is expected and harmless.)

## Part 6 — ISE configuration (web GUI)

### Network devices (the two switches)
**Administration → Network Resources → Network Devices → Add** (repeat for both):
- Name `CORE-SW`, IP `10.10.20.2`, device type / location defaults
- RADIUS Authentication Settings: shared secret `LabRadius-2026`
- Name `ACC-SW`, IP `10.10.20.3`, same RADIUS secret

### 802.1X user
**Administration → Identity Management → Identities → Users → Add**:
`employee1 / Employee-2026!`, status Enabled. (This build left Password Lifetime at the
ISE default "With Expiration" (60 days) — if you re-run the lab after 60 days, reset or
recreate the user.)

### MAB endpoint
1. Create the group first: **Administration → Identity Management → Groups → Endpoint
   Identity Groups → Add**: `MAB-Devices` (description "MAB endpoints - LINUX1", parent
   group left blank).
2. **Context Visibility → Endpoints → Add**: MAC `52:54:00:10:30:01`, description "LINUX1
   MAB endpoint", check **Static Group Assignment** and set Identity Group Assignment =
   **MAB-Devices**. The endpoints list can show a stale "No data found" right after the
   add — reload the page and the row appears.

### Authorization profiles
**Policy → Policy Elements → Results → Authorization → Authorization Profiles → Add**:
- `VLAN10-USERS`: Access Type ACCESS_ACCEPT, Common Tasks → **VLAN** checked, ID = **10**
- `VLAN30-IOT`: Access Type ACCESS_ACCEPT, Common Tasks → **VLAN** checked, ID = **30**

The VLAN checkbox writes RADIUS Tunnel-Type = 13, Tunnel-Medium-Type = 6 and
Tunnel-Private-Group-ID = the VLAN ID. The profile's *Attributes Details* box shows them
as `1:10` / `1:30` — the `1:` prefix is the RFC 2868 tunnel tag byte, not part of the
VLAN ID (the editor's "Tag ID" field refers to that tag, not the VLAN).

### Policy set
**Policy → Policy Sets**, in the **Default** set:
- **Authentication policy — no changes needed.** The factory rules already do the right
  thing (verified in this build): MAB (Wired_MAB OR Wireless_MAB) → Internal Endpoints;
  Dot1X (Wired_802.1X OR Wireless_802.1X) → All_User_ID_Stores; Default →
  All_User_ID_Stores.
- **Authorization rules**: use the table's **⊕** (inserts a blank rule at the **top**;
  ISE auto-names it "Authorization Rule N" — the name is not editable) and build, in
  order:
  1. Condition **Wired_802.1X** → profile **VLAN10-USERS**
  2. Condition **Wired_MAB** → profile **VLAN30-IOT**
  3. (factory rules below — leave them) … Default: **DenyAccess**

  Order matters: the factory rule **Basic_Authenticated_Access** (any passed
  authentication → PermitAccess, *no* VLAN assignment) sits above the default rule, so
  your two rules must be placed **above** the factory rules or authenticated endpoints
  will land in the port's native VLAN with a plain PermitAccess. (In the Conditions
  Studio, library conditions are added by *dragging* the row into the Editor — clicking
  only selects it.)
  
  Optional hardening: also require the endpoint group on rule 2 (Wired_MAB **AND**
  endpoint in group MAB-Devices) so only pre-registered MACs get VLAN 30. This build's
  rule 2 is Wired_MAB only, which is sufficient for the lab as designed.

**Save** the policy set (bottom of the page) and confirm both rules show as saved. ISE is
ready to answer the switches.

## Part 7 — Switch AAA / 802.1X configuration (ACC-SW, Catalyst 9000v)

Only ACC-SW is an authenticator (CORE-SW just switches). IOS XE uses **IBNS 2.0**:
authentication is driven by `policy-map type control subscriber` policies attached to the
ports with a `service-policy`, not by the legacy `authentication order/priority` commands.
Apply on ACC-SW (the RADIUS source is the switch's VLAN 20 SVI, 10.10.20.3). Two
paste-time gotchas if you apply this as one file: run `enable` first (the console may sit
at the exec prompt), and the **first** `class-map type control subscriber` line triggers
IOS XE's one-time legacy-to-CPL conversion prompt — answer it, then re-apply the file
(the configuration is idempotent).

```
configure terminal
aaa new-model
radius server ISE1
 address ipv4 10.10.20.10 auth-port 1812 acct-port 1813
 key LabRadius-2026
aaa group server radius ISE-GROUP
 server name ISE1
aaa authentication dot1x default group ISE-GROUP
aaa authorization network default group ISE-GROUP
aaa accounting dot1x default start-stop group ISE-GROUP
aaa server radius dynamic-author
 client 10.10.20.10 server-key LabRadius-2026
ip radius source-interface Vlan20
dot1x system-auth-control
device-tracking policy IPDT_POLICY
 no protocol udp
 tracking enable
class-map type control subscriber match-all DOT1X_NO_RESP
 match method dot1x
 match result-type method-timeout
class-map type control subscriber match-all MAB_FAILED
 match method mab
 match result-type method-failure
policy-map type control subscriber DOT1X_MAB_POLICY
 event session-started match-all
  10 class always do-until-failure
   10 authenticate using dot1x priority 10
   20 authenticate using mab priority 20
 event authentication-failure match-first
  10 class DOT1X_NO_RESP do-until-failure
   10 terminate dot1x
   20 authenticate using mab priority 20
  20 class MAB_FAILED do-until-failure
   10 terminate mab
   20 authentication-restart 60
  30 class always do-until-failure
   10 terminate dot1x
   20 terminate mab
   30 authentication-restart 60
 event agent-found match-all
  10 class always do-until-failure
   10 terminate mab
   20 authenticate using dot1x priority 10
policy-map type control subscriber MAB_POLICY
 event session-started match-all
  10 class always do-until-failure
   10 authenticate using mab priority 10
 event authentication-failure match-first
  10 class always do-until-failure
   10 terminate mab
   20 authentication-restart 60
interface GigabitEthernet1/0/2
 description PC1-8021X
 device-tracking attach-policy IPDT_POLICY
 access-session control-direction in
 access-session host-mode single-host
 access-session port-control auto
 mab
 dot1x pae authenticator
 service-policy type control subscriber DOT1X_MAB_POLICY
interface GigabitEthernet1/0/3
 description LINUX1-MAB
 device-tracking attach-policy IPDT_POLICY
 access-session control-direction in
 access-session host-mode single-host
 access-session port-control auto
 mab
 service-policy type control subscriber MAB_POLICY
end
write memory
```

How to read it: on PC1's port the policy tries **dot1x first** (priority 10) and falls
back to **MAB** when the supplicant times out (`DOT1X_NO_RESP`); if a supplicant appears
later (`agent-found`), MAB is terminated and dot1x runs. LINUX1's port runs the MAB-only
policy, so it authenticates as soon as the device sends any frame. The
`aaa server radius dynamic-author` block lets ISE send Change-of-Authorization to the
switch (the matching CoA setting is on ISE's network device entry, port 1700).

## Part 8 — Endpoints

### PC1 — wired 802.1X supplicant (Ubuntu desktop)
1. Start PC1. It is plugged into the dot1x port, so it has no network until it authenticates.
2. Settings → Network → Wired → ⚙ → **Security** tab:
   - 802.1X security: **ON**
   - Authentication: **Protected EAP (PEAP)**
   - Inner authentication: **MSCHAPv2**
   - Username `employee1`, password `Employee-2026!`
   - CA certificate: none / "No CA certificate required" (lab only)
3. Apply and reconnect the wired connection. The switch asks ISE, ISE checks the internal
   user, and the port is authorized into **VLAN 10**; PC1 then gets a DHCP address from the FTD.

### LINUX1 — MAB device (Alpine Linux)
No configuration on the device: it has no supplicant. When it links up, ACC-SW falls back to
MAB, sends LINUX1's MAC (`52:54:00:10:30:01`) to ISE, ISE matches the endpoint group, and the
port is authorized into **VLAN 30**. LINUX1 then DHCPs an address in 10.10.30.0/24.

## Part 9 — Verification

1. **Switch**: on ACC-SW —
   `show access-session` → PC1's port (Gi1/0/2) shows method **dot1x**, status
   **Authorized**, LINUX1's port (Gi1/0/3) shows method **mab**, status **Authorized**;
   `show access-session interface GigabitEthernet1/0/2 details` shows VLAN 10 assigned by
   ISE, and Gi1/0/3 shows VLAN 30.
2. **ISE**: **Operations → RADIUS → Live Log** — a green authentication for `employee1`
   (802.1X, profile VLAN10-USERS) and one for the MAC `52:54:00:10:30:01` (MAB, profile
   VLAN30-IOT). (On this build the Live Log view itself returned "Server Error: undefined"
   while authentications were succeeding — the switch's `show access-session` and the ISE
   dashboard endpoint count are the reliable witnesses; see Troubleshooting.)
3. **Addresses**: PC1 holds a 10.10.10.x address; LINUX1 holds 10.10.30.x (`ip addr`).
4. **Captive portal**: on PC1, browse to an HTTP site. The first request is redirected to the
   FTD login page; sign in as `webuser` and the page loads. In FDM (**Monitoring → Users** /
   identity events) the authenticated user session is visible.
5. **IoT restriction**: from LINUX1, browsing out fails (rule IOT-BLOCK), while
   `http://10.10.20.20` (WEB1) still answers.
6. **Static NAT forward**: from a host on the outside (a second CML external connector set
   to NAT plus a throwaway Alpine node joins the same outside segment for this test), browse
   to `http://<FTD-outside-IP>:8080` → WEB1's nginx welcome page. **Known limitation on this
   FTD build**: the configuration verifies correctly (`show nat detail` shows the WEB1-8080
   rule; the OUTSIDE-WEB1 access rule is deployed), and a packet capture on the outside
   interface proves the SYNs arrive — but `packet-tracer` shows the FTD classifying traffic
   to its own **DHCP-assigned** outside address as *self-addressed* and diverting it away
   from the NAT rule, so the forward does not pass traffic in this environment. The
   workarounds (static outside address, or an explicit public-IP object in the NAT rule)
   are in Troubleshooting. Every other flow in this list passes as written.

## Troubleshooting notes

- **ISE ZTP aborts with "Gateway ping failed" / "Nameserver ping failed"**: the CML ISE image
  provisions itself from the node's `ise-ztp.conf` on first boot and *pings the default
  gateway and the nameserver* during that first boot. In this topology the gateway is the
  not-yet-configured FTD, and 8.8.8.8 is unreachable until the FTD provides NAT. Ways through:
  configure the FTD's VLAN 20 subinterface (10.10.20.1) *before* starting ISE; or temporarily
  add `ip address 10.10.20.1 255.255.255.0 secondary` to CORE-SW's `interface Vlan20` so the
  gateway answers (remove the secondary before the FTD interface is deployed, or you'll have
  a duplicate gateway); and/or add `SkipIcmpChecks=true` to `ise-ztp.conf`, which skips these
  setup-time ping checks entirely (runtime DNS is unaffected once the FTD path exists — this
  build used the secondary-IP trick for the gateway plus SkipIcmpChecks for the nameserver).
  If a boot already failed this way, fix the checks, **wipe the ISE node's disks** in CML
  (node → Wipe Disks), confirm the `ise-ztp.conf` values, and start it again; the config can
  only be edited while the node is in the DEFINED state, not while stopped after a boot.
- ISE first boot and application start are slow (tens of minutes on modest hosts) — check
  `show application status ise` before blaming the network.
- If the switch shows the port stuck unauthorized or the Live Log is empty, verify the
  RADIUS source interface (Vlan20) can ping 10.10.20.10 and that the shared secrets match
  exactly on the switch and in ISE's network device entry. `show aaa servers` on ACC-SW is
  the decisive check: if the Authen/MAC-auth transaction counters stay at **0** while the
  endpoint sends traffic, the switch never started a session at all — on a real Catalyst
  9000v that points at the control policy not being attached to the port; in CML it is
  also the signature of the IOSvL2 / IOL-L2 XE images, whose authenticator never fires
  (see the platform warning in Prerequisites — use the Catalyst 9000v for ACC-SW).
- MAB only triggers after dot1x times out on a dual-method port; a MAB-only port
  (Gi1/0/3 here) authenticates as soon as the device sends any frame (DHCP discover is
  enough).
- ISE 3.5 ships with the Blast RADIUS fix ("Message Authenticator Required On Response").
  If authentications fail with Message-Authenticator errors, check that posture on the
  switch/ISE pair — this build worked with ISE's defaults and the FDM ISE-RADIUS object's
  "Require Message-Authenticator" left checked.
- The captive portal only intercepts HTTP/HTTPS egress covered by the EGRESS-AUTH rule;
  deploy the FDM configuration after every policy change.
- **Catalyst 9000v sizing and variant**: give ACC-SW **12 vCPU / 32 GB**. At 16 GB the
  cat9000v-uadp image starves (low-memory warnings, OOM kills, chassis reload loops) even
  though the host has capacity to spare. Use the **UADP** variant: on the Q200 variant the
  session manager is not functional in CML (ports learn MACs and pass traffic, RADIUS
  `test aaa` succeeds, but `show access-session` reports "No sessions match supplied
  criteria" and no authentication session ever starts) — a limitation also reported by
  other CML users; UADP runs the session manager correctly.
- **CML links that report STARTED but pass nothing to a Catalyst 9000v**: if links were
  created after the Cat9000v node had already booted, that node's interfaces can be left
  in CML state STOPPED while the link shows STARTED and IOS shows up/up. Restarting the
  node does not fix it. Start the interface itself
  (`PUT /api/v0/labs/<lab>/interfaces/<interface-id>/state/start`, or stop/start the
  interface from the workbench) and traffic flows.
- **ISE ARP replies are 46-byte runt frames**: the Cat9000v drops them, so ACC-SW cannot
  resolve ISE's MAC even though ISE answers. Add a static ARP entry on ACC-SW —
  `arp 10.10.20.10 5254.0005.c326 arpa` (use ISE's actual MAC) — and save it; IOSvL2
  tolerates the runts, which is why CORE-SW never shows the symptom.
- **PC1 supplicant behaviour**: before the 802.1X supplicant is configured, PC1's port
  falls back to MAB and — because the as-built Wired_MAB rule has no endpoint-group
  condition — PC1 lands in VLAN 30 with a 10.10.30.x lease. After configuring the
  supplicant and authorizing into VLAN 10, run the connection up a second time
  (`nmcli con up "Wired connection 1"`) so it re-DHCPs into 10.10.10.x.
- **Captive portal redirects but the login page never loads**: the portal service
  (TCP 885 on the inside gateway) can wedge after unclean FTD shutdowns while the
  redirect keeps working. An FTD reboot restored it on this build; verify afterwards
  with `https://10.10.10.1:885/x.auth` answering (an HTTP 400 to a bare request is the
  healthy sign).
- **ISE Live Log shows "Server Error: undefined" / no data** while endpoints authenticate:
  on this build that view was broken independently of the authentication path — the
  dashboard's endpoint count and the switch's session table showed the real state.
  Treat it as a reporting quirk, not an auth failure.
- **FDM dead or 503 after unclean FTD shutdowns** (empty policy views, CLISH commands
  hanging, deploys stuck): the management plane loses its process enable-marker files.
  In expert mode, check `sudo pmtool status`; the recovery on this build was recreating
  the missing pure marker files (e.g. `/ngfw/etc/sf/offbox.run`, `rmq.enable`,
  `/etc/sf/sflogmon.run` — markers only, never the `.conf` files) and restoring
  `/ngfw/etc/sf/sftunnel.conf` from its `.in` render when it had been quarantined as
  `.CORRUPT` (pin it with `chattr +i` afterwards so the early-boot renderer cannot
  quarantine it again; remove the pin with `chattr -i` before any legitimate change).
  Two related FDM behaviours to expect afterwards: the web UI can take several minutes
  to answer TCP after the processes report Running, and the FDM session token lives
  about 30 minutes — a dialog left open past that fails silently, so reload the page
  (the refresh token restores the session; open dialogs are discarded). A deployment
  dialog stuck on "in progress" is not evidence either — reload and read the
  "Last successful deployment" banner.
- **Port-forward to the FTD's own outside address does not pass traffic when that address
  is DHCP-assigned** (Part 9 item 6): `packet-tracer input outside tcp <client> <port>
  <outside-IP> 8080` shows phase "NO-NAT / self-addressed — NAT divert to egress
  interface identity" and the NAT rule's hit counters stay at 0 even though a capture
  proves the SYNs arrive. Workarounds: assign the outside interface a **static** address
  in the same NAT segment, or build the forward's original destination as an explicit
  host object for the public address instead of the "interface" keyword.
