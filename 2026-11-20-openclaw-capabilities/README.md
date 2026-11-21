# OpenClaw 2026.11 Capabilities Lab — Local Ollama NetOps Workflows (`2026-11-20-openclaw-capabilities`)

Hands-on lab exploring the core capabilities of **OpenClaw `2026.11.6`** running locally in WSL2 Docker against local **Ollama** models (`qwen3:8b` and `llama3.1-64k:latest`) with zero cloud API keys or external messaging dependencies.

All network fixtures use RFC 5737 documentation IPv4 blocks (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`) and `.lab.internal` hostnames.

---

## 1. What This Lab Covers

1. **Gateway & Workspace-as-Brain Architecture:** Loopback WebSocket/HTTP control plane (`127.0.0.1:18789`), multi-engine SQLite state (`state` schema 36, `agent` schema 38), and plain Markdown continuity files (`SOUL.md`, `AGENTS.md`, `USER.md`, `MEMORY.md`).
2. **Control UI & Admin Surfaces:** Sessions, navigation command palette (`Meetings`, `Automations`, `Skills`, `Plugins`, `Settings`, `Agents`), inline `/` session commands, per-session local model selector, and docked `Ask OpenClaw` assistant.
3. **Use Case 1 — Custom Workspace Skill (`netops-triage`):** Precedence-loaded `workspace/skills/netops-triage/SKILL.md` classifying a 24-line multi-device syslog capture into `P1`/`P2`/`P3` severity tiers with read-only CLI checks.
4. **Use Case 2 — Autonomous Multi-Tool Execution (`read` -> `write` -> `exec`):** Agent-generated Python 3 syslog auditor (`audit_syslog.py` -> `audit_report.json`) verified side-by-side against an independent ground-truth script (`scripts/ground_truth_verify.py`).
5. **Use Case 3 — Persistent Cross-Session Memory, Hybrid Search & Memory Dreaming:** Appending `edge-fw-01.lab.internal` baseline facts in Session A, recalling both `core-rtr-01` and `edge-fw-01` baselines in a fresh Session B, running `openclaw memory search`, and inspecting `Light Sleep` staged memory candidates.
6. **Use Case 4 — Native Gateway Cron Watchdog:** Scheduling and running a 15-minute `netops-crit-watchdog` job (`--no-deliver`) inside the Gateway and inspecting structured run diagnostics.
7. **Use Case 5 — Security Audit, Activity Ledger & Local Model Comparison:** Running `openclaw security audit`, `openclaw approvals get`, and `openclaw audit`, profiling `ollama ps` VRAM/CPU split, and comparing `qwen3:8b` real tool invocation against `llama3.1-64k:latest` raw JSON output.

---

## 2. Requirements & Ports

- **Host OS:** Windows 11 with WSL2 (`Ubuntu-24.04`, mirrored networking enabled) + Docker Engine in WSL2, or native Linux with Docker Compose v2
- **Local LLM Runtime:** Ollama listening on `127.0.0.1:11434`
  - `ollama pull qwen3:8b` (5.2 GB — required for real tool execution)
  - `ollama pull llama3.1:8b` / `llama3.1-64k:latest` (4.9 GB — optional comparison model)
- **GPU / RAM:** Tested on an 8 GB VRAM GPU (`qwen3:8b` at `32768` context uses ~10 GB split `39% CPU / 61% GPU`)

| Service | Bind Address & Port | Purpose |
| :--- | :--- | :--- |
| OpenClaw Gateway & Control UI | `127.0.0.1:18789` | Web Control UI, `/health`, and typed WebSocket RPC (`ws://127.0.0.1:18789`) |
| Ollama Local API | `127.0.0.1:11434` | Local LLM inference (`qwen3:8b`, `llama3.1-64k:latest`) |

---

## 3. Quick Start & Reproduction Steps

```bash
# 1. Create a local .env with a random Gateway token (never commit .env)
cp .env.example .env
sed -i "s/replace-with-random-local-lab-token/$(openssl rand -hex 24)/" .env

# 2. Start the OpenClaw Gateway container
docker compose up -d

# 3. Verify Gateway health and version
curl -s http://127.0.0.1:18789/health
docker exec openclaw-ollama-lab openclaw --version
docker exec openclaw-ollama-lab openclaw status
```

Open `http://127.0.0.1:18789/` in your browser and paste the `OPENCLAW_GATEWAY_TOKEN` from `.env` when prompted by the Control UI.

Run each capability test in order from [prompts/PROMPTS.md](prompts/PROMPTS.md), and compare syslog counts with:

```bash
python3 scripts/ground_truth_verify.py workspace/network_syslog.log
```

---

## 4. Observed Results (From `evidence/`)

- **Health & Build:** `{"ok":true,"status":"live"}` on `OpenClaw 2026.11.6 (06afb10)`, `17/53` skills ready offline including `openclaw-workspace` skill `netops-triage`.
- **Use Case 1 (`07c-uc1-triage-output.txt`):** Completed in `371.1s` (`5m 53s` cold 13K-token prompt prefill + `read` calls on `SKILL.md` and `network_syslog.log`), producing a 16-row Markdown triage table with read-only `show` commands (`show bgp summary`, `show ip ospf neighbor`, `show interfaces`, `show logging`). Note: at 8B scale, `qwen3:8b` placed `HA_FAILOVER` and `OSPF_NBR_DOWN` in `P2` rather than `P1` and paired one `LINK_DOWN` row with `show environment fan` — always review 8B classifications.
- **Use Case 2 (`08a`–`08e`):** First pass (`214.4s`) wrote `audit_syslog.py`, caught its own Python `dict(...)` syntax error via `exec`, and printed the fix. Follow-up turn saved and ran the corrected script, matching ground truth (`24` total events; `CRIT: 4, ERR: 8, WARN: 8, INFO: 4`; `core-rtr-01: 7`, `edge-fw-01: 6`, `dist-sw-01: 5`, `dist-sw-02: 3`, `wan-rtr-02: 3`), while `scripts/ground_truth_verify.py` caught a subtle string-matching bug (`'ssh auth fail'` with spaces vs `'SSH_AUTH_FAIL'`, missing `203.0.113.44: 3`).
- **Use Case 3 (`09a`–`09d`):** Warm `MEMORY.md` edit completed in `76.5s`; fresh-session recall (`demo-uc3-mem-recall`) returned both `core-rtr-01.lab.internal` (`ASN 65001`, `192.0.2.1/32`) and `edge-fw-01.lab.internal` (`192.0.2.10/32`, `edge-fw-02.lab.internal`, `Tuesdays 03:00-05:00 UTC`) in `87.9s`. `openclaw memory search "edge-fw-01"` scored `0.894` on `MEMORY.md:1-4`, and `Light Sleep` staged session corpus candidates at `confidence: 0.58`.
- **Use Case 4 (`10a`–`10d`):** `netops-crit-watchdog` (`--every 15m --no-deliver`) executed in `34 ms` with `completionStatus: "succeeded"`, `summary: "4"`, `exitCode: 0`.
- **Use Case 5 (`11a`–`11d`):** `openclaw security audit` reported `0 critical · 1 warn · 1 info`; `openclaw audit` logged millisecond `agent_run` and `tool_action` events; `llama3.1-64k:latest` emitted raw JSON (`{"name": "memory_get", ...}`) in plain text instead of invoking the tool.

---

## 5. Known Issues & Fixes

1. **WSL2 `/mnt/c` 9p SQLite Locking Hangs:** Never bind-mount `/home/node/.openclaw` to a Windows `/mnt/c` path — SQLite locking stalls `doctor --fix` and `gateway status`. Keep `/home/node/.openclaw` on a native Docker volume (`openclaw_lab_config`) and bind-mount only `./workspace`.
2. **Cold 13K System-Prompt Timeouts on 8 GB GPUs:** With `qwen3:8b` split `39% CPU / 61% GPU` at `32K` context, cold first-turn tool runs take `180–375s` (dropping to `30–88s` once KV prefix cache hits `80–99%`). Pass `--thinking off --timeout 540` on CLI agent turns.
3. **Local Cron Delivery Flag (`--no-deliver`):** When no external messaging channel (Slack/Telegram/Discord) is configured, pass `--no-deliver` to `openclaw cron add` so completed command jobs report `completionStatus: "succeeded"` instead of failing channel delivery.
4. **Offline-Only Memory Maintenance CLI:** `openclaw memory status` requires exclusive offline SQLite state ownership (`stop` the Gateway first). While the Gateway is running, use `openclaw memory search "<query>"` or in-session `memory_get` / `memory_search` tools.

---

## 6. Cleanup

To stop the container while preserving your configured volume and sessions:

```bash
docker compose stop
```
