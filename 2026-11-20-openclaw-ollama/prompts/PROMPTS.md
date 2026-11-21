# Prompts Used — 2026-11-20-openclaw-ollama

Every prompt sent to OpenClaw in order during the hands-on lab, including follow-ups.

## 1. One-Shot Network Engineering Prompt (Cold Load — `ollama/llama3.1-64k:latest`)
```text
Explain RFC 5737 documentation IPv4 prefixes in 3 concise bullet points for a network engineer.
```
- **Result:** 97.84 s, exit 0. Model printed a raw JSON `web_fetch` block as plain text instead of answering directly.

## 2. One-Shot Direct Follow-Up (Warm — `ollama/llama3.1-64k:latest`)
```text
Answer directly from your own knowledge without calling any tools: explain RFC 5737 documentation IPv4 prefixes in 3 concise bullet points for a network engineer.
```
- **Result:** 34.88 s, exit 0. Model hallucinated `192.0.0.0/24`, `192.0.0.0/29`, and `192.0.0.0/30` (incorrect; real RFC 5737 prefixes are `192.0.2.0/24`, `198.51.100.0/24`, and `203.0.113.0/24`).

## 3. Real Tool-Using Agent Task — Model 1 (`ollama/llama3.1-64k:latest`)
```text
Read network_syslog.log in your workspace. Write a Python 3 script named parse_syslog.py in your workspace that parses network_syslog.log, counts total events per device, counts events per severity (CRIT, ERR, WARN, INFO), counts total SSH_AUTH_FAIL events and per-device SSH_AUTH_FAIL counts, and writes the structured JSON result to summary.json. Run python3 parse_syslog.py and report the exact counts from summary.json.
```
- **Result:** 119.49 s, exit 0. Model failed native tool calling (printed JSON function blocks in plain text; zero files created).

## 4. Real Tool-Using Agent Task — Model 2 (`ollama/qwen3:8b`)
```text
Read network_syslog.log in your workspace. Write a Python 3 script named parse_syslog.py in your workspace that parses network_syslog.log, counts total events per device, counts events per severity (CRIT, ERR, WARN, INFO), counts total SSH_AUTH_FAIL events and per-device SSH_AUTH_FAIL counts, and writes the structured JSON result to summary.json. Run python3 parse_syslog.py and report the exact counts from summary.json.
```
- **Result:** 238.56 s, exit 0. Autonomously called `read`, `write`, and `exec`; wrote `parse_syslog.py`, executed it, generated `summary.json`, and matched independent Python ground-truth verification 100% across all 24 events, 5 devices, 4 severities, and 5 `SSH_AUTH_FAIL` entries.
