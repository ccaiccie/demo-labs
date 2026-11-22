# Claude-BugHunter Local Security Assessment & Triage Lab

An authorized, loopback-only hands-on lab demonstrating how **Claude-BugHunter** security skills and deterministic triage workflows operate inside **Google Antigravity** against a deliberately vulnerable local NetOps Inventory & Ticket Portal (`http://127.0.0.1:8765`).

> **Authorized-Use Scope Notice:** This lab is strictly limited to `http://127.0.0.1:8765` using 100% synthetic RFC 5737 documentation IP addresses (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`) and `.lab.internal` hostnames and emails. Never run security probes against third-party domains, public IPs, or production systems without explicit written authorization. Nothing in this lab is submitted to HackerOne or any external bug bounty platform.

---

## What Claude-BugHunter Is (and Is Not)

**What it is:**
- An open-source bug bounty and application security skill library from [`elementalsouls/Claude-BugHunter`](https://github.com/elementalsouls/Claude-BugHunter).
- Ships **83 `SKILL.md` knowledge modules** (58 `hunt-*` web-application vulnerability skills, 10 enterprise platform attack skills, 6 reporting & validation skills, 5 recon & OSINT skills, and 4 methodology & mindset skills) built from **681 disclosed-report patterns** across **24 core vulnerability classes**.
- Includes a Python standard-library-only CLI (`scripts/cbh.py`) with five deterministic subcommands (`recon`, `surface`, `classify`, `triage`, `report`) that runs **offline / curl-only with no Anthropic API key required**.
- Encodes disciplined triage rules, notably the **7-Question Triage Gate** (`triage-validation/SKILL.md`), designed to kill false positives and low-value informational noise before writing a report.

**What it is not:**
- It is **not** a magic autonomous zero-config vulnerability scanner that replaces human verification.
- It is **not** a license to scan unauthorized targets.
- Its **15 slash commands** (`/hunt`, `/recon`, `/triage`, `/report`, `/validate`, `/chain`, `/autopilot`, etc.), plugin marketplace integration, and LLM-driven `/hunt` orchestration engine are **Claude-Code-only by upstream design**.

---

## Google Antigravity Installation & Compatibility

Claude-BugHunter's `SKILL.md` knowledge layer is multi-harness and installs cleanly into **Google Antigravity** (`%USERPROFILE%\.gemini\config\skills\`) without overwriting pre-existing unrelated skills:

```powershell
# From the cloned upstream repository
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 -AntiGravity -NoProfile
```

### Observed Installation Verification (`evidence/01-install-verify.txt`)
- **Installed directory:** `%USERPROFILE%\.gemini\config\skills\`
- **Total skill directories:** `85` (`83` Claude-BugHunter skills, including `58` `hunt-*` skills, plus pre-existing non-CBH skills preserved intact)
- **Key verified skill files:** `bb-methodology\SKILL.md`, `hunt-sqli\SKILL.md`, `hunt-xss\SKILL.md`, `hunt-idor\SKILL.md`, `triage-validation\SKILL.md`, `report-writing\SKILL.md`, `security-arsenal\SKILL.md`
- **`cbh` CLI verification (no Anthropic API key required):**
  - `python upstream-claude-bughunter\scripts\cbh.py --help` exited `0`
  - `cbh.py classify` deterministically mapped local lab URLs to relevant skills:
    - `http://127.0.0.1:8765/search?q=core-rtr-01` -> `hunt-sqli`, `hunt-xss`
    - `http://127.0.0.1:8765/api/devices?hostname=core-rtr-01.lab.internal` -> `hunt-api-misconfig`, `hunt-auth-bypass`, `hunt-idor`
    - `http://127.0.0.1:8765/api/tickets/102` -> `hunt-api-misconfig`, `hunt-idor`

### Honest Note on Claude-Code-Only Features
- In Google Antigravity, you get the **full 83-skill `SKILL.md` knowledge library** and the **stdlib-only `cbh.py` CLI** without needing an Anthropic API key.
- The **15 slash commands** (`commands/*.md`) and the Claude Code plugin `/hunt` engine do **not** run natively as Antigravity slash commands; instead, Antigravity loads the installed `SKILL.md` instructions directly to guide recon, testing, verification, and triage.

---

## Local Lab Architecture & Port Binding

The target is a self-contained Flask + SQLite **NetOps Inventory & Ticket Portal** (`app/app.py`) seeded from `testdata/seed.json` (3 synthetic users, 6 synthetic network devices, 5 synthetic maintenance tickets).

- **Port binding:** Strictly `127.0.0.1:8765` (`127.0.0.1:8765:8765` in `docker-compose.yml`; never exposed on `0.0.0.0`).
- **Endpoints:**
  - `GET /health` — returns `{"mode": "vulnerable"|"patched", "patches": {"idor": bool, "sqli": bool, "xss": bool}, "status": "ok"}`
  - `GET /` — NetOps Inventory & Ticket Portal dashboard
  - `GET /search?q=<term>` — reflected search page (`text/html`); intentionally unescaped when `PATCH_XSS!=1`, HTML-escaped when `PATCH_XSS=1`
  - `GET /api/devices?hostname=<name>` — device inventory JSON API; intentionally string-formatted SQLite query when `PATCH_SQLI!=1`, parameterized query when `PATCH_SQLI=1`
  - `GET /api/tickets/<id>` — maintenance ticket JSON API; returns any ticket including `internal_note` when `PATCH_IDOR!=1`, enforces `X-Lab-User == ticket.owner` (else HTTP `403`) when `PATCH_IDOR=1`
  - `GET /api/status?check=<val>` — benign diagnostic JSON endpoint (`application/json` + `X-Content-Type-Options: nosniff`) used to demonstrate False Positive triage

---

## How to Run, Test, Patch, and Stop

### 1. Start in Vulnerable Mode
```powershell
wsl -e bash -lc 'cd /mnt/c/Users/superuser/ag-lab/claude-bughunter-1122 && docker compose up -d --build'
curl.exe -s http://127.0.0.1:8765/health
```

### 2. Run the Reproducible Assessment Suite (Before Patch)
```powershell
python tests\run_lab_tests.py --out-txt evidence\02-scan-before.txt --out-json evidence\findings-before.json
```

### 3. Apply All Three Patches and Restart
```powershell
wsl -e bash -lc 'cd /mnt/c/Users/superuser/ag-lab/claude-bughunter-1122 && PATCH_SQLI=1 PATCH_XSS=1 PATCH_IDOR=1 docker compose up -d --force-recreate'
curl.exe -s http://127.0.0.1:8765/health
```

### 4. Re-Run the Exact Same Suite (After Patch) and Generate Diff
```powershell
python tests\run_lab_tests.py --out-txt evidence\04-scan-after.txt --out-json evidence\findings-after.json
python tests\generate_diff.py
```

### 5. Revert to Vulnerable Mode (Optional)
```powershell
wsl -e bash -lc 'cd /mnt/c/Users/superuser/ag-lab/claude-bughunter-1122 && PATCH_SQLI=0 PATCH_XSS=0 PATCH_IDOR=0 docker compose up -d --force-recreate'
```

### 6. Stop and Remove the Container
```powershell
wsl -e bash -lc 'cd /mnt/c/Users/superuser/ag-lab/claude-bughunter-1122 && docker compose down'
```

---

## Observed Findings & Before/After Remediation Results

All results below are taken directly from `evidence/02-scan-before.txt`, `evidence/03-triage-and-verification.md`, `evidence/04-scan-after.txt`, and `evidence/05-before-after-diff.txt`.

| Case ID | Endpoint / Vector | Claude-BugHunter Skill | Classification | Before Patch (`vulnerable`) | After Patch (`patched`) |
|---|---|---|---|---|---|
| `BASE-001` | `GET /health` | `bb-methodology` | Baseline | HTTP `200` (`status: ok`) | HTTP `200` (`status: ok`) |
| `BASE-002` | `GET /api/devices?hostname=core-rtr-01.lab.internal` | `bb-methodology` | Baseline | HTTP `200`, `count: 1` (`192.0.2.10`) | HTTP `200`, `count: 1` (`192.0.2.10`) |
| `BASE-003` | `GET /search?q=core-rtr-01` | `bb-methodology` | Baseline | HTTP `200`, `text/html` | HTTP `200`, `text/html` |
| `BASE-004` | `GET /api/tickets/101` (`X-Lab-User: alice.netops`) | `bb-methodology` | Baseline | HTTP `200`, owner ticket returned | HTTP `200`, owner ticket returned |
| `SQLI-001` | `GET /api/devices?hostname=' OR '1'='1` | `hunt-sqli` | **True Positive (TP)** | HTTP `200`, `count: 6` (all 6 synthetic devices dumped) | HTTP `200`, `count: 0`, `devices: []` (parameterized query) |
| `XSS-001` | `GET /search?q=<script>alert('LAB-XSS-PROOF')</script>` | `hunt-xss` | **True Positive (TP)** | HTTP `200`, unescaped `<script>` (browser alert dialog `'LAB-XSS-PROOF'` fired) | HTTP `200`, HTML-escaped `&lt;script&gt;alert(&#x27;LAB-XSS-PROOF&#x27;)&lt;/script&gt;` (0 dialogs) |
| `IDOR-001` | `GET /api/tickets/102` (`X-Lab-User: carol.noc`) | `hunt-idor` | **True Positive (TP)** | HTTP `200`, leaked `bob.secops`'s ticket `102` and `internal_note` | HTTP `403`, `{"error":"forbidden","message":"Access denied: X-Lab-User does not match ticket owner."}` |
| `FP-001` | `GET /api/status?check=<script>alert('FP-CHECK')</script>` | `triage-validation` | **False Positive (FP)** | HTTP `200`, `application/json` + `X-Content-Type-Options: nosniff` (not executable HTML) | Unchanged (`FP_CONFIRMED`); no patch needed |
| `HDR-001` | `GET /` (response headers) | `triage-validation` | **Informational (Kill Standalone)** | Missing CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, HSTS | Defensive hardening advice only; not a standalone finding |

**Summary Counts:**
- **Before patch:** `8/8` test cases executed cleanly — **4 baselines passed**, **3 True Positives confirmed**, **1 False Positive confirmed**, plus **1 standalone informational header check killed**.
- **After patch:** `8/8` test cases executed cleanly — **4 baselines passed** (zero functional regressions), **0 True Positives remaining** (**3/3 verified patched**), **1 False Positive unchanged**.

---

## 7-Question Triage Gate Summary (`evidence/03-triage-and-verification.md`)

Using `triage-validation/SKILL.md` (rule: ask Q1–Q7 in order; one failing answer kills the finding):

1. **`SQLI-001` (`hunt-sqli`) — PASS (7/7):** Unauthenticated single request dumps all 6 inventory rows; root cause in `app/app.py`; proven data extraction beyond an error message. Verified fixed with `PATCH_SQLI=1`.
2. **`XSS-001` (`hunt-xss`) — PASS (7/7, with Q6 calibration note):** Unescaped `<script>` reflected into `text/html` and confirmed executing in a browser. Per `triage-validation` Q6, a real bounty report should demonstrate session or data impact beyond an `alert()` popup. Verified fixed with `PATCH_XSS=1`.
3. **`IDOR-001` (`hunt-idor`) — PASS (7/7):** Non-owner `carol.noc` retrieved `bob.secops`'s ticket `102` and its `internal_note`. Verified fixed with `PATCH_IDOR=1` (HTTP `403`).
4. **`FP-001` (`triage-validation`) — KILLED at Q1 (False Positive):** Even though `<script>` appears in the JSON body, `Content-Type: application/json` plus `X-Content-Type-Options: nosniff` prevents browser script execution.
5. **`HDR-001` (`triage-validation`) — KILLED Standalone (Q1/Q7):** Missing hardening headers belong on the never-submit-standalone list unless chained to a proven exploit; tracked solely as defensive guidance.

---

## Evidence & Repository Layout

- `app/app.py`, `app/requirements.txt` — Deliberately vulnerable / patch-toggleable Flask + SQLite fixture
- `Dockerfile`, `docker-compose.yml` — Loopback-only (`127.0.0.1:8765`) container definition
- `testdata/seed.json` — 100% synthetic RFC 5737 devices, users, and maintenance tickets
- `testdata/test-payloads.json` — Local-only baseline, TP, and FP test definitions
- `tests/run_lab_tests.py`, `tests/generate_diff.py` — Stdlib-only loopback-enforced verification scripts
- `evidence/` — Captured install verification, before/after HTTP logs, JSON findings, 7-Question triage evaluation, before/after diff, and clean light-background screenshots
- `prompts/PROMPTS.md` — Documented user prompt and lab workflow steps

---

## Known Limits

- This lab uses a simplified local Flask + SQLite fixture with header-based identity (`X-Lab-User`) rather than full OAuth/OIDC or multi-tier production authentication.
- Claude-BugHunter's 15 slash commands (`/hunt`, `/triage`, `/report`, etc.) and autonomous `/hunt` orchestrator require Claude Code; in Google Antigravity, the 83 `SKILL.md` modules and deterministic `cbh.py` CLI are used directly.
- Running `tests/run_lab_tests.py` validates the local fixture only and enforces loopback-only (`127.0.0.1`) targets.
