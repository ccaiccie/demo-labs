"""Mock NetOps receiver: incident tickets, firewall blocklist, event log.
POST /incident, /block, /log with JSON. GET / shows a live page. GET /api/state returns JSON."""
import json, os, threading, html
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DATA = "/data/state.json"
LOCK = threading.Lock()

def load():
    try:
        with open(DATA) as f: return json.load(f)
    except Exception:
        return {"incidents": [], "blocklist": [], "events": [], "next": 1001}

def save(s):
    os.makedirs("/data", exist_ok=True)
    with open(DATA, "w") as f: json.dump(s, f, indent=2)

def now(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def as_obj(v):
    if isinstance(v, str):
        try: return json.loads(v)
        except Exception: return {"summary": v, "message": v}
    return v if isinstance(v, dict) else {}

class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        try: body = json.loads(self.rfile.read(n) or b"{}")
        except Exception: return self._send(400, '{"error":"bad json"}')
        log = as_obj(body.get("log")); v = as_obj(body.get("verdict"))
        rec = {"time": now(), "host": log.get("host", "?"), "message": log.get("message", ""), "verdict": v}
        with LOCK:
            s = load()
            if self.path == "/incident":
                rec["ticket"] = f"INC-{s['next']}"; s["next"] += 1; s["incidents"].insert(0, rec)
                out = {"result": "incident opened", "ticket": rec["ticket"]}
            elif self.path == "/block":
                ip = v.get("source_ip") or "unknown"; rec["ip"] = ip
                if ip not in [b["ip"] for b in s["blocklist"]]: s["blocklist"].insert(0, rec)
                out = {"result": "source IP blocked", "ip": ip}
            elif self.path == "/log":
                s["events"].insert(0, rec); out = {"result": "logged"}
            else:
                return self._send(404, '{"error":"unknown endpoint"}')
            save(s)
        print(now(), self.path, rec["host"], v.get("severity"), "|", rec["message"][:90], flush=True)
        out["verdict"] = v
        self._send(200, json.dumps(out))

    def do_GET(self):
        s = load()
        if self.path.startswith("/api/state"): return self._send(200, json.dumps(s, indent=2))
        e = html.escape
        def checks(v): return "<br>".join(e(c) for c in (v.get("suggested_checks") or []))
        inc = "".join(f"<tr><td><b>{e(r['ticket'])}</b><br>{e(r['time'])}</td><td>{e(r['host'])}</td><td class=sev-{e(str(r['verdict'].get('severity','')))}>{e(str(r['verdict'].get('severity','')))}</td><td>{e(str(r['verdict'].get('summary','')))}<br><i>{e(str(r['verdict'].get('likely_cause','')))}</i></td><td class=mono>{checks(r['verdict'])}</td></tr>" for r in s["incidents"])
        blk = "".join(f"<tr><td class=mono><b>{e(r['ip'])}</b></td><td>{e(r['time'])}</td><td>{e(r['host'])}</td><td>{e(str(r['verdict'].get('summary','')))}</td></tr>" for r in s["blocklist"])
        evs = "".join(f"<tr><td>{e(r['time'])}</td><td>{e(r['host'])}</td><td class=sev-{e(str(r['verdict'].get('severity','')))}>{e(str(r['verdict'].get('severity','')))}</td><td>{e(str(r['verdict'].get('summary','')))}</td></tr>" for r in s["events"])
        page = f"""<!doctype html><html><head><meta charset=utf-8><meta http-equiv=refresh content=3><title>NetOps Receiver</title>
<style>body{{font-family:Segoe UI,Arial,sans-serif;margin:18px;background:#f6f8fa;color:#1f2328}}h1{{margin:0 0 4px}}h2{{margin:18px 0 6px}}
table{{border-collapse:collapse;width:100%;background:#fff}}td,th{{border:1px solid #d0d7de;padding:6px 8px;vertical-align:top;font-size:14px;text-align:left}}
th{{background:#eaeef2}}.mono{{font-family:Consolas,monospace;font-size:13px}}.sev-critical{{color:#fff;background:#cf222e;font-weight:bold}}
.sev-warning{{background:#fff8c5;font-weight:bold}}.sev-info{{background:#ddf4ff}}.empty{{color:#777}}</style></head><body>
<h1>NetOps Receiver</h1><div>Mock ticketing, firewall blocklist and event log fed by n8n. Auto-refreshes every 3 seconds.</div>
<h2>Incident tickets ({len(s['incidents'])})</h2><table><tr><th>Ticket</th><th>Device</th><th>Severity</th><th>Summary / likely cause</th><th>Suggested checks</th></tr>{inc or '<tr><td colspan=5 class=empty>No incidents yet</td></tr>'}</table>
<h2>Firewall blocklist ({len(s['blocklist'])})</h2><table><tr><th>Blocked IP</th><th>Time</th><th>Reported by</th><th>Reason</th></tr>{blk or '<tr><td colspan=4 class=empty>Blocklist empty</td></tr>'}</table>
<h2>Event log ({len(s['events'])})</h2><table><tr><th>Time</th><th>Device</th><th>Severity</th><th>Summary</th></tr>{evs or '<tr><td colspan=4 class=empty>No events yet</td></tr>'}</table>
</body></html>"""
        self._send(200, page, "text/html; charset=utf-8")

    def log_message(self, *a): pass

if __name__ == "__main__":
    print("netops-receiver listening on :8090", flush=True)
    ThreadingHTTPServer(("0.0.0.0", 8090), H).serve_forever()
