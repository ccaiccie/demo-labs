#!/usr/bin/env bash
set -euo pipefail

LAB_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${LAB_DIR}"
export ANSIBLE_CONFIG="${LAB_DIR}/ansible.cfg"
export COLUMNS=140

echo "=== [02-inspect-show] netlab version / tool versions ==="
netlab version | head -n 4
containerlab version | grep -E 'version:|commit:|date:'
ansible --version | head -n 2
dot -V 2>&1

echo "=== [02-inspect-show] netlab status ==="
netlab status

echo "=== [02-inspect-show] netlab report addressing ==="
netlab report addressing

echo "=== [02-inspect-show] netlab report bgp ==="
netlab report bgp

echo "=== [02-inspect-show] netlab inspect --node r1 (ospf & bgp) ==="
netlab inspect --node r1 ospf
netlab inspect --node r1 bgp

echo "=== [02-inspect-show] netlab inspect --node r4 (bgp) ==="
netlab inspect --node r4 bgp

echo "=== [02-inspect-show] Waiting for OSPF + BGP convergence before show commands ==="
netlab validate ospf_r1 ospf_core ibgp_as65001 ebgp_as65002 -q

echo "=== [02-inspect-show] FRR show ip ospf neighbor (r1, r2) ==="
echo "--- r1: show ip ospf neighbor ---"
netlab connect r1 --show ip ospf neighbor
echo "--- r2: show ip ospf neighbor ---"
netlab connect r2 --show ip ospf neighbor

echo "=== [02-inspect-show] FRR show ip bgp summary (r1, r2, r3, r4) ==="
for node in r1 r2 r3 r4; do
  echo "--- ${node}: show ip bgp summary ---"
  netlab connect "${node}" --show ip bgp summary
done

echo "=== [02-inspect-show] FRR show ip route (r1, r4) ==="
echo "--- r1: show ip route ---"
netlab connect r1 --show ip route
echo "--- r4: show ip route ---"
netlab connect r4 --show ip route

echo "=== [02-inspect-show] Linux hosts ip addr, ip route & end-to-end ping ==="
echo "--- h1: ip -o -f inet addr show ---"
netlab connect h1 -- ip -o -f inet addr show
echo "--- h1: ip route ---"
netlab connect h1 -- ip route
echo "--- h2: ip -o -f inet addr show ---"
netlab connect h2 -- ip -o -f inet addr show
echo "--- h2: ip route ---"
netlab connect h2 -- ip route
echo "--- h1 -> h2 ping (203.0.113.22) ---"
netlab connect h1 -- ping -c 4 203.0.113.22

echo "=== [02-inspect-show] PASS ==="
