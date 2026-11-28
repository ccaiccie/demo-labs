#!/bin/sh
# =============================================================================
# linux1-mab-setup.sh — LINUX1 network setup for MAB (Alpine Linux)
#
# Endpoint script for Part 8 of the lab guide. LINUX1 has no 802.1X
# supplicant — that is the point of the exercise. The switch falls back to
# MAB, ISE matches this node's MAC address against the statically assigned
# endpoint record in the MAB-Devices group, and authorizes VLAN 30.
#
# The MAC address (52:54:00:10:30:01) is a property of the CML node, set in
# the topology — NOT configured inside the guest. This script only makes
# sure the guest asks for an address by DHCP and then verifies the result.
#
# Run on LINUX1 as root (stock Alpine login: cisco / cisco, then su or sudo).
# =============================================================================
set -u

echo "--- interface configuration (DHCP on eth0) ---"
cat > /etc/network/interfaces <<'EOF'
auto lo
iface lo inet loopback

auto eth0
iface eth0 inet dhcp
EOF
rc-service networking restart

echo "--- verify ---"
echo "MAC address (must read 52:54:00:10:30:01 — if it does not, fix the"
echo "MAC on the CML node; ISE will not match any other address):"
ip link show eth0 | grep ether
echo "address (expect 10.10.30.100 — first lease in the FTD VLAN 30 pool):"
ip -brief address show eth0
echo "gateway (FTD VLAN 30 subinterface):"; ping -c2 10.10.30.1
echo "WEB1 (allowed by the IOT-WEB1 rule):"; ping -c2 10.10.20.20
echo "internet (expected to FAIL — the IOT-BLOCK rule denies the IoT VLAN"
echo "internet egress; the failure is the policy working, not a fault):"
ping -c2 -W2 8.8.8.8 || echo "  -> blocked, as designed"
cat <<'EOF'
On the switch:  show authentication sessions interface Gi1/0/3 details
                -> Method: mab, Status: Authorized, Vlan: 30
EOF
