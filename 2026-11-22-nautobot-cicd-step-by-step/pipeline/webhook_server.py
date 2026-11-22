#!/usr/bin/env python3
"""
Lightweight HTTP webhook receiver for Nautobot -> CI/CD pipeline triggers.
Runs inside the `ci-runner` container on port 8086.

Endpoints:
  GET  /health           -> {"status": "ok"}
  GET  /runs             -> recent webhook events & pipeline run results
  POST /webhook/nautobot -> logs Nautobot SoT change event and triggers pipeline/run_cicd.py
"""

import json
import os
import subprocess
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List


PIPELINE_DIR = Path(__file__).resolve().parent
LOG_DIR = Path(os.environ.get("CICD_LOG_DIR", str(PIPELINE_DIR / "logs")))
LOG_DIR.mkdir(parents=True, exist_ok=True)
WEBHOOK_LOG = LOG_DIR / "webhooks.jsonl"

RUN_LOCK = threading.Lock()
STATE_LOCK = threading.Lock()
PENDING_EVENTS: List[str] = []
DEBOUNCE_TIMER: Any = None
RECENT_RUNS: List[Dict[str, Any]] = []
DEBOUNCE_SECONDS = float(os.environ.get("CICD_DEBOUNCE_SECONDS", "3.0"))


def _flush_and_run() -> None:
    global DEBOUNCE_TIMER
    with STATE_LOCK:
        events = list(PENDING_EVENTS)
        PENDING_EVENTS.clear()
        DEBOUNCE_TIMER = None
    if not events:
        return
    event_summary = events[-1] if len(events) == 1 else f"{events[-1]} (+{len(events) - 1} coalesced events)"
    execute_pipeline(event_summary, {"event": "coalesced", "model": "sot-change", "count": len(events)})


def schedule_pipeline(event_summary: str) -> None:
    global DEBOUNCE_TIMER
    with STATE_LOCK:
        PENDING_EVENTS.append(event_summary)
        if DEBOUNCE_TIMER is not None:
            DEBOUNCE_TIMER.cancel()
        DEBOUNCE_TIMER = threading.Timer(DEBOUNCE_SECONDS, _flush_and_run)
        DEBOUNCE_TIMER.daemon = True
        DEBOUNCE_TIMER.start()


def execute_pipeline(event_summary: str, payload: Dict[str, Any]) -> None:
    run_record: Dict[str, Any] = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "reason": event_summary,
        "model": payload.get("model"),
        "event": payload.get("event"),
        "status": "running",
    }
    RECENT_RUNS.append(run_record)
    if len(RECENT_RUNS) > 50:
        RECENT_RUNS.pop(0)

    cmd = [
        sys.executable,
        str(PIPELINE_DIR / "run_cicd.py"),
        "--reason",
        event_summary,
        "--auto-merge",
    ]
    if os.environ.get("CICD_AUTO_DEPLOY", "true").lower() == "true":
        cmd.append("--deploy")
    if os.environ.get("CICD_RUN_COMPLIANCE", "true").lower() == "true":
        cmd.append("--run-compliance")

    with RUN_LOCK:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        run_record["finished_at"] = datetime.now(timezone.utc).isoformat()
        run_record["returncode"] = proc.returncode
        run_record["status"] = "success" if proc.returncode == 0 else "failed"
        run_record["stdout_tail"] = "\n".join(proc.stdout.splitlines()[-25:])
        run_record["stderr_tail"] = "\n".join(proc.stderr.splitlines()[-15:])
        run_log = LOG_DIR / f"run-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.log"
        run_log.write_text(f"CMD: {' '.join(cmd)}\n\nSTDOUT:\n{proc.stdout}\n\nSTDERR:\n{proc.stderr}\n", encoding="utf-8")
        print(f"[webhook] Pipeline finished rc={proc.returncode} ({event_summary})", flush=True)


class WebhookHandler(BaseHTTPRequestHandler):
    def _send_json(self, code: int, obj: Any) -> None:
        body = json.dumps(obj, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json(200, {"status": "ok", "service": "nautobot-cicd-webhook"})
        elif self.path == "/runs":
            self._send_json(200, {"runs": RECENT_RUNS[-20:]})
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path != "/webhook/nautobot":
            self._send_json(404, {"error": "not found"})
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid JSON"})
            return

        event = payload.get("event", "updated")
        model = payload.get("model", "sot-object")
        data = payload.get("data") or {}
        obj_name = data.get("name") or data.get("display") or data.get("id") or "unknown"
        username = payload.get("username", "nautobot")
        event_summary = f"Nautobot {event} {model} '{obj_name}' by {username}"

        record = {
            "received_at": datetime.now(timezone.utc).isoformat(),
            "summary": event_summary,
            "payload": payload,
        }
        with WEBHOOK_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")

        print(f"[webhook] Received: {event_summary}", flush=True)

        schedule_pipeline(event_summary)

        self._send_json(202, {"accepted": True, "summary": event_summary})

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[http] {self.address_string()} - {fmt % args}", flush=True)


def main() -> int:
    host = os.environ.get("WEBHOOK_HOST", "0.0.0.0")
    port = int(os.environ.get("WEBHOOK_PORT", "8086"))
    server = ThreadingHTTPServer((host, port), WebhookHandler)
    print(f"[webhook] Listening on http://{host}:{port}/webhook/nautobot", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[webhook] Shutting down", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
