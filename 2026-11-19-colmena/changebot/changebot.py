#!/usr/bin/env python3
"""change-bot: turns an AI-produced intent into a git branch, runs CI, and deploys with Colmena only if CI passes.
n8n calls POST /change with {"request": "...", "intent": {...}}. The AI never touches the nodes."""
import json, re, subprocess, sys, time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

REPO = Path.home() / "colmena-demo"
NODES = {"router1", "dns1", "monitor1"}

def say(msg):
    print(f"[change-bot {time.strftime('%H:%M:%S')}] {msg}", flush=True)

def sh(*cmd, check=True):
    p = subprocess.Popen(cmd, cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    out = []
    for line in p.stdout:
        print("    " + line.rstrip(), flush=True); out.append(line)
    p.wait()
    if check and p.returncode:
        raise RuntimeError(f"{cmd[0]} failed")
    return p.returncode, "".join(out)

def edit(path, fn):
    """Load a data file, change it, and write it back in the same one-entry-per-line style."""
    f = REPO / path
    data = json.loads(f.read_text()); fn(data)
    lines = [f"  {json.dumps(k)}: {json.dumps(v, separators=(', ', ': ')).replace('{', '{ ').replace('}', ' }')}" for k, v in data.items()]
    f.write_text("{\n" + ",\n".join(lines) + "\n}\n")

def handle(req, intent):
    action = intent.get("action")
    say(f"request: {req}")
    say(f"AI intent: {json.dumps(intent)}")
    if action == "add_dns_record":
        name, ip, node = str(intent.get("name", "")).lower(), str(intent.get("ip", "")), "dns1"
        slug = f"dns-{name}"
        change = lambda: edit("data/dns-records.json", lambda d: d.__setitem__(name, ip))
    elif action == "open_port":
        node, port, proto = intent.get("node"), int(intent.get("port", 0)), intent.get("protocol", "tcp")
        if node not in NODES:
            return f"Rejected: unknown node {node!r}. Nothing was changed."
        slug = f"port-{node}-{proto}{port}"
        def change():
            edit("data/firewall.json", lambda d: d[node][proto].append(port))
    else:
        return f"I can only add DNS records or open firewall ports. Nothing was changed. ({intent.get('summary', '')})"
    branch = f"change/{re.sub(r'[^a-z0-9-]', '-', slug)}-{time.strftime('%H%M%S')}"
    sh("git", "switch", "-q", "main")
    sh("git", "switch", "-q", "-c", branch)
    change()
    sh("git", "diff", "--stat")
    sh("git", "-c", "user.name=change-bot", "-c", "user.email=change-bot@lab.local",
       "commit", "-qam", f"AI change request: {req}")
    rev = sh("git", "rev-parse", "--short", "HEAD")[1].strip()
    say(f"committed {rev} on {branch}; running CI")
    rc, ci_out = sh("ci/check.sh", node, check=False)
    sh("git", "switch", "-q", "main")
    if rc:
        reasons = "; ".join(l.split("POLICY FAIL:", 1)[1].strip() for l in ci_out.splitlines() if "POLICY FAIL:" in l) or "the build failed"
        say("CI failed: branch kept for review, nothing deployed")
        return f"Rejected by CI: {reasons}. Branch {branch} (commit {rev}) was not merged and nothing was deployed."
    sh("git", "merge", "-q", "--ff-only", branch)
    say(f"CI passed: merged {branch} into main; deploying to {node}")
    rc, out = sh("colmena", "apply", "--on", node, check=False)
    if rc:
        return f"CI passed and {branch} was merged, but colmena apply on {node} failed. Check the change-bot log."
    say("deploy finished")
    return f"Done. Branch {branch} (commit {rev}) passed CI, was merged to main and deployed to {node} with colmena apply."

class H(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        intent = body.get("intent") or {}
        if isinstance(intent, str):
            intent = json.loads(intent)
        try:
            reply = handle(body.get("request", ""), intent)
        except Exception as e:
            subprocess.run(["git", "switch", "-q", "main"], cwd=REPO)
            reply = f"Error: {e}. Nothing was deployed."
        say("reply: " + reply)
        data = json.dumps({"reply": reply}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
    def log_message(self, *a): pass

if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    say(f"listening on {host}:8091, repo {REPO}")
    HTTPServer((host, 8091), H).serve_forever()
