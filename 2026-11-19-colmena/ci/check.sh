#!/usr/bin/env bash
# CI gate for a change branch: policy check, then evaluate and build the affected node.
set -euo pipefail
node="$1"
echo "== CI 1/2: policy check"
python3 ci/policy.py main
echo "== CI 2/2: colmena build --on $node"
colmena build --on "$node" 2>&1 | tail -n 5
echo "== CI PASSED"
