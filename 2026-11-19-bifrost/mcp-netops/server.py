#!/usr/bin/env python3
"""Local MCP server for the Bifrost lab.

Exposes three read-only tools over Streamable HTTP, limited to DEMO_DATA_DIR.
A plain /health endpoint is also served so Docker can probe the process.
"""

from __future__ import annotations

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse

DEMO_DIR = Path(os.environ.get("DEMO_DATA_DIR", "/demo-data")).resolve()

mcp = FastMCP(
    "netops",
    host="0.0.0.0",
    port=8765,
    stateless_http=True,
    json_response=True,
)


def _safe_path(name: str) -> Path:
    if not name or name.strip() != name:
        raise ValueError("file name required")
    candidate = (DEMO_DIR / name).resolve()
    if not str(candidate).startswith(str(DEMO_DIR) + os.sep) and candidate != DEMO_DIR:
        raise ValueError("path escapes the demo data directory")
    if not candidate.is_file():
        raise FileNotFoundError(f"not found: {name}")
    return candidate


@mcp.tool()
def list_demo_files() -> str:
    """List the sample network files in the read-only demo data folder."""
    names = sorted(p.name for p in DEMO_DIR.iterdir() if p.is_file())
    return "\n".join(names) if names else "(empty)"


@mcp.tool()
def read_demo_file(name: str) -> str:
    """Read one sample file from the demo data folder. Name only, no paths."""
    path = _safe_path(name)
    text = path.read_text(encoding="utf-8")
    if len(text) > 8000:
        return text[:8000] + "\n...[truncated]..."
    return text


@mcp.tool()
def get_interface_brief() -> str:
    """Return the sample 'show ip interface brief' output from the demo folder."""
    return _safe_path("interfaces.txt").read_text(encoding="utf-8")


@mcp.custom_route("/health", methods=["GET"])
async def health(_request: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


@mcp.custom_route("/", methods=["GET"])
async def root(_request: Request) -> JSONResponse:
    return JSONResponse({"service": "bifrost-demo-mcp-netops", "mcp": "/mcp"})


if __name__ == "__main__":
    if not DEMO_DIR.is_dir():
        raise SystemExit(f"DEMO_DATA_DIR does not exist: {DEMO_DIR}")
    mcp.run(transport="streamable-http")
