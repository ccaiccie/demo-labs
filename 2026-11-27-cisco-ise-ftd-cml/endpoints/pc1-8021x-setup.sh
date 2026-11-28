#!/usr/bin/env bash
# =============================================================================
# pc1-8021x-setup.sh — configure PC1 as a wired 802.1X supplicant
#
# Endpoint script for Part 8 of the lab guide. In the filmed build this
# connection was created in the Ubuntu desktop GUI; this script is the same
# configuration expressed with nmcli:
#   EAP = PEAP, phase 2 = MSCHAPv2, identity employee1 (an ISE internal user),
#   address by DHCP (the FTD's VLAN 10 pool, 10.10.10.100-200).
# Expected result: ISE authorizes the port with the VLAN10-USERS profile and
# PC1 lands on VLAN 10 (guide Part 9 verifies the session on ACC-SW and ISE).
#
# Run on PC1. Requires NetworkManager (stock Ubuntu desktop).
# =============================================================================
set -u
CONN="${1:-Wired connection 1}"   # check with: nmcli connection show

echo "Configuring 802.1X on connection: $CONN"
sudo nmcli connection modify "$CONN" \
  ipv4.method auto \
  802-1x.eap peap \
  802-1x.identity "employee1" \
  802-1x.password "Employee-2026!" \
  802-1x.phase2-auth mschapv2
# The lab ISE uses its self-signed certificate; the GUI build ticked
# "No CA certificate is required". nmcli has no single equivalent flag — if
# the supplicant refuses the ISE certificate, open the connection in the GUI
# editor once and tick that box, or set 802-1x.ca-cert to the ISE root CA.

sudo nmcli connection down "$CONN" >/dev/null 2>&1 || true
sudo nmcli connection up "$CONN"

echo "--- verify ---"
ip -brief address
echo "gateway (FTD VLAN 10 subinterface):"; ping -c2 10.10.10.1
echo "WEB1 inside server:";                ping -c2 10.10.20.20
cat <<'EOF'
Expected: a 10.10.10.x address (the pool starts at .100), both pings answer.
On the switch:  show authentication sessions interface Gi1/0/2 details
                -> Status: Authorized, Vlan: 10
Browsing the internet now triggers the FTD captive portal — log in with the
AD account webuser / WebUser-2026! (that is the portal working, not a fault).
EOF
