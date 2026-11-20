#!/usr/bin/env python3
"""Minimal local HTTP webhook receiver for LibreNMS alert testing.

Listens on 0.0.0.0:8080 inside the internal Docker network (lab_mgmt).
Logs every incoming alert POST payload to stdout and appends JSON lines to
/tmp/alerts.jsonl, returning HTTP 200.
"""

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import sys
import threading

LOG_PATH = os.environ.get("ALERT_LOG_PATH", "/tmp/alerts.jsonl")
PORT = int(os.environ.get("WEBHOOK_PORT", "8080"))
_LOCK = threading.Lock()
_COUNT = 0


def _append_record(record: dict) -> int:
    global _COUNT
    line = json.dumps(record, ensure_ascii=False)
    with _LOCK:
        _COUNT += 1
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
            fh.flush()
        print(f"[webhook-receiver] #{_COUNT} {line}", flush=True)
        return _COUNT


class WebhookHandler(BaseHTTPRequestHandler):
    def _send_json(self, code: int, body: dict) -> None:
        raw = json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        if self.path.rstrip("/") == "/health":
            self._send_json(200, {"status": "ok", "received": _COUNT})
            return

        if self.path.rstrip("/") == "/alerts":
            alerts = []
            if os.path.exists(LOG_PATH):
                with _LOCK:
                    with open(LOG_PATH, "r", encoding="utf-8") as fh:
                        for line in fh:
                            line = line.strip()
                            if line:
                                try:
                                    alerts.append(json.loads(line))
                                except json.JSONDecodeError:
                                    alerts.append({"raw": line})
            self._send_json(200, {"count": len(alerts), "alerts": alerts})
            return

        self._send_json(200, {"service": "webhook-receiver", "endpoints": ["/health", "/alert", "/alerts"]})

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length) if length > 0 else b""
        text_body = raw_body.decode("utf-8", errors="replace")
        try:
            parsed = json.loads(text_body) if text_body.strip() else {}
        except json.JSONDecodeError:
            parsed = {"raw_body": text_body}

        record = {
            "received_at": datetime.now(timezone.utc).isoformat(),
            "method": "POST",
            "path": self.path,
            "client_ip": self.client_address[0],
            "content_type": self.headers.get("Content-Type", ""),
            "payload": parsed,
        }
        count = _append_record(record)
        self._send_json(200, {"status": "received", "count": count})

    def log_message(self, fmt: str, *args) -> None:
        sys.stdout.write(f"[http] {self.client_address[0]} - {fmt % args}\n")
        sys.stdout.flush()


def main() -> None:
    os.makedirs(os.path.dirname(LOG_PATH) or "/tmp", exist_ok=True)
    server = HTTPServer(("0.0.0.0", PORT), WebhookHandler)
    print(f"[webhook-receiver] Listening on 0.0.0.0:{PORT}, logging to {LOG_PATH}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
