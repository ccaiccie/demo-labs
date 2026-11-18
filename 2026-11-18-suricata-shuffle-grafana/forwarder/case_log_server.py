#!/usr/bin/env python3
"""Tiny local case log: accepts POST /case JSON, appends to /data/cases.jsonl, GET /cases lists recent."""
import json, os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from datetime import datetime, timezone

DATA = Path(os.environ.get("CASE_LOG_PATH", "/data/cases.jsonl"))
DATA.parent.mkdir(parents=True, exist_ok=True)
PORT = int(os.environ.get("PORT", "8099"))

class H(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.log_date_time_string(), fmt % args), flush=True)

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/health"):
            return self._json(200, {"ok": True})
        if self.path.startswith("/cases"):
            rows = []
            if DATA.exists():
                for line in DATA.read_text(encoding="utf-8", errors="replace").splitlines()[-100:]:
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        pass
            return self._json(200, {"count": len(rows), "cases": rows})
        self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path.rstrip("/") != "/case":
            return self._json(404, {"error": "not found"})
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        try:
            obj = json.loads(raw.decode("utf-8", errors="replace") or "{}")
        except Exception:
            return self._json(400, {"error": "bad json"})
        obj["_received_at"] = datetime.now(timezone.utc).isoformat()
        with DATA.open("a", encoding="utf-8") as f:
            f.write(json.dumps(obj) + "\n")
        print(f"[case] {obj.get('signature')} from {obj.get('src_ip')}", flush=True)
        self._json(200, {"stored": True, "signature": obj.get("signature")})

if __name__ == "__main__":
    print(f"[caselog] listening on 0.0.0.0:{PORT} file={DATA}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
