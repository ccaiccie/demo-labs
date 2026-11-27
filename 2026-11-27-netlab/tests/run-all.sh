#!/usr/bin/env bash
set -euo pipefail

LAB_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="${LAB_DIR}/tests/logs"
mkdir -p "${LOG_DIR}"

SCRIPTS=(
  "01-up.sh"
  "02-inspect-show.sh"
  "03-validate.sh"
  "04-failure-scenario.sh"
  "05-graph.sh"
  "06-down.sh"
)

echo "================================================================"
echo " netlab-demo end-to-end test suite"
echo " Lab dir: ${LAB_DIR}"
echo " Started: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "================================================================"

for s in "${SCRIPTS[@]}"; do
  LOG_FILE="${LOG_DIR}/${s%.sh}.log"
  echo ""
  echo ">>> Running tests/${s} (log: tests/logs/${s%.sh}.log)"
  bash "${LAB_DIR}/tests/${s}" 2>&1 | tee "${LOG_FILE}"
done

echo ""
echo "================================================================"
echo " ALL 6 STAGES PASSED"
echo " Finished: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo " Logs saved under: ${LOG_DIR}"
echo "================================================================"
