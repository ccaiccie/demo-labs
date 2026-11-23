#!/usr/bin/env bash
set -e
# Create baseline dummy interfaces representing WAN, LAN, DMZ, and MGMT zones
for iface in eth-wan eth-lan eth-dmz eth-mgmt; do
  ip link show "$iface" >/dev/null 2>&1 || ip link add "$iface" type dummy
  ip link set "$iface" up
done

# Initialize empty nftables table so nft list ruleset is always valid
if [ ! -f /etc/nftables.d/fw-edge-01.nft ]; then
  cat <<'EOF' > /etc/nftables.d/fw-edge-01.nft
table inet lab_fw {
  chain forward {
    type filter hook forward priority 0; policy drop;
  }
}
EOF
fi
nft -f /etc/nftables.d/fw-edge-01.nft || true

exec tail -f /dev/null
