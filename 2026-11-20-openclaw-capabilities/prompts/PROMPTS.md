# Prompts Used in Order (`2026-11-20-openclaw-capabilities`)

All prompts below were executed against OpenClaw `2026.11.6` backed by local Ollama (`127.0.0.1:11434`) using RFC 5737 documentation prefixes (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`) and `lab.internal` device names.

---

## 1. Control UI Interactive Check
**Target:** OpenClaw Control UI (`http://127.0.0.1:18789/`, Main Session)
```text
In 3 concise bullet points, list the three RFC 5737 IPv4 documentation blocks and why NetOps labs use them.
```

---

## 2. Use Case 1 — Custom Workspace Skill (`netops-triage`)
**Model:** `ollama/qwen3:8b` (`--timeout 420`)
**Session Key:** `agent:main:explicit:demo-uc1-triage`
```text
Use the netops-triage skill to read /home/node/.openclaw/workspace/network_syslog.log and triage all critical routing/failover events and repeated SSH authentication failures into a Markdown table with columns Device, Event, Tier, and First Verification Command.
```

---

## 3. Use Case 2 — Autonomous Multi-Tool Python Syslog Auditor (`read` + `write` + `exec`)
**Model:** `ollama/qwen3:8b` (`--timeout 420`)
**Session Key:** `agent:main:explicit:demo-uc2-auditor`
*(Follow-up refinement from baseline testing: explicitly specifying `TIMESTAMP DEVICE SEVERITY EVENT DETAILS` ensures the generated script indexes token `1` for device hostnames rather than token `0`.)*
```text
Read /home/node/.openclaw/workspace/network_syslog.log (each line is space-separated: TIMESTAMP DEVICE SEVERITY EVENT DETAILS). Write a Python 3 script /home/node/.openclaw/workspace/audit_syslog.py that counts total_events, by_severity, by_device (using token index 1, the DEVICE hostname), and ssh_auth_fail_by_src, saves the JSON to /home/node/.openclaw/workspace/audit_report.json, runs the script with python3, and prints the JSON.
```

---

## 4. Use Case 3A — Persistent Workspace Memory Write (`MEMORY.md`)
**Model:** `ollama/qwen3:8b` (`--timeout 420`)
**Session Key:** `agent:main:explicit:demo-uc3-mem-write`
```text
Read /home/node/.openclaw/workspace/MEMORY.md and append a new section titled ### Lab Baseline: edge-fw-01.lab.internal with Management IP: 192.0.2.10/32, HA Peer: edge-fw-02.lab.internal, and Change Window: Tuesdays 03:00-05:00 UTC. Preserve all existing lines intact.
```

---

## 5. Use Case 3B — Cross-Session Memory Recall (Fresh Session)
**Model:** `ollama/qwen3:8b` (`--timeout 420`)
**Session Key:** `agent:main:explicit:demo-uc3-mem-recall`
```text
Read /home/node/.openclaw/workspace/MEMORY.md and report: (1) the BGP ASN and Loopback for core-rtr-01.lab.internal, and (2) the Management IP, HA Peer, and Change Window for edge-fw-01.lab.internal.
```

---

## 6. Use Case 4 — Native Gateway Cron Watchdog (CLI)
```bash
openclaw cron add --name "netops-crit-watchdog" --every 15m \
  --command "grep -c CRIT /home/node/.openclaw/workspace/network_syslog.log" \
  --no-deliver --json
```

---

## 7. Use Case 5 — Local Model Tool-Calling Comparison (`llama3.1-64k:latest`)
**Model:** `ollama/llama3.1-64k:latest` (`--timeout 180`)
**Session Key:** `agent:main:explicit:demo-uc5-llama`
```text
Use your read tool to read /home/node/.openclaw/workspace/MEMORY.md and tell me the exact Loopback IP and Weekly Maintenance Window for core-rtr-01.lab.internal.
```
