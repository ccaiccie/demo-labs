# OpenClaw + Local Ollama on Windows WSL2 (2026-11-20-openclaw-ollama)

Hands-on Network Technician lab running **OpenClaw** (`ghcr.io/openclaw/openclaw:latest`, v2026.11.6) 100% locally against **Ollama** on Windows + WSL2 Docker, with zero cloud API keys, zero paid accounts, and zero messaging channels.

## What This Lab Tests
- Verifying official OpenClaw upstream sources (`docs.openclaw.ai`, `openclaw.ai/install.sh`, `github.com/openclaw/openclaw`, `ghcr.io/openclaw/openclaw:latest`).
- Connecting containerized OpenClaw in WSL2 Docker (`network_mode: host`) to Windows Ollama on `http://127.0.0.1:11434` via WSL2 mirrored networking without changing Ollama's bind address.
- Running the OpenClaw Gateway on loopback port `18789` with a local token in `.env` (gitignored).
- Comparing two local 8B Ollama models (`ollama/llama3.1-64k:latest` vs `ollama/qwen3:8b`) on a real network engineering tool task: parsing a 24-line RFC 5737 / `lab.internal` syslog file with Python and verifying every count independently against ground truth.

## Requirements
- Windows 11 with WSL2 (mirrored networking enabled) and Docker Engine inside WSL2.
- Ollama running locally on Windows (`127.0.0.1:11434`) with tool-capable local models installed:
  - `llama3.1-64k:latest` (8.0B Q4_K_M, 4.9 GB, `num_ctx: 64000`, `capabilities: completion, tools`)
  - `qwen3:8b` (8.2B Q4_K_M, 5.2 GB, 40K context, `capabilities: completion, tools, thinking`)
- Ports:
  - `127.0.0.1:11434` — existing local Ollama service (untouched)
  - `127.0.0.1:18789` — OpenClaw Gateway & Control UI (loopback-only; verify free with `netstat -ano` first)

## Exact Install & Run Steps

1. **Verify ports and Ollama reachability from WSL2:**
   ```powershell
   netstat -ano | findstr ":11434 :18789 "
   ollama list
   wsl curl -s http://127.0.0.1:11434/api/tags
   ```

2. **Create a gitignored `.env` with a random gateway token (never commit or print):**
   ```powershell
   $tok = ([guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')).Substring(0,48)
   Set-Content -Encoding ASCII -NoNewline -Path .env -Value "OPENCLAW_GATEWAY_TOKEN=$tok`n"
   ```

3. **Pull the official image and start the isolated stack:**
   ```powershell
   wsl docker pull ghcr.io/openclaw/openclaw:latest
   wsl docker compose up -d
   ```

4. **Seed the local-only `openclaw.json` into the native Linux Docker volume and restart:**
   ```powershell
   wsl docker cp config/openclaw.json openclaw-ollama-lab:/home/node/.openclaw/openclaw.json
   wsl docker compose up -d
   ```

5. **Run CLI health checks (wrapped in `timeout 60`):**
   ```powershell
   wsl docker exec openclaw-ollama-lab timeout 60 openclaw --version
   wsl docker exec openclaw-ollama-lab timeout 60 openclaw gateway status
   wsl docker exec openclaw-ollama-lab timeout 60 openclaw models list
   wsl docker exec openclaw-ollama-lab timeout 60 openclaw doctor --non-interactive
   ```

6. **Run the syslog parser agent task (example with `ollama/qwen3:8b`):**
   Copy `fixtures/network_syslog.log` into `workspace/network_syslog.log`, then run:
   ```powershell
   wsl docker exec openclaw-ollama-lab timeout 260 openclaw agent \
     --session-id lab-syslog-qwen3 \
     --model ollama/qwen3:8b \
     --message "Read network_syslog.log in your workspace. Write a Python 3 script named parse_syslog.py in your workspace that parses network_syslog.log, counts total events per device, counts events per severity (CRIT, ERR, WARN, INFO), counts total SSH_AUTH_FAIL events and per-device SSH_AUTH_FAIL counts, and writes the structured JSON result to summary.json. Run python3 parse_syslog.py and report the exact counts from summary.json." \
     --timeout 240
   ```

7. **Verify the Control UI:**
   Open `http://127.0.0.1:18789/` in a browser. The UI loads `OpenClaw Control` and enforces token authentication (`This Gateway expects its token` for `ws://127.0.0.1:18789`).

## Observed Results

| Test | Model | Wall-Clock Time | Memory (`ollama ps`) | Outcome |
| --- | --- | --- | --- | --- |
| One-shot RFC 5737 (cold) | `ollama/llama3.1-64k:latest` | 97.84 s | 13 GB (56%/44% CPU/GPU, 64K ctx) | Printed raw JSON `web_fetch` text instead of answering |
| One-shot RFC 5737 (warm, direct) | `ollama/llama3.1-64k:latest` | 34.88 s | 13 GB (56%/44% CPU/GPU, 64K ctx) | Hallucinated `192.0.0.0/24`, `/29`, `/30` (incorrect) |
| Syslog parser agent task | `ollama/llama3.1-64k:latest` | 119.49 s | 13 GB (56%/44% CPU/GPU, 64K ctx) | Printed raw JSON tool blocks in prose; 0 files created |
| Syslog parser agent task | `ollama/qwen3:8b` | 238.56 s | 10 GB (39%/61% CPU/GPU, 32K ctx) | **Succeeded**: ran `read`, `write`, `exec`; created `parse_syslog.py` & `summary.json`; **100% match** against ground truth |

### Independent Ground-Truth Verification (24 Syslog Lines)
- **Devices:** `core-rtr-01.lab.internal=7`, `edge-fw-01.lab.internal=6`, `dist-sw-01.lab.internal=5`, `dist-sw-02.lab.internal=3`, `wan-rtr-02.lab.internal=3` — **100% match**
- **Severities:** `CRIT=4`, `ERR=8`, `WARN=8`, `INFO=4` — **100% match**
- **`SSH_AUTH_FAIL`:** 5 total (`edge-fw-01.lab.internal=3`, `dist-sw-01.lab.internal=1`, `wan-rtr-02.lab.internal=1`) — **100% match**
- **Code-review note:** `parse_syslog.py` stored `total_ssh_auth_fail` as the per-device dictionary instead of a scalar integer `5`, while every underlying device and severity count is exact.

## Known Issues & Real Fixes
1. **WSL2 `/mnt/c` (9p) mount hangs `openclaw doctor --fix`:**
   - **Symptom:** Container stayed in `health: starting` and turned `unhealthy`; port `18789` returned `HTTP=000`; `docker top` showed `openclaw doctor --fix --non-interactive` spinning on CPU (>2m33s).
   - **Fix:** Move `/home/node/.openclaw` onto a native Linux Docker volume (`openclaw_lab_config` on ext4) while keeping `./workspace` bind-mounted. Startup dropped to 3.7 seconds.
2. **8B Llama 3.1 tool-calling breakdown under large tool schemas:**
   - **Symptom:** `ollama/llama3.1-64k:latest` printed JSON function calls as plain text and created no files.
   - **Fix:** Switch to `ollama/qwen3:8b` (`--model ollama/qwen3:8b`), which natively executed `read`, `write`, and `exec` tools end to end.
3. **Wrap CLI checks in `timeout 60`:**
   - Prevents diagnostic commands like `openclaw gateway status` from hanging if the gateway is still starting or unhealthy.

## Lab Files
- `docker-compose.yml` — Isolated WSL Docker Compose stack (`network_mode: host`, native ext4 config volume)
- `config/openclaw.json` — Local-only Ollama provider & loopback gateway configuration (no secrets)
- `fixtures/network_syslog.log` — 24-line RFC 5737 / `lab.internal` sample syslog dataset
- `workspace/parse_syslog.py` — Python parser generated by OpenClaw (`ollama/qwen3:8b`)
- `workspace/summary.json` — Structured JSON output generated by `parse_syslog.py`
- `prompts/PROMPTS.md` — Exact prompts used in order
- `evidence/` — Raw verification logs, model outputs, ground-truth check, and Control UI screenshot

## Cleanup
```powershell
wsl docker compose stop
# Optional full removal (including the isolated config volume):
# wsl docker compose down -v
```
