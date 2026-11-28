#!/usr/bin/env bash
# =============================================================================
# admin-pc-setup.sh — ADMIN-PC: the operator workstation for the lab
#
# Endpoint script for the lab guide. ADMIN-PC is where the FDM and ISE web
# GUIs are driven from (and where the api/ scripts in this repo are run).
# Static address 10.10.20.50/24 on the services VLAN, plus /etc/hosts names
# for the lab systems so the GUIs and scripts can use names instead of IPs.
#
# Run on ADMIN-PC (Ubuntu desktop). Requires NetworkManager.
# =============================================================================
set -u
CONN="${1:-Wired connection 1}"   # check with: nmcli connection show

echo "--- static address 10.10.20.50/24 ---"
sudo nmcli connection modify "$CONN" ipv4.method manual \
  ipv4.addresses 10.10.20.50/24 ipv4.gateway 10.10.20.1 ipv4.dns 8.8.8.8
sudo nmcli connection up "$CONN"

echo "--- /etc/hosts lab names ---"
sudo tee -a /etc/hosts >/dev/null <<'EOF'
# CML ISE/FTD lab
10.10.20.10  ise
10.10.20.5   fdm
10.10.20.20  web1
10.10.20.60  addc1
10.10.20.2   core-sw
10.10.20.3   acc-sw
EOF

echo "--- verify ---"
ip -brief address
for h in 10.10.20.1 10.10.20.10 10.10.20.5 10.10.20.20 10.10.20.60; do
  ping -c1 -W2 "$h" >/dev/null && echo "  $h answers" || echo "  $h NO ANSWER"
done
cat <<'EOF'
Management stations:
  FDM  https://10.10.20.5     (admin / LabFTD-2026!)
  ISE  https://10.10.20.10    (admin / LabISE-2027! — GUI password, after the
                               forced first-login reset; the CLI password
                               stayed LabISE-2026!)
EOF
