#!/usr/bin/env bash
# =============================================================================
# web1-setup.sh — WEB1: static address + the lab web server
#
# Endpoint script for the lab guide. WEB1 is the inside web server every
# verification flow points at: INSIDE-WEB1 and IOT-WEB1 allow HTTP to it from
# the user and IoT VLANs, and the FTD publishes it on the outside as
# <outside address>:8080 -> WEB1:80 (the WEB1-8080 static NAT rule).
#
# Run on WEB1 (Ubuntu). Requires NetworkManager + apt access for apache2.
# =============================================================================
set -u
CONN="${1:-Wired connection 1}"   # check with: nmcli connection show

echo "--- static address 10.10.20.20/24 ---"
sudo nmcli connection modify "$CONN" ipv4.method manual \
  ipv4.addresses 10.10.20.20/24 ipv4.gateway 10.10.20.1 ipv4.dns 8.8.8.8
sudo nmcli connection up "$CONN"

echo "--- web server ---"
sudo apt update && sudo apt install -y apache2
sudo tee /var/www/html/index.html >/dev/null <<'EOF'
<!DOCTYPE html>
<html><head><title>WEB1</title></head>
<body><h1>WEB1 &mdash; inside web server</h1>
<p>CML lab: Cisco ISE 802.1X &amp; MAB with FTD internet egress.
If you can read this page, the access rule for your VLAN allowed HTTP
to 10.10.20.20.</p></body></html>
EOF
sudo systemctl enable --now apache2

echo "--- verify ---"
ip -brief address
curl -s http://127.0.0.1 | head -3
cat <<'EOF'
From ADMIN-PC:  curl http://10.10.20.20        (inside path)
From the "internet" side: http://<FTD outside address>:8080
  — note the guide's troubleshooting finding: with a DHCP-assigned outside
    address the FTD treats that traffic as self-addressed and the static
    NAT does not engage; the inside paths above are the lab's verified ones.
EOF
