from __future__ import annotations

from datetime import datetime, timezone
from flask import Flask, jsonify, render_template_string

app = Flask(__name__)

DEVICES = [
    {
        "hostname": "core-rtr-01.iad",
        "ip": "10.10.0.1",
        "role": "Core Router",
        "status": "Healthy",
        "latency_ms": 1.2,
        "uptime": "48d 14h",
        "check_status": "pass",
        "packet_loss_pct": 0.0,
        "detail": "BGP peers established (4/4); CPU 18%; optics nominal.",
    },
    {
        "hostname": "dist-sw-01.iad",
        "ip": "10.10.1.10",
        "role": "Distribution Switch",
        "status": "Healthy",
        "latency_ms": 2.4,
        "uptime": "62d 07h",
        "check_status": "pass",
        "packet_loss_pct": 0.0,
        "detail": "MLAG active; all 10GbE uplinks error-free.",
    },
    {
        "hostname": "dist-sw-02.iad",
        "ip": "10.10.1.11",
        "role": "Distribution Switch",
        "status": "Healthy",
        "latency_ms": 2.7,
        "uptime": "62d 07h",
        "check_status": "pass",
        "packet_loss_pct": 0.0,
        "detail": "MLAG standby synced; spanning-tree root verified.",
    },
    {
        "hostname": "edge-fw-01.iad",
        "ip": "10.10.254.1",
        "role": "Edge Firewall",
        "status": "Degraded",
        "latency_ms": 18.6,
        "uptime": "19d 03h",
        "check_status": "warn",
        "packet_loss_pct": 0.4,
        "detail": "Elevated RTT (18.6 ms) on wan-0/1; HA failover peer ready.",
    },
    {
        "hostname": "wan-gw-01.iad",
        "ip": "198.51.100.2",
        "role": "WAN Gateway",
        "status": "Healthy",
        "latency_ms": 4.1,
        "uptime": "91d 22h",
        "check_status": "pass",
        "packet_loss_pct": 0.0,
        "detail": "IPsec tunnels up (6/6); transit link utilization 34%.",
    },
    {
        "hostname": "dns-auth-01.iad",
        "ip": "10.10.53.10",
        "role": "Authoritative DNS",
        "status": "Healthy",
        "latency_ms": 0.9,
        "uptime": "114d 05h",
        "check_status": "pass",
        "packet_loss_pct": 0.0,
        "detail": "Zone serials synchronized; query latency < 1 ms.",
    },
]

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>NetOps Status</title>
  <style>
    :root {
      --bg: #0b1120;
      --surface: #111827;
      --surface-alt: #162033;
      --border: #1f2937;
      --text: #f3f4f6;
      --muted: #9ca3af;
      --accent: #38bdf8;
      --accent-hover: #0ea5e9;
      --ok-bg: rgba(16, 185, 129, 0.14);
      --ok-text: #34d399;
      --warn-bg: rgba(245, 158, 11, 0.16);
      --warn-text: #fbbf24;
      --fail-bg: rgba(239, 68, 68, 0.16);
      --fail-text: #f87171;
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
      padding: 32px 48px 56px;
    }

    .container {
      max-width: 1400px;
      margin: 0 auto;
    }

    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 24px;
      padding-bottom: 24px;
      border-bottom: 1px solid var(--border);
      margin-bottom: 28px;
    }

    .title-group h1 {
      font-size: 2rem;
      font-weight: 700;
      letter-spacing: -0.02em;
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .status-dot {
      width: 12px;
      height: 12px;
      border-radius: 50%;
      background: var(--ok-text);
      box-shadow: 0 0 12px rgba(52, 211, 153, 0.7);
      display: inline-block;
    }

    .subtitle {
      color: var(--muted);
      font-size: 0.95rem;
      margin-top: 4px;
    }

    .actions {
      display: flex;
      align-items: center;
      gap: 16px;
    }

    #run-health-check {
      background: var(--accent);
      color: #082f49;
      border: none;
      border-radius: 8px;
      padding: 12px 22px;
      font-size: 0.98rem;
      font-weight: 700;
      cursor: pointer;
      transition: background 0.15s ease, transform 0.1s ease;
      box-shadow: 0 4px 14px rgba(56, 189, 248, 0.25);
    }

    #run-health-check:hover:not(:disabled) {
      background: var(--accent-hover);
      transform: translateY(-1px);
    }

    #run-health-check:disabled {
      opacity: 0.65;
      cursor: wait;
    }

    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 18px;
      margin-bottom: 28px;
    }

    .kpi-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 18px 22px;
    }

    .kpi-label {
      color: var(--muted);
      font-size: 0.85rem;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }

    .kpi-value {
      font-size: 1.85rem;
      font-weight: 700;
      margin-top: 6px;
    }

    .kpi-value.ok { color: var(--ok-text); }
    .kpi-value.warn { color: var(--warn-text); }

    .panel {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      overflow: hidden;
      margin-bottom: 28px;
    }

    .panel-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 18px 24px;
      border-bottom: 1px solid var(--border);
      background: var(--surface-alt);
    }

    .panel-header h2 {
      font-size: 1.1rem;
      font-weight: 600;
    }

    .panel-meta {
      color: var(--muted);
      font-size: 0.88rem;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      text-align: left;
    }

    th {
      padding: 14px 24px;
      font-size: 0.8rem;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--muted);
      border-bottom: 1px solid var(--border);
      background: rgba(15, 23, 42, 0.5);
    }

    td {
      padding: 16px 24px;
      border-bottom: 1px solid var(--border);
      font-size: 0.96rem;
    }

    tbody tr:last-child td {
      border-bottom: none;
    }

    tbody tr:hover {
      background: rgba(56, 189, 248, 0.06);
    }

    .mono {
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }

    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 12px;
      border-radius: 999px;
      font-size: 0.82rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }

    .badge-ok {
      background: var(--ok-bg);
      color: var(--ok-text);
    }

    .badge-warn {
      background: var(--warn-bg);
      color: var(--warn-text);
    }

    .badge-fail {
      background: var(--fail-bg);
      color: var(--fail-text);
    }

    #health-results {
      outline: none;
    }

    #health-results:focus {
      box-shadow: 0 0 0 2px var(--accent);
    }

    .results-summary {
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      padding: 18px 24px;
      border-bottom: 1px solid var(--border);
    }

    .summary-pills {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      align-items: center;
    }

    .timestamp {
      color: var(--muted);
      font-size: 0.9rem;
    }

    .check-list {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 14px;
      padding: 20px 24px 24px;
    }

    .check-item {
      background: var(--surface-alt);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 14px 18px;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .check-item-top {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
    }

    .check-host {
      font-weight: 600;
      font-size: 0.98rem;
    }

    .check-meta {
      color: var(--muted);
      font-size: 0.85rem;
    }

    .check-detail {
      color: #d1d5db;
      font-size: 0.9rem;
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="title-group">
        <h1><span class="status-dot" aria-hidden="true"></span>NetOps Status</h1>
        <p class="subtitle">US-East (IAD) Production Network Telemetry &amp; Active Diagnostics</p>
      </div>
      <div class="actions">
        <button id="run-health-check" type="button">Run health check</button>
      </div>
    </header>

    <section class="kpi-grid" aria-label="Network summary">
      <div class="kpi-card">
        <div class="kpi-label">Managed Devices</div>
        <div class="kpi-value">{{ summary.total }}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Healthy</div>
        <div class="kpi-value ok">{{ summary.healthy }}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Degraded</div>
        <div class="kpi-value warn">{{ summary.degraded }}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Avg Latency</div>
        <div class="kpi-value mono">{{ summary.avg_latency }} ms</div>
      </div>
    </section>

    <section class="panel" aria-labelledby="devices-heading">
      <div class="panel-header">
        <h2 id="devices-heading">Network Device Inventory</h2>
        <span class="panel-meta">Polling interval: 30s &bull; Region: iad-prod-1</span>
      </div>
      <table id="device-table">
        <thead>
          <tr>
            <th>Hostname</th>
            <th>IP Address</th>
            <th>Role</th>
            <th>Status</th>
            <th>Latency</th>
            <th>Uptime</th>
          </tr>
        </thead>
        <tbody>
          {% for d in devices %}
          <tr data-hostname="{{ d.hostname }}">
            <td class="mono">{{ d.hostname }}</td>
            <td class="mono">{{ d.ip }}</td>
            <td>{{ d.role }}</td>
            <td>
              {% if d.status == 'Healthy' %}
              <span class="badge badge-ok">{{ d.status }}</span>
              {% else %}
              <span class="badge badge-warn">{{ d.status }}</span>
              {% endif %}
            </td>
            <td class="mono">{{ "%.1f"|format(d.latency_ms) }} ms</td>
            <td class="mono">{{ d.uptime }}</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </section>

    <section id="health-results" class="panel" tabindex="-1" hidden aria-live="polite"></section>
  </div>

  <script>
    (function () {
      const btn = document.getElementById("run-health-check");
      const resultsEl = document.getElementById("health-results");

      function escapeHtml(value) {
        return String(value)
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;")
          .replace(/"/g, "&quot;")
          .replace(/'/g, "&#39;");
      }

      function badgeClass(status) {
        if (status === "pass") return "badge-ok";
        if (status === "warn") return "badge-warn";
        return "badge-fail";
      }

      btn.addEventListener("click", async function () {
        btn.disabled = true;
        btn.textContent = "Running health check...";

        try {
          const response = await fetch("/api/health-check", {
            method: "POST",
            headers: { "Accept": "application/json" }
          });
          if (!response.ok) {
            throw new Error("HTTP " + response.status);
          }
          const data = await response.json();

          const overallClass = data.status === "ok" ? "badge-ok" : "badge-warn";
          const overallLabel = data.status === "ok" ? "ALL CHECKS PASSED" : "WARNINGS DETECTED";

          const itemsHtml = data.checks.map(function (c) {
            return (
              '<div class="check-item" data-device="' + escapeHtml(c.hostname) + '">' +
                '<div class="check-item-top">' +
                  '<span class="check-host mono">' + escapeHtml(c.hostname) + '</span>' +
                  '<span class="badge ' + badgeClass(c.status) + '">' + escapeHtml(c.status) + '</span>' +
                '</div>' +
                '<div class="check-meta mono">' +
                  escapeHtml(c.ip) + ' &bull; ' + escapeHtml(c.role) +
                  ' &bull; RTT ' + escapeHtml(c.latency_ms.toFixed(1)) + ' ms' +
                  ' &bull; Loss ' + escapeHtml(c.packet_loss_pct.toFixed(1)) + '%' +
                '</div>' +
                '<div class="check-detail">' + escapeHtml(c.detail) + '</div>' +
              '</div>'
            );
          }).join("");

          resultsEl.innerHTML =
            '<div class="panel-header">' +
              '<h2>Health Check Results</h2>' +
              '<span class="badge ' + overallClass + '">' + overallLabel + '</span>' +
            '</div>' +
            '<div class="results-summary">' +
              '<div class="summary-pills">' +
                '<span class="badge badge-ok">Pass: ' + escapeHtml(data.summary.passed) + '</span>' +
                '<span class="badge badge-warn">Warn: ' + escapeHtml(data.summary.warn) + '</span>' +
                '<span class="panel-meta">Total checked: ' + escapeHtml(data.summary.total) + ' devices</span>' +
              '</div>' +
              '<div class="timestamp mono">Checked at: ' + escapeHtml(data.timestamp) + '</div>' +
            '</div>' +
            '<div class="check-list">' + itemsHtml + '</div>';

          resultsEl.hidden = false;
        } catch (err) {
          resultsEl.innerHTML =
            '<div class="panel-header">' +
              '<h2>Health Check Results</h2>' +
              '<span class="badge badge-fail">ERROR</span>' +
            '</div>' +
            '<div class="results-summary">' +
              '<span class="check-detail">Failed to execute health check: ' + escapeHtml(err.message) + '</span>' +
            '</div>';
          resultsEl.hidden = false;
        } finally {
          btn.disabled = false;
          btn.textContent = "Run health check";
        }
      });
    })();
  </script>
</body>
</html>
"""


@app.route("/")
def index():
    total = len(DEVICES)
    healthy = sum(1 for d in DEVICES if d["status"] == "Healthy")
    degraded = total - healthy
    avg_latency = round(sum(d["latency_ms"] for d in DEVICES) / total, 1) if total else 0.0
    summary = {
        "total": total,
        "healthy": healthy,
        "degraded": degraded,
        "avg_latency": f"{avg_latency:.1f}",
    }
    return render_template_string(HTML_TEMPLATE, devices=DEVICES, summary=summary)


@app.route("/api/health-check", methods=["GET", "POST"])
def api_health_check():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    checks = [
        {
            "hostname": d["hostname"],
            "ip": d["ip"],
            "role": d["role"],
            "status": d["check_status"],
            "latency_ms": d["latency_ms"],
            "packet_loss_pct": d["packet_loss_pct"],
            "detail": d["detail"],
        }
        for d in DEVICES
    ]
    passed = sum(1 for c in checks if c["status"] == "pass")
    warn = sum(1 for c in checks if c["status"] == "warn")
    failed = sum(1 for c in checks if c["status"] == "fail")
    overall_status = "fail" if failed else ("warn" if warn else "ok")

    return jsonify(
        {
            "status": overall_status,
            "timestamp": now,
            "summary": {
                "total": len(checks),
                "passed": passed,
                "warn": warn,
                "failed": failed,
            },
            "checks": checks,
        }
    )


@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8099, debug=False)
