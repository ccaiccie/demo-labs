# Configuring this lab with the REST APIs

The lab in the guide was configured in the FDM and ISE web GUIs, step by step.
These scripts are the same configuration expressed as REST API calls, so it
can be repeated, diffed and reviewed like code. They create the same object
names as the guide, check before creating (safe to re-run), and stop with a
clear error if a prerequisite is missing.

| Script | Configures | API used |
|---|---|---|
| `fdm-configure.sh` | FTD: network/port objects, `iot_zone`, AD realm `LAB-AD`, manual NAT (`PAT-VLAN10`, `PAT-VLAN20`, `WEB1-8080`), access rules (`EGRESS-AUTH`, `IOT-BLOCK`, `INSIDE-WEB1`, `OUTSIDE-WEB1`, `IOT-WEB1`), identity rule `CAPTIVE-PORTAL`, then deploys | FDM REST API, `https://10.10.20.5/api/fdm/latest` (token auth) |
| `ise-configure.sh` | ISE: network devices `CORE-SW` / `ACC-SW`, internal user `employee1`, endpoint group `MAB-Devices` + LINUX1's MAC, authorization profiles `VLAN10-USERS` / `VLAN30-IOT`, and the Default policy set's `Wired_802.1X` / `Wired_MAB` rules | ERS, `https://10.10.20.10:9060/ers/config` (devices, users, endpoints, profiles) + OpenAPI, `https://10.10.20.10/api/v1` (policy sets — ERS cannot manage those) |

Endpoint setup lives one level up, in `../endpoints/` (PC1's 802.1X
supplicant, LINUX1's MAB networking, WEB1's web server, ADMIN-PC's operator
setup).

## Before you run

- Run from ADMIN-PC (see `../endpoints/admin-pc-setup.sh`) — it can reach
  both management addresses. Needs `bash`, `curl`, `jq`.
- FTD interfaces, subinterfaces and zones from guide Parts 3–4 must exist;
  the FDM script looks them up by name. The two DHCP pools stay a GUI step —
  FDM's DHCP API surface is thin (see the note in the script header).
- On ISE, first enable the APIs once in the GUI:
  **Administration → System → Settings → API Settings** → *ERS (Read/Write)*
  and *Open API (Read/Write)*, and call with an admin account in the
  ERS Admin group.
- Credentials default to the lab values published in the guide; override
  with `FDM_USER`/`FDM_PASS` and `ISE_USER`/`ISE_PASS`. Note the ISE GUI
  password (`LabISE-2027!`, set at the forced first-login reset) is the one
  the APIs take — the ISE CLI password is different and unchanged.

## Honest limits

- Object field names follow the FTD 7.x FDM API (`latest`) and ISE 3.5.
  On another version, each box documents itself: FDM serves an API explorer
  on the device, and ISE serves the ERS SDK at `https://<ise>:9060/ers/sdk`.
- The scripts reproduce the lab's *policy layer*. Day-0 work (CML topology,
  switch configuration files, FTD first boot, ISE console wizard, the Samba
  AD DC) stays in the guide — the AD DC now has a complete step-by-step
  section of its own in Part 4.
