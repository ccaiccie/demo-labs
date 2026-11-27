#!/usr/bin/env bash
# Runs the connectivity tests from each spoke's test VM and shows the effective routes that decide the path.
# Needs: az (logged in), terraform, python3. Run from anywhere:  ./tests/run-tests.sh
set -euo pipefail
cd "$(dirname "$0")/.."

RG=$(terraform output -raw resource_group)
TARGETS=$(terraform output -json targets)
VMS=$(terraform output -json test_vms)
echo "steer_through_firewall=$(terraform output -raw steer_through_firewall)  snat_mode=$(terraform output -raw snat_mode)"
echo

# Script executed inside each VM. Any HTTP status code means TCP + TLS reached the private endpoint
# (400/403/404 are normal without credentials). 000 means the connection never completed.
CHECK=$(python3 - "$TARGETS" <<'EOF'
import json, sys
t = json.loads(sys.argv[1])
lines = []
for name, v in sorted(t.items()):
    f = v["fqdn"]
    lines.append(
        f'ip=$(getent ahostsv4 {f} | awk \'NR==1{{print $1}}\'); '
        f'code=$(curl -s -o /dev/null -w "%{{http_code}}" --connect-timeout 5 --max-time 10 https://{f}/ || true); '
        f'printf "%-14s %-46s resolves %-12s expect {v["ip"]:<12} http %s\\n" {name} {f} "$ip" "$code"')
print("\n".join(lines))
EOF
)

for vm in $(python3 -c 'import json,sys; print(" ".join(sorted(json.loads(sys.argv[1]))))' "$VMS"); do
  name=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])[sys.argv[2]]["name"])' "$VMS" "$vm")
  nic=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])[sys.argv[2]]["nic"])' "$VMS" "$vm")
  echo "=== $vm ($name) ==="
  az vm run-command invoke -g "$RG" -n "$name" --command-id RunShellScript --scripts "$CHECK" \
    --query 'value[0].message' -o tsv | sed -n '/\[stdout\]/,/\[stderr\]/p' | grep -v '^\[std'
  echo "--- effective routes on $nic (private endpoint and spoke prefixes)"
  az network nic show-effective-route-table -g "$RG" -n "$nic" \
    --query "value[?contains(join(',', addressPrefix), '10.')].{source:source, state:state, prefix:join(',', addressPrefix), nextHop:nextHopType, ip:join(',', nextHopIpAddress)}" -o table
  echo
done

cat <<'EOF'
How to read it
  http 4xx with steer_through_firewall=true  -> reached the endpoint; confirm on the firewall:
        show session all filter destination <endpoint ip>
        Monitor > Traffic, filter:  ( addr.dst in 10.1.2.0/24 ) or ( addr.dst in 10.2.2.0/24 )
  Effective routes: the endpoint's /32 InterfaceEndpoint route should show state Invalid, and the
        User route for the PE subnet (or the other spoke) should be Active with next hop 10.0.2.100.
  http 000 -> blocked: NSG on snet-pe (source was not the firewall), firewall policy, or a missing route.
EOF
