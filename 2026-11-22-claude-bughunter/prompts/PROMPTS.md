# Lab Prompts & Workflow Steps

This file documents the user goal and the structured hands-on workflow used to build, test, triage, and remediate the **Claude-BugHunter Local Security Assessment & Triage Lab**.

---

## Original Lab Goal

Build an authorized, loopback-only local lab (`http://127.0.0.1:8765`) to evaluate **Claude-BugHunter** (`https://github.com/elementalsouls/Claude-BugHunter`) inside **Google Antigravity**, verify what works without an Anthropic API key, run structured vulnerability assessments against a realistic NetOps Inventory & Ticket Portal using 100% synthetic RFC 5737 data, independently separate True Positives from False Positives using the 7-Question Triage Gate, apply targeted patches, and verify before/after remediation with zero regressions.

---

## Step-by-Step Workflow

### Step 1: Preflight, Upstream Research & Antigravity Skill Installation
1. Verify port `127.0.0.1:8765` is free on both Windows (`netstat`) and WSL (`ss`).
2. Clone `https://github.com/elementalsouls/Claude-BugHunter` locally and inspect its `README.md`, `INSTALL.md`, `USAGE.md`, `docs/multi-harness.md`, and `scripts/install.ps1`.
3. Confirm non-destructive installation behavior and install the **83** Claude-BugHunter `SKILL.md` modules into Google Antigravity (`%USERPROFILE%\.gemini\config\skills\`) using:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 -AntiGravity -NoProfile
   ```
4. Verify pre-existing unrelated skills remain intact and verify that `scripts/cbh.py` runs offline/curl-only without an Anthropic API key.

### Step 2: Synthetic NetOps Test Data & Local Fixture Build
1. Create `testdata/seed.json` with 100% synthetic NetOps records: 3 users (`alice.netops`, `bob.secops`, `carol.noc`), 6 devices using only RFC 5737 IPs (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`) and `.lab.internal` hostnames, and 5 maintenance tickets with synthetic non-secret internal notes.
2. Create `testdata/test-payloads.json` defining 4 functional baselines (`BASE-001`..`004`), 3 True Positive probes (`SQLI-001`, `XSS-001`, `IDOR-001`), and 1 False Positive check (`FP-001`).
3. Build `app/app.py` (Flask + SQLite), `Dockerfile` (`python:3.12-slim`), and `docker-compose.yml` bound strictly to `127.0.0.1:8765:8765` with independent patch toggles (`PATCH_SQLI`, `PATCH_XSS`, `PATCH_IDOR`).
4. Launch the container in vulnerable mode and verify `GET http://127.0.0.1:8765/health` returns HTTP `200`.

### Step 3: Claude-BugHunter-Guided Assessment (Before Patch)
1. Classify local lab endpoints with `cbh.py classify` to map URLs to `hunt-sqli`, `hunt-xss`, `hunt-idor`, and `hunt-api-misconfig`.
2. Execute `tests/run_lab_tests.py` against `http://127.0.0.1:8765` in vulnerable mode and capture full HTTP requests and responses in `evidence/02-scan-before.txt` and `evidence/findings-before.json`.
3. Capture clean visual evidence of the dashboard, reflected XSS, and SQL injection in `evidence/screenshots/`.

### Step 4: Independent TP/FP Verification & 7-Question Triage Gate
1. Independently validate every candidate finding in `evidence/03-triage-and-verification.md`:
   - Confirm `SQLI-001`, `XSS-001`, and `IDOR-001` as True Positives passing all 7 local triage questions.
   - Confirm `FP-001` (`/api/status?check=<script>...`) as a False Positive killed at Q1 because it returns `application/json` with `X-Content-Type-Options: nosniff`.
   - Kill `HDR-001` (missing hardening headers on `GET /`) as a standalone finding per `triage-validation/SKILL.md`.
2. Keep all triage strictly local; never submit lab findings to external bug bounty platforms.

### Step 5: Patch Application & Before/After Verification
1. Recreate the container with `PATCH_SQLI=1 PATCH_XSS=1 PATCH_IDOR=1`.
2. Re-run `tests/run_lab_tests.py` to produce `evidence/04-scan-after.txt` and `evidence/findings-after.json`.
3. Run `tests/generate_diff.py` to generate `evidence/05-before-after-diff.txt`, verifying all 3 True Positives are remediated (`PATCHED_VERIFIED`), all 4 baselines still pass with zero regressions, and `FP-001` remains unchanged (`FP_CONFIRMED`).
