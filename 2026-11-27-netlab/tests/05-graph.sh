#!/usr/bin/env bash
set -euo pipefail

LAB_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="${LAB_DIR}/tests/logs"
mkdir -p "${OUT_DIR}"

cd "${LAB_DIR}"

echo "=== [05-graph] Generating Graphviz DOT files with netlab graph ==="
netlab graph "${OUT_DIR}/topology.dot"
netlab graph -t bgp "${OUT_DIR}/bgp.dot"

echo "=== [05-graph] Rendering light-background SVG and PNG via dot ==="
dot -Gbgcolor=white -Tsvg "${OUT_DIR}/topology.dot" -o "${OUT_DIR}/topology.svg"
dot -Gbgcolor=white -Tpng "${OUT_DIR}/topology.dot" -o "${OUT_DIR}/topology.png"
dot -Gbgcolor=white -Tsvg "${OUT_DIR}/bgp.dot" -o "${OUT_DIR}/bgp.svg"
dot -Gbgcolor=white -Tpng "${OUT_DIR}/bgp.dot" -o "${OUT_DIR}/bgp.png"

ls -lh "${OUT_DIR}/topology.dot" "${OUT_DIR}/topology.svg" "${OUT_DIR}/topology.png" \
       "${OUT_DIR}/bgp.dot" "${OUT_DIR}/bgp.svg" "${OUT_DIR}/bgp.png"

for f in topology.dot topology.svg topology.png bgp.dot bgp.svg bgp.png; do
  if [ ! -s "${OUT_DIR}/${f}" ]; then
    echo "FAIL: ${OUT_DIR}/${f} is missing or empty" >&2
    exit 1
  fi
done

echo "=== [05-graph] PASS ==="
