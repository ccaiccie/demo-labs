#!/usr/bin/env bash
# Run the local CrewAI lab end to end against Ollama on this machine.
set -euo pipefail
LAB_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$LAB_ROOT"
export PATH="$HOME/.local/bin:$PATH"
export PYTHONPATH="$LAB_ROOT${PYTHONPATH:+:$PYTHONPATH}"

if ! curl -fsS http://127.0.0.1:11434/api/tags >/dev/null; then
  echo "Ollama is not reachable at http://127.0.0.1:11434" >&2
  exit 1
fi

uv run python scripts/smoke_tools.py
uv run python crews/research_writer.py
uv run python crews/log_triage.py
uv run python flows/severity_flow.py
uv run python flows/memory_followup.py

echo "Outputs:"
ls -l outputs/
