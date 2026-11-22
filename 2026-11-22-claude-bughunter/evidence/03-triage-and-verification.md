# Independent Verification & 7-Question Triage Gate Evaluation

> **Scope Notice:** All tests and triage evaluations below were executed **exclusively** against the authorized local NetOps Inventory & Ticket Portal fixture at `http://127.0.0.1:8765` using 100% synthetic RFC 5737 / `.lab.internal` data. **No external targets were tested and nothing was submitted to HackerOne or any bug bounty platform.**

## 1. Independent Verification Summary

| ID | Endpoint / Vector | Claude-BugHunter Skill | Naive Signal | Independent Verification Verdict | Pre-Patch Observation | Post-Patch Observation |
|---|---|---|---|---|---|---|
| `SQLI-001` | `GET /api/devices?hostname=' OR '1'='1` | `hunt-sqli` | Extra rows returned | **True Positive (TP)** | HTTP `200`, `count: 6` — dumps all 6 devices (`core-rtr-01.lab.internal` through `mgmt-jump-06.lab.internal`), vs baseline `count: 1`. | HTTP `200`, `count: 0`, `devices: []` (parameterized SQLite query). |
| `XSS-001` | `GET /search?q=<script>alert('LAB-XSS-PROOF')</script>` | `hunt-xss` | Reflected `<script>` | **True Positive (TP)** | HTTP `200` (`text/html`), unescaped `<script>alert('LAB-XSS-PROOF')</script>` in `<h2>Results for: ...</h2>`; verified real Chromium dialog `'LAB-XSS-PROOF'`. | HTTP `200` (`text/html`), HTML-escaped `&lt;script&gt;alert(&#x27;LAB-XSS-PROOF&#x27;)&lt;/script&gt;`; zero browser dialogs fired. |
| `IDOR-001` | `GET /api/tickets/102` with `X-Lab-User: carol.noc` | `hunt-idor` | HTTP 200 on foreign ID | **True Positive (TP)** | HTTP `200`, returns `bob.secops`'s ticket `102` including `internal_note` (`LAB-TICKET-NOTE-ONLY-198-51-100-42`). | HTTP `403`, `{"error":"forbidden","message":"Access denied: X-Lab-User does not match ticket owner."}`. |
| `FP-001` | `GET /api/status?check=<script>alert('FP-CHECK')</script>` | `triage-validation` | Reflected `<script>` in body | **False Positive (FP)** | HTTP `200`, `Content-Type: application/json`, `X-Content-Type-Options: nosniff`. Browsers do not execute HTML/JS in JSON responses. | Unchanged (`FP_CONFIRMED`); no fix needed because endpoint is not exploitable. |
| `HDR-001` | `GET /` (response headers) | `triage-validation` | Missing CSP, XFO, XCTO, Referrer-Policy, HSTS | **Informational / Kill Standalone** | Missing 5 hardening headers on `GET /`. Useful as defense-in-depth context, but **not** a standalone bounty finding without a proven exploit chain. | Same headers; hardening recommended defensively, not filed standalone. |

**Verified Counts (Pre-Patch):**
- Baselines passed: **4 / 4** (`BASE-001` through `BASE-004`)
- Confirmed True Positives (TP): **3** (`SQLI-001`, `XSS-001`, `IDOR-001`)
- Confirmed False Positives (FP): **1** (`FP-001`)
- Standalone Informational (killed by gate): **1** (`HDR-001`)

---

## 2. Claude-BugHunter 7-Question Triage Gate (Local Lab Evaluation)

Evaluated per `%USERPROFILE%\.gemini\config\skills\triage-validation\SKILL.md`. Rule: **Ask Q1–Q7 in order; one failing answer kills the finding.**

### Finding 1: `SQLI-001` — SQL Injection on `GET /api/devices?hostname=` (`hunt-sqli`)
- **Q1 (Exploitable right now, step-by-step?):** **PASS.** Reproducible single-request `GET http://127.0.0.1:8765/api/devices?hostname=%27+OR+%271%27%3D%271` requires no authentication and dumps all 6 rows from the `devices` table (vs 1 row on baseline).
- **Q2 (On accepted impact list?):** **PASS.** SQL injection with confirmed data extraction is universally accepted (High/Critical tier).
- **Q3 (Root cause in an in-scope asset?):** **PASS (Local Lab Scope).** Root cause is in `app/app.py` on `127.0.0.1:8765`.
- **Q4 (Does it require privileged access?):** **PASS.** Unauthenticated GET request.
- **Q5 (Already known / intended behavior?):** **PASS.** Unintended string-concatenated SQL query in vulnerable mode.
- **Q6 (Proven impact beyond "technically possible"?):** **PASS.** Demonstrated extraction of all 6 inventory records (`mgmt-jump-06.lab.internal`, `203.0.113.50`, etc.), not just a SQL error message.
- **Q7 (Known-invalid / never-submit class?):** **PASS.** Valid vulnerability class.
- **Local Gate Decision:** **PASS (All 7/7) — Confirmed High/Critical TP.** Verified fixed when `PATCH_SQLI=1` (`count: 0`).

### Finding 2: `XSS-001` — Reflected XSS on `GET /search?q=` (`hunt-xss`)
- **Q1 (Exploitable right now, step-by-step?):** **PASS.** `GET http://127.0.0.1:8765/search?q=%3Cscript%3Ealert%28%27LAB-XSS-PROOF%27%29%3C%2Fscript%3E` reflects unescaped `<script>` into `text/html`.
- **Q2 (On accepted impact list?):** **PASS.** Reflected XSS on a web portal is an accepted Medium/High class.
- **Q3 (Root cause in an in-scope asset?):** **PASS (Local Lab Scope).** Root cause in `app/app.py` `/search` handler.
- **Q4 (Requires privileged access?):** **PASS.** Any user visiting the crafted URL triggers execution.
- **Q5 (Already known / intended behavior?):** **PASS.** Unintended unescaped HTML interpolation.
- **Q6 (Proven impact beyond "technically possible"?):** **PASS (Lab Proof; note real-bounty downgrade caveat).** Confirmed actual JavaScript execution in headless Chromium (`dialogs=['LAB-XSS-PROOF']`). Note: per `triage-validation` Q6, in a real bounty program you would demonstrate session/data impact rather than only `alert()`, which is noted as a severity-calibration reminder.
- **Q7 (Known-invalid / never-submit class?):** **PASS.** Valid reflected XSS.
- **Local Gate Decision:** **PASS (All 7/7) — Confirmed Medium TP.** Verified fixed when `PATCH_XSS=1` (`&lt;script&gt;` escaped, zero browser dialogs).

### Finding 3: `IDOR-001` — Horizontal IDOR on `GET /api/tickets/<id>` (`hunt-idor`)
- **Q1 (Exploitable right now, step-by-step?):** **PASS.** Acting as `X-Lab-User: carol.noc`, `GET http://127.0.0.1:8765/api/tickets/102` returns HTTP 200 with `bob.secops`'s private ticket and `internal_note`.
- **Q2 (On accepted impact list?):** **PASS.** Cross-user authorization bypass (IDOR) leaking another user's private record is accepted (Medium/High).
- **Q3 (Root cause in an in-scope asset?):** **PASS (Local Lab Scope).** Root cause in `app/app.py` `/api/tickets/<id>` handler.
- **Q4 (Requires privileged access?):** **PASS.** Standard non-owner user (`carol.noc`) reads `bob.secops`'s ticket.
- **Q5 (Already known / intended behavior?):** **PASS.** Tickets are user-owned; `PATCH_IDOR=1` enforces `X-Lab-User == ticket.owner`.
- **Q6 (Proven impact beyond "technically possible"?):** **PASS.** Retrieved exact foreign user data (`owner: "bob.secops"`, `internal_note: "LAB-TICKET-NOTE-ONLY-198-51-100-42..."`), not just a 200 status code.
- **Q7 (Known-invalid / never-submit class?):** **PASS.** Valid broken object-level authorization.
- **Local Gate Decision:** **PASS (All 7/7) — Confirmed Medium/High TP.** Verified fixed when `PATCH_IDOR=1` (HTTP `403 Forbidden`).

### Candidate 4: `FP-001` — Reflected `<script>` on `GET /api/status?check=` (`triage-validation`)
- **Q1 (Exploitable right now, step-by-step?):** **FAIL — KILL.** Although a naive regex scanner sees `<script>alert('FP-CHECK')</script>` echoed in the response body, the response is served with `Content-Type: application/json` and `X-Content-Type-Options: nosniff`. Browsers treat the response as JSON data, never parsing or executing `<script>` tags.
- **Local Gate Decision:** **KILLED at Q1 — Confirmed False Positive (FP).** Demonstrates why independent verification against live HTTP headers and browser rendering prevents bogus reports.

### Candidate 5: `HDR-001` — Missing Security Headers on `GET /` (`triage-validation`)
- **Q1 / Q7:** **FAIL — KILL STANDALONE.** Missing `Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, and `Strict-Transport-Security` are on the `triage-validation` **NEVER SUBMIT standalone** list unless chained to a concrete exploit (e.g., working clickjacking PoC or CSP-bypass-amplified XSS). Recorded as defensive hardening guidance only.
