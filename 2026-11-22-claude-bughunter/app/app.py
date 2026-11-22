"""
Deliberately vulnerable local NetOps Inventory & Ticket Portal fixture
for authorized Claude-BugHunter skill & triage testing.

Bind strictly to 127.0.0.1:8765. Never deploy to a public network.

Patch toggles (environment variables):
  PATCH_SQLI=1 -> use parameterized SQLite query on /api/devices
  PATCH_XSS=1  -> HTML-escape query parameter `q` on /search
  PATCH_IDOR=1 -> enforce X-Lab-User ownership check on /api/tickets/<id>
"""

import html
import json
import os
import sqlite3
from pathlib import Path

from flask import Flask, jsonify, make_response, request

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
SEED_CANDIDATES = [
    Path(os.environ.get("SEED_PATH", "")) if os.environ.get("SEED_PATH") else None,
    BASE_DIR.parent / "testdata" / "seed.json",
    Path("/app/testdata/seed.json"),
]
DB_PATH = os.environ.get("LAB_DB_PATH", str(BASE_DIR / "netops_lab.db"))

FALLBACK_SEED = {
    "users": [
        {"id": 1, "username": "alice.netops", "display_name": "Alice Rivera", "email": "alice@lab.internal", "role": "netops-engineer"},
        {"id": 2, "username": "bob.secops", "display_name": "Bob Patel", "email": "bob@lab.internal", "role": "secops-analyst"},
        {"id": 3, "username": "carol.noc", "display_name": "Carol Chen", "email": "carol@lab.internal", "role": "noc-operator"},
    ],
    "devices": [
        {"id": 1, "hostname": "core-rtr-01.lab.internal", "ip_address": "192.0.2.10", "role": "core-router", "os_version": "LabIOS-XE 17.9", "site": "dc-west-lab", "status": "online", "owner": "alice.netops"},
        {"id": 2, "hostname": "dist-sw-02.lab.internal", "ip_address": "192.0.2.20", "role": "distribution-switch", "os_version": "LabNX-OS 10.3", "site": "dc-west-lab", "status": "online", "owner": "alice.netops"},
        {"id": 3, "hostname": "edge-fw-03.lab.internal", "ip_address": "198.51.100.1", "role": "edge-firewall", "os_version": "LabPAN-OS 11.1", "site": "dc-east-lab", "status": "online", "owner": "bob.secops"},
        {"id": 4, "hostname": "wan-gw-04.lab.internal", "ip_address": "203.0.113.1", "role": "wan-gateway", "os_version": "LabJunOS 23.4", "site": "dc-east-lab", "status": "maintenance", "owner": "alice.netops"},
    ],
    "tickets": [
        {"id": 101, "owner": "alice.netops", "device_hostname": "core-rtr-01.lab.internal", "title": "BGP graceful restart timer audit on core-rtr-01", "status": "open", "priority": "high", "summary": "Verify BGP hold and graceful restart timers ahead of weekend maintenance.", "internal_note": "LAB-TICKET-NOTE-ONLY-192-0-2-10: Peer AS 65001 test window approved."},
        {"id": 102, "owner": "bob.secops", "device_hostname": "edge-fw-03.lab.internal", "title": "Review egress ACL rules on edge-fw-03", "status": "in_progress", "priority": "high", "summary": "Audit lab egress policy and remove stale RFC 5737 test entries.", "internal_note": "LAB-TICKET-NOTE-ONLY-198-51-100-42: SecOps internal review marker."},
    ],
}


def patch_enabled(name: str) -> bool:
    return os.environ.get(name, "0").strip() == "1"


def current_mode() -> str:
    if patch_enabled("PATCH_SQLI") and patch_enabled("PATCH_XSS") and patch_enabled("PATCH_IDOR"):
        return "patched"
    return "vulnerable"


def load_seed_data() -> dict:
    for candidate in SEED_CANDIDATES:
        if candidate and candidate.is_file():
            with candidate.open("r", encoding="utf-8") as fh:
                return json.load(fh)
    return FALLBACK_SEED


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    seed = load_seed_data()
    conn = get_db()
    cur = conn.cursor()
    cur.executescript(
        """
        DROP TABLE IF EXISTS users;
        DROP TABLE IF EXISTS devices;
        DROP TABLE IF EXISTS tickets;

        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            email TEXT NOT NULL,
            role TEXT NOT NULL
        );

        CREATE TABLE devices (
            id INTEGER PRIMARY KEY,
            hostname TEXT NOT NULL,
            ip_address TEXT NOT NULL,
            role TEXT NOT NULL,
            os_version TEXT NOT NULL,
            site TEXT NOT NULL,
            status TEXT NOT NULL,
            owner TEXT NOT NULL
        );

        CREATE TABLE tickets (
            id INTEGER PRIMARY KEY,
            owner TEXT NOT NULL,
            device_hostname TEXT NOT NULL,
            title TEXT NOT NULL,
            status TEXT NOT NULL,
            priority TEXT NOT NULL,
            summary TEXT NOT NULL,
            internal_note TEXT NOT NULL
        );
        """
    )

    for u in seed.get("users", []):
        cur.execute(
            "INSERT INTO users (id, username, display_name, email, role) VALUES (?, ?, ?, ?, ?)",
            (u["id"], u["username"], u["display_name"], u["email"], u["role"]),
        )

    for d in seed.get("devices", []):
        cur.execute(
            "INSERT INTO devices (id, hostname, ip_address, role, os_version, site, status, owner) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (d["id"], d["hostname"], d["ip_address"], d["role"], d["os_version"], d["site"], d["status"], d["owner"]),
        )

    for t in seed.get("tickets", []):
        cur.execute(
            "INSERT INTO tickets (id, owner, device_hostname, title, status, priority, summary, internal_note) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (t["id"], t["owner"], t["device_hostname"], t["title"], t["status"], t["priority"], t["summary"], t["internal_note"]),
        )

    conn.commit()
    conn.close()


init_db()

PAGE_STYLE = """
<style>
  :root {
    --bg: #f8fafc;
    --card: #ffffff;
    --border: #cbd5e1;
    --text: #0f172a;
    --muted: #475569;
    --accent: #1d4ed8;
    --vuln-bg: #fee2e2;
    --vuln-fg: #991b1b;
    --patch-bg: #dcfce7;
    --patch-fg: #166534;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.5;
  }
  header {
    background: #ffffff;
    border-bottom: 1px solid var(--border);
    padding: 16px 28px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  header h1 { margin: 0; font-size: 20px; color: var(--text); }
  .badge {
    padding: 4px 12px;
    border-radius: 999px;
    font-size: 13px;
    font-weight: 600;
  }
  .badge-vuln { background: var(--vuln-bg); color: var(--vuln-fg); }
  .badge-patch { background: var(--patch-bg); color: var(--patch-fg); }
  main { max-width: 1080px; margin: 24px auto; padding: 0 20px 40px; }
  .card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 18px 20px;
    margin-bottom: 20px;
  }
  h2 { margin-top: 0; font-size: 17px; }
  .search-bar { display: flex; gap: 10px; }
  input[type="text"] {
    flex: 1;
    padding: 9px 12px;
    border: 1px solid var(--border);
    border-radius: 6px;
    font-size: 14px;
    background: #ffffff;
    color: var(--text);
  }
  button {
    padding: 9px 16px;
    background: var(--accent);
    color: #ffffff;
    border: none;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
  }
  table { width: 100%; border-collapse: collapse; font-size: 14px; }
  th, td {
    text-align: left;
    padding: 8px 10px;
    border-bottom: 1px solid #e2e8f0;
  }
  th { background: #f1f5f9; color: var(--muted); font-weight: 600; }
  code {
    background: #f1f5f9;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 13px;
  }
  a { color: var(--accent); text-decoration: none; }
  a:hover { text-decoration: underline; }
  .meta { color: var(--muted); font-size: 13px; }
</style>
"""


@app.route("/health", methods=["GET"])
def health():
    return jsonify(
        {
            "status": "ok",
            "mode": current_mode(),
            "patches": {
                "sqli": patch_enabled("PATCH_SQLI"),
                "xss": patch_enabled("PATCH_XSS"),
                "idor": patch_enabled("PATCH_IDOR"),
            },
        }
    )


@app.route("/", methods=["GET"])
def index():
    conn = get_db()
    devices = conn.execute(
        "SELECT id, hostname, ip_address, role, os_version, site, status, owner FROM devices ORDER BY id"
    ).fetchall()
    tickets = conn.execute(
        "SELECT id, owner, device_hostname, title, status, priority FROM tickets ORDER BY id"
    ).fetchall()
    conn.close()

    mode = current_mode()
    badge_cls = "badge-patch" if mode == "patched" else "badge-vuln"
    badge_txt = f"Mode: {mode.upper()} (SQLI={'PATCHED' if patch_enabled('PATCH_SQLI') else 'VULN'} | XSS={'PATCHED' if patch_enabled('PATCH_XSS') else 'VULN'} | IDOR={'PATCHED' if patch_enabled('PATCH_IDOR') else 'VULN'})"

    device_rows = "".join(
        f"<tr><td>{d['id']}</td><td><code>{html.escape(d['hostname'])}</code></td>"
        f"<td>{html.escape(d['ip_address'])}</td><td>{html.escape(d['role'])}</td>"
        f"<td>{html.escape(d['site'])}</td><td>{html.escape(d['status'])}</td>"
        f"<td>{html.escape(d['owner'])}</td></tr>"
        for d in devices
    )
    ticket_rows = "".join(
        f"<tr><td><a href='/api/tickets/{t['id']}'>#{t['id']}</a></td>"
        f"<td>{html.escape(t['owner'])}</td><td><code>{html.escape(t['device_hostname'])}</code></td>"
        f"<td>{html.escape(t['title'])}</td><td>{html.escape(t['status'])}</td>"
        f"<td>{html.escape(t['priority'])}</td></tr>"
        for t in tickets
    )

    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>NetOps Inventory &amp; Ticket Portal (Local Lab)</title>
  {PAGE_STYLE}
</head>
<body>
  <header>
    <div>
      <h1>NetOps Inventory &amp; Ticket Portal</h1>
      <div class="meta">Authorized Local Lab Fixture &middot; Bound to 127.0.0.1:8765 &middot; Synthetic RFC 5737 Data</div>
    </div>
    <span class="badge {badge_cls}">{html.escape(badge_txt)}</span>
  </header>
  <main>
    <div class="card">
      <h2>Device Search</h2>
      <form class="search-bar" action="/search" method="get">
        <input type="text" name="q" placeholder="Search hostname, site, or role (e.g. core-rtr-01)">
        <button type="submit">Search</button>
      </form>
      <p class="meta" style="margin-bottom:0;">
        Endpoints:
        <a href="/health">/health</a> &middot;
        <a href="/search?q=core-rtr-01">/search?q=core-rtr-01</a> &middot;
        <a href="/api/devices?hostname=core-rtr-01.lab.internal">/api/devices</a> &middot;
        <a href="/api/tickets/101">/api/tickets/101</a> &middot;
        <a href="/api/status?check=ping">/api/status</a>
      </p>
    </div>

    <div class="card">
      <h2>Network Device Inventory ({len(devices)})</h2>
      <table>
        <thead>
          <tr><th>ID</th><th>Hostname</th><th>IP Address</th><th>Role</th><th>Site</th><th>Status</th><th>Owner</th></tr>
        </thead>
        <tbody>{device_rows}</tbody>
      </table>
    </div>

    <div class="card">
      <h2>Maintenance Tickets ({len(tickets)})</h2>
      <table>
        <thead>
          <tr><th>Ticket</th><th>Owner</th><th>Device</th><th>Title</th><th>Status</th><th>Priority</th></tr>
        </thead>
        <tbody>{ticket_rows}</tbody>
      </table>
    </div>
  </main>
</body>
</html>"""
    return page, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/search", methods=["GET"])
def search():
    q = request.args.get("q", "")
    conn = get_db()
    like_term = f"%{q}%"
    rows = conn.execute(
        "SELECT id, hostname, ip_address, role, site, status FROM devices "
        "WHERE hostname LIKE ? OR role LIKE ? OR site LIKE ? ORDER BY id",
        (like_term, like_term, like_term),
    ).fetchall()
    conn.close()

    # INTENTIONAL Reflected XSS when PATCH_XSS != 1; HTML-escaped when PATCH_XSS=1.
    rendered_query = html.escape(q) if patch_enabled("PATCH_XSS") else q

    result_rows = "".join(
        f"<tr><td>{r['id']}</td><td><code>{html.escape(r['hostname'])}</code></td>"
        f"<td>{html.escape(r['ip_address'])}</td><td>{html.escape(r['role'])}</td>"
        f"<td>{html.escape(r['site'])}</td><td>{html.escape(r['status'])}</td></tr>"
        for r in rows
    )
    if not result_rows:
        result_rows = "<tr><td colspan='6' class='meta'>No matching devices found.</td></tr>"

    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Search Results - NetOps Portal</title>
  {PAGE_STYLE}
</head>
<body>
  <header>
    <div>
      <h1>NetOps Inventory Search</h1>
      <div class="meta"><a href="/">&larr; Back to Portal</a></div>
    </div>
    <span class="badge {'badge-patch' if patch_enabled('PATCH_XSS') else 'badge-vuln'}">
      XSS Protection: {'ENABLED' if patch_enabled('PATCH_XSS') else 'DISABLED (LAB)'}
    </span>
  </header>
  <main>
    <div class="card">
      <h2>Results for: {rendered_query}</h2>
      <table>
        <thead>
          <tr><th>ID</th><th>Hostname</th><th>IP Address</th><th>Role</th><th>Site</th><th>Status</th></tr>
        </thead>
        <tbody>{result_rows}</tbody>
      </table>
    </div>
  </main>
</body>
</html>"""
    return page, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/api/devices", methods=["GET"])
def api_devices():
    hostname = request.args.get("hostname", "")
    conn = get_db()
    try:
        if not hostname:
            rows = conn.execute(
                "SELECT id, hostname, ip_address, role, os_version, site, status, owner FROM devices ORDER BY id"
            ).fetchall()
        elif patch_enabled("PATCH_SQLI"):
            rows = conn.execute(
                "SELECT id, hostname, ip_address, role, os_version, site, status, owner FROM devices WHERE hostname = ?",
                (hostname,),
            ).fetchall()
        else:
            # INTENTIONAL SQL Injection when PATCH_SQLI != 1
            unsafe_sql = (
                "SELECT id, hostname, ip_address, role, os_version, site, status, owner "
                f"FROM devices WHERE hostname = '{hostname}'"
            )
            rows = conn.execute(unsafe_sql).fetchall()
    except sqlite3.Error as exc:
        conn.close()
        return jsonify({"error": "database_error", "detail": str(exc)}), 400
    conn.close()

    devices = [dict(r) for r in rows]
    return jsonify({"count": len(devices), "devices": devices})


@app.route("/api/tickets/<int:ticket_id>", methods=["GET"])
def api_ticket(ticket_id: int):
    conn = get_db()
    row = conn.execute(
        "SELECT id, owner, device_hostname, title, status, priority, summary, internal_note "
        "FROM tickets WHERE id = ?",
        (ticket_id,),
    ).fetchone()
    conn.close()

    if row is None:
        return jsonify({"error": "not_found", "ticket_id": ticket_id}), 404

    ticket = dict(row)

    if patch_enabled("PATCH_IDOR"):
        lab_user = request.headers.get("X-Lab-User", "").strip()
        if not lab_user or lab_user != ticket["owner"]:
            return (
                jsonify(
                    {
                        "error": "forbidden",
                        "message": "Access denied: X-Lab-User does not match ticket owner.",
                    }
                ),
                403,
            )

    return jsonify(ticket)


@app.route("/api/status", methods=["GET"])
def api_status():
    check_val = request.args.get("check", "ok")
    resp = make_response(
        jsonify(
            {
                "service": "netops-portal-lab",
                "status": "ok",
                "mode": current_mode(),
                "echo_check": check_val,
                "note": "Benign JSON diagnostic endpoint; served strictly as application/json.",
            }
        ),
        200,
    )
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Lab-Service"] = "netops-portal-lab"
    return resp


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8765, debug=False)
