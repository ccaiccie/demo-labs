"""Tiny lab webhook receiver: prints a short summary of every POST Uptime Kuma sends."""
import json
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

STATUS = {0: "DOWN", 1: "UP", 2: "PENDING", 3: "MAINTENANCE"}
KEEP = ("monitorID", "status", "msg", "important", "localDateTime", "timezone")


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0) or 0))
        stamp = datetime.now().strftime("%H:%M:%S")
        print(f"\n===== {stamp}  POST {self.path} =====", flush=True)
        try:
            body = json.loads(raw or b"{}")
            hb = body.get("heartbeat") or {}
            mon = body.get("monitor") or {}
            print(f"monitor : {mon.get('name')}", flush=True)
            print(f"status  : {STATUS.get(hb.get('status'), hb.get('status'))}", flush=True)
            print(f"msg     : {str(body.get('msg', '')).splitlines()[0][:110]}", flush=True)
            if hb:
                short = {k: hb.get(k) for k in KEEP if k in hb}
                if isinstance(short.get("msg"), str):
                    short["msg"] = short["msg"].strip().splitlines()[-1][:90] if short["msg"].strip() else ""
                print("heartbeat: " + json.dumps(short, indent=2, ensure_ascii=False), flush=True)
        except Exception:
            print(raw.decode("utf-8", "replace")[:1500], flush=True)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok": true}')

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    print("lab webhook receiver listening on :8080", flush=True)
    HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
