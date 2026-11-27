#!/usr/bin/env bash
set -euo pipefail

LAB_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${LAB_DIR}"
export ANSIBLE_CONFIG="${LAB_DIR}/ansible.cfg"

# Ensure r2 eth3 is always restored even if the script aborts partway
cleanup() {
  netlab connect r2 -- vtysh -c "configure terminal" -c "interface eth3" -c "no shutdown" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "=== [04-failure-scenario] Step 1: Baseline BGP summary on r2 and r4 ==="
echo "--- r2 baseline ---"
netlab connect r2 --show ip bgp summary
echo "--- r4 baseline ---"
netlab connect r4 --show ip bgp summary
echo "--- r1 route to h2 subnet (203.0.113.16/28) before failure ---"
netlab connect r1 --show ip route 203.0.113.16/28

echo "=== [04-failure-scenario] Step 2: Shut down r2->r4 eBGP link (r2 eth3) ==="
netlab connect r2 -- vtysh -c "configure terminal" -c "interface eth3" -c "shutdown"
sleep 5

echo "--- r2 BGP summary during failure ---"
netlab connect r2 --show ip bgp summary
echo "--- r4 BGP summary during failure ---"
netlab connect r4 --show ip bgp summary
echo "--- r1 route to h2 subnet (203.0.113.16/28) during failure (failover via r3) ---"
netlab connect r1 --show ip route 203.0.113.16/28

echo "=== [04-failure-scenario] Step 3: Verify netlab validate detects eBGP failure ==="
set +e
VAL_OUT=$(netlab validate ebgp_as65002 --skip-wait 2>&1)
FAIL_RC=$?
set -e
echo "${VAL_OUT}"
echo "netlab validate ebgp_as65002 --skip-wait exit code: ${FAIL_RC}"
if [ "${FAIL_RC}" -eq 0 ]; then
  echo "FAIL: expected ebgp_as65002 validation to fail while r2 eth3 is shut down" >&2
  exit 1
fi
if ! printf '%s\n' "${VAL_OUT}" | grep -q '\[FAIL\]'; then
  echo "FAIL: expected [FAIL] in netlab validate output (not a CLI error)" >&2
  exit 1
fi
echo "Confirmed: netlab validate detected the r2-r4 eBGP link failure."

echo "=== [04-failure-scenario] Step 4: Verify traffic reroutes via r3-r4 (h1 -> h2 ping still succeeds) ==="
netlab connect h1 -- ping -c 4 203.0.113.22
netlab validate ping_h1_h2

echo "=== [04-failure-scenario] Step 5: Restore r2 eth3 and verify full recovery ==="
netlab connect r2 -- vtysh -c "configure terminal" -c "interface eth3" -c "no shutdown"
trap - EXIT

echo "Waiting for full netlab validate recovery..."
netlab validate

echo "--- r2 BGP summary after recovery ---"
netlab connect r2 --show ip bgp summary
echo "--- r4 BGP summary after recovery ---"
netlab connect r4 --show ip bgp summary

echo "=== [04-failure-scenario] PASS ==="
