#!/usr/bin/env python3
"""Offline smoke test for path-safe log and knowledge tools (no LLM)."""

from __future__ import annotations

import sys
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB_ROOT))

from tools.log_tools import (
    list_knowledge_files,
    list_log_files,
    read_knowledge_file,
    read_log_file,
)


def _run(fn, *args):
    # CrewAI tool objects expose .func or are callable depending on version.
    target = getattr(fn, "func", None) or getattr(fn, "_run", None) or fn
    return target(*args) if args else target()


def main() -> None:
    logs = _run(list_log_files)
    knowledge = _run(list_knowledge_files)
    print("LOGS:\n" + logs)
    print("KNOWLEDGE:\n" + knowledge)
    assert "core-sw1.log" in logs and "edge-fw1.log" in logs and "access-sw2.log" in logs
    assert "ospf-lab.md" in knowledge and "syslog-triage.md" in knowledge
    core = _run(read_log_file, "core-sw1.log")
    edge = _run(read_log_file, "edge-fw1.log")
    access = _run(read_log_file, "access-sw2.log")
    assert "192.0.2.19" in core and "FULL" in core
    assert "198.51.100.66" in edge and "Login denied" in edge
    assert "00:11:22:33:44:61" in access and "MACFLAP" in access
    ospf = _run(read_knowledge_file, "ospf-lab.md")
    assert "192.0.2.19" in ospf
    try:
        _run(read_log_file, "../.env")
    except (ValueError, FileNotFoundError):
        pass
    else:
        raise SystemExit("path escape was not blocked")
    print("SMOKE_OK")


if __name__ == "__main__":
    main()
