"""Path-safe tools that list and read lab log and knowledge fixtures."""

from __future__ import annotations

from pathlib import Path

from crewai.tools import tool

LAB_ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = LAB_ROOT / "fixtures" / "logs"
KNOWLEDGE_DIR = LAB_ROOT / "fixtures" / "knowledge"


def _safe_file(base: Path, filename: str) -> Path:
    name = (filename or "").strip()
    if not name or name != Path(name).name or ".." in name:
        raise ValueError(f"invalid filename: {filename!r}")
    path = (base / name).resolve()
    if base.resolve() not in path.parents:
        raise ValueError(f"path escape: {filename!r}")
    if not path.is_file():
        raise FileNotFoundError(f"file not found: {name}")
    return path


@tool("list_log_files")
def list_log_files() -> str:
    """List available syslog files in the lab fixtures/logs directory. Returns basenames only."""
    files = sorted(p.name for p in LOG_DIR.glob("*.log") if p.is_file())
    return "\n".join(files) if files else "(none)"


@tool("read_log_file")
def read_log_file(filename: str) -> str:
    """Read one syslog file by basename only, for example edge-fw1.log, core-sw1.log, or access-sw2.log."""
    return _safe_file(LOG_DIR, filename).read_text(encoding="utf-8")


@tool("list_knowledge_files")
def list_knowledge_files() -> str:
    """List Markdown knowledge files in fixtures/knowledge. Returns basenames only."""
    files = sorted(p.name for p in KNOWLEDGE_DIR.glob("*.md") if p.is_file())
    return "\n".join(files) if files else "(none)"


@tool("read_knowledge_file")
def read_knowledge_file(filename: str) -> str:
    """Read one knowledge Markdown file by basename only, for example ospf-lab.md or syslog-triage.md."""
    return _safe_file(KNOWLEDGE_DIR, filename).read_text(encoding="utf-8")
