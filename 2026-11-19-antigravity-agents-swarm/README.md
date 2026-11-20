# Google Antigravity 2.33 + Gemini 4 Neon: agents, subagents, Orchestrator and /swarm

Dated lab folder for the Network Technician channel: `2026-11-19-antigravity-agents-swarm`.

Video: link will be added after upload.

This is a long, hands-on course (about 85 minutes) recorded live on a Windows 11 workstation with **Google Antigravity 2.33.0** signed in to a Google AI Pro account. Everything on screen really happened: the prompts, the waiting, the failures and the fixes. It covers:

- First launch, onboarding and the interface (conversations, projects, Automations, Customizations)
- Settings: permissions, models and usage, browser, conversations and the customization token budget
- Models and thinking levels: Gemini 4 Neon Low / Medium / High / Extra, and **Orchestrator (Neon)**
- Project 1: a Cisco syslog triage tool built with Neon High, verified in the terminal, then fixed with Neon Low
- The Review tab, a `.gitignore` and a clean commit made by the agent
- **Orchestrator with four parallel subagents** building a config-backup auditor (diff + security audit + HTML report + tests, 74 tests pass)
- **`/swarm` with nine members** building a reusable narrated demo-video pipeline (Docker lab app, Playwright driver, ffmpeg recorder, Kokoro narration, loudness/RMS checker, HTML player)
- A live end-to-end run of that pipeline: a sandbox `Wsl/E_ACCESSDENIED` failure, `gdigrab` error 5, swarm feedback on the Board, and a working narrated video
- The built-in browser and the browser subagent (with the URL permission prompt)
- Project rules, reusable skills, Automations and MCP
- What the whole session actually used from the weekly and five-hour quota
- A recipe for using Antigravity to make demo videos like the ones on this channel

No paid add-ons were used. **Enable AI Credit Overages was left OFF** for the entire session.

## Folder contents

| Path | What it is |
|---|---|
| `netops-tools/` | Project 1 + the Orchestrator project, exactly as the agents left it (no `.git`, no `__pycache__`) |
| `netops-tools/syslog_triage.py` | Cisco IOS/ASA syslog triage CLI (PRI decode, Cisco tag severity, alerts, mismatches, `--json`) |
| `netops-tools/config_diff.py` | Section-aware diff of two IOS backups (Config Diff Developer subagent) |
| `netops-tools/security_audit.py` | Six risky-setting rules with severities (Security Audit Developer subagent) |
| `netops-tools/netaudit.py` | CLI that combines both and writes a self-contained HTML report (NetAudit CLI Developer subagent) |
| `netops-tools/tests/` | 74 unittest cases (Unit Test Developer subagent + the original syslog tests) |
| `netops-tools/samples/` | `sample.log` and two dated backups of `edge-rtr1` (made-up lab data) |
| `netops-tools/reports/` | The HTML report generated during the recording |
| `demo-pipeline/` | The pipeline the 9-member swarm built, plus the live-run fixes (no `out/` binaries) |
| `demo-pipeline/lab/` | Flask "NetOps Status" app, `Dockerfile`, `docker-compose.yml` (published on `127.0.0.1:8099` only) |
| `demo-pipeline/driver/drive.py` | Playwright driver, writes `steps.json`; holds each step for its narration length; Playwright 1080p video fallback |
| `demo-pipeline/record/` | ffmpeg `gdigrab` recorder + its tests |
| `demo-pipeline/tts/narrate.py` | Kokoro `am_michael` narration with the "eye pee" and "reed" pronunciation rules and a `--self-test` |
| `demo-pipeline/assemble/assemble.py` | Mux, `loudnorm`, per-minute active-speech RMS report (pass = spread of 1.5 dB or less) |
| `demo-pipeline/player/make_html.py` | HTML player with 1x / 1.5x / 2x buttons |
| `demo-pipeline/run_all.ps1` | Runs all six steps (`-SkipDockerDown` keeps the lab running) |
| `demo-pipeline/script.json` | The four-line narration script for the sample video |
| `demo-pipeline/.agents/rules/demo-video-conventions.md` | Always-on workspace rule created in chapter 13 |
| `demo-pipeline/.agents/skills/make-demo/SKILL.md` | Reusable `make-demo` skill created in chapter 13 |
| `course-build/` | The scripts used to produce this course video (TTS, cards, privacy OCR scan, render with masks, RMS check) and `segments.json` (the full narration script) |

## Chapter guide

| Time | Chapter |
|---|---|
| 0:00 | Intro |
| 0:44 | Course roadmap |
| 3:35 | First launch and onboarding |
| 6:28 | Interface tour |
| 10:53 | Settings, permissions, browser, and usage |
| 15:02 | Models, thinking levels, and Orchestrator |
| 18:01 | First project: a syslog triage tool with Neon High |
| 24:28 | Verify like an engineer and fix with Neon Low |
| 29:05 | Review tab, .gitignore and a clean commit |
| 33:02 | Orchestrator and subagents |
| 43:19 | /swarm: nine agents build a demo-video pipeline |
| 52:04 | Live run: failures, swarm feedback, and a working video |
| 1:01:11 | Built-in browser and browser subagent |
| 1:07:08 | Project rules, reusable skills, Automations, and MCP |
| 1:17:18 | What the session actually used: quotas |
| 1:19:30 | Recipe: recording demo videos with Antigravity |
| 1:24:42 | Outro |

## Requirements to reproduce

- Windows 10/11 with Google Antigravity 2.x installed (user install) and a Google account. Free quota is enough for the small tasks; `/swarm` is marked "Preview & Quota Heavy".
- Python 3.11+ on Windows (`python` on PATH), Git for Windows.
- WSL 2 with Docker Engine (or Docker Desktop) for the pipeline lab container.
- For narration: `pip install kokoro-onnx soundfile numpy` plus the Kokoro `kokoro-v1.0.onnx` and `voices-v1.0.bin` files. Pass the folder with `-ModelDir` (the default in the scripts is the path used on the recording machine; change it).
- ffmpeg on PATH. Playwright for Python: `pip install playwright` then `python -m playwright install chromium`.

## Step-by-step lab

### 1. Prepare a dedicated lab folder

Never point a coding agent at your whole home directory or a folder of real customer configs.

```powershell
mkdir $HOME\ag-lab\netops-tools; cd $HOME\ag-lab\netops-tools
git init
# copy samples\ from this repo, then
git add samples; git commit -m "Lab samples"
```

### 2. First project with Neon High

In Antigravity: New Conversation, Create Project, This Computer, Add Folder, pick `netops-tools`, Next. Model: **Gemini 4 Neon, High**. Prompt used:

> Create a small Python 3 tool `syslog_triage.py` that parses Cisco IOS and ASA style syslog lines in `samples/sample.log`, decodes facility and severity from the RFC 3164 PRI value, extracts timestamp, host, the Cisco `%FACILITY-SEVERITY-MNEMONIC` tag and the message, and counts unparsed lines. Print a summary by severity and by host, then an ALERTS section for severity 0-3 plus any LOGIN_FAILED, BPDUGUARD or ERR-DISABLE event. Standard library only, optional `--json` flag, unit tests and a short README. First write an implementation plan, then build it, run the tests, and run the tool on the sample to verify the output.

Observed: plan artifact, 3 files (+584), 16/16 tests.

### 3. Verify yourself, then fix with Neon Low

Open a terminal tab and run:

```powershell
python -m unittest discover -s tests -v
python syslog_triage.py samples\sample.log
```

We noticed the PRI severity disagreed with the Cisco tag severity on some lines. Switch to **Neon Low** (well-defined change) in the same conversation:

> Review note: in this network the Cisco tag severity (the digit in %FACILITY-SEVERITY-MNEMONIC) is authoritative; the PRI severity can be misleading. Make the summary and alerts use the tag severity when a tag exists and fall back to the PRI severity otherwise, and add a MISMATCHES section listing lines where the two differ. Update the tests and the README, then run the tests and the tool again.

Observed: 19/19 tests, ALERTS 11 -> 7, MISMATCHES 10, 3 files +97 -28.

### 4. Review tab and a clean commit

The Review tab's Commit dialog would have included `__pycache__`, so we cancelled it and asked Neon Low:

> Add a .gitignore for Python (pycache, virtual env, build outputs), then stage everything and make a git commit with a clear message. Show me git log and git status when done.

Observed: one retry on `git add`, then commit "Add Cisco syslog triage CLI tool, unit tests, README, and Python .gitignore", working tree clean.

### 5. Orchestrator (Neon) with subagents

New Conversation in `netops-tools`, model picker -> **Orchestrator (Neon)** ("Neon that may offload routine steps to Hydrogen"). Prompt (condensed):

> Extend netops-tools with a config backup auditor. Split it into parallel workstreams and delegate them to subagents: (1) `config_diff.py` compares two IOS backups in `samples/backups` and reports added/removed lines grouped by section (interface, router, line...); (2) `security_audit.py` flags telnet enabled, no service password-encryption, SNMP community public/private, HTTP server on, missing exec-timeout, enable password instead of secret, each with a severity; (3) a `netaudit.py` CLI that combines both and writes an HTML report; (4) unit tests. Stdlib only, do not change existing files, verify everything at the end.

What to watch: the parent thinks for about three minutes, writes **API contracts and file ownership**, then starts four `netops_worker` subagents (Config Diff Developer, Security Audit Developer, NetAudit CLI Developer, Unit Test Developer). Open a subagent and read "Message from Parent Agent". The subagents found and fixed a section-ordering assertion and a `None` vs `int` sort bug themselves. Final: **74 tests OK**, 4 findings on the 11-19 backup (CRITICAL SNMP public RW, HIGH telnet, 2 MEDIUM), HTML report in `reports/`.

Run it yourself:

```powershell
python -m unittest discover -s tests
python netaudit.py samples\backups\edge-rtr1_2026-11-18.cfg samples\backups\edge-rtr1_2026-11-19.cfg
```

### 6. /swarm builds the demo-video pipeline

New Project `demo-pipeline` (empty folder), model **Gemini 4 Neon, Medium**, type `/swarm` and pick the built-in skill. Prompt (condensed):

> Build a reusable narrated demo-video pipeline in this repo, one component per agent, in parallel. A) lab: tiny Flask "NetOps Status" app with a device table and a Run health check button, Dockerfile + compose, published only on 127.0.0.1:8099, started from Windows through WSL. B) Playwright driver that opens the app, waits, clicks the button and writes each step with a timestamp to steps.json. C) ffmpeg screen recorder. D) Kokoro narration with the am_michael voice; say IP as "eye pee" and present-tense "read" as "reed". E) assembly with loudness normalization and a per-minute speech RMS check within 1.5 dB. F) HTML player with speed buttons. Plus run_all.ps1 that ties it together.

The swarm creates a roster (lab, driver, record, tts, assemble, player, integrator, verifier, monitor). Use **Open the Swarm UI** to see the **Board** (posts and @mentions), **Members** (who owns which directory) and **Graph** (who talked to whom, with replay). It finished in about six minutes and the verifier ran component checks, but **nobody ran the pipeline end to end**.

### 7. Run it for real

In the same swarm conversation:

> Now actually run .\run_all.ps1 -SkipDockerDown end to end on this machine. Leave the lab container running so I can browse it. If any step fails, fix the code and re-run until out\demo.mp4 and out\player.html exist, then show me the per-minute RMS result and the step timestamps.

What happened on camera:

1. Run 1 (sandboxed terminal): `Wsl/E_ACCESSDENIED` calling `wsl.exe`.
2. Run 2: Docker build OK, TTS OK, driver OK, then `gdigrab` "Failed to capture image (error 5)" because the agent's session cannot capture the interactive desktop.
3. The coordinator posted "Live run feedback" to `@driver` and `@integrator` on the Board: add a Playwright 1920x1080 video fallback, pace each step from `out/tts/manifest.json`, and fix a PowerShell quoting bug.
4. Run 3: `out/demo.mp4` (41.3 s), `out/player.html`, per-minute speech RMS -15.74 dBFS, spread 0.00 dB, PASS.

Reproduce:

```powershell
cd demo-pipeline
pip install -r requirements.txt
python -m playwright install chromium
.\run_all.ps1 -SkipDockerDown -ModelDir C:\path\to\kokoro
start out\player.html
# when finished
wsl -e bash -lc "cd /mnt/c/path/to/demo-pipeline/lab && docker compose down"
```

### 8. Built-in browser and browser subagent

New Conversation, Neon Medium:

> Use the browser subagent and the built-in browser to test the local NetOps Status app at http://127.0.0.1:8099. Open it, read the device inventory, click Run health check, wait for the Health Check Results, and report every device with its status and health check result in a table. Also tell me if anything looks wrong in the UI. Do not edit any files.

Antigravity asks "Allow executing actions on this URL?"; we picked **allow 127.0.0.1:8099 in this conversation**. Result: PASS 5, WARN 1, no console errors, and one real UI finding (the Loss percentage wraps on narrow cards, fixed by width; suggestion `white-space: nowrap`).

### 9. Rules and skills

Neon Low, prompt (condensed):

> Use the agy-customizations skill. Create workspace customizations for our demo-video conventions: an always-on rule (Kokoro am_michael, say IP as "eye pee" and present-tense read as "reed", never show API keys, secrets, emails or desktop notifications on screen, per-minute speech RMS within 1.5 dB, video titles of 100 characters or fewer) and a reusable skill `make-demo` that runs .\run_all.ps1 -SkipDockerDown then checks the RMS report and the pronunciation in the TTS manifest. Do not run the pipeline now. Show the files and where Antigravity loads them from.

Findings: rules live in `.agents/rules/*.md` (`trigger: always_on`), skills in `.agents/skills/NAME/SKILL.md`. Only the skill's name and description are injected up front; the full file loads on demand. A new skill appears as `/make-demo` only in a **new** conversation. In a rule check the model changed IP to "eye pee" but left "read" alone, which is why the pipeline has a pronunciation self-test: rules guide, tests enforce.

## Orchestrator vs /swarm

| | Orchestrator (Neon) | /swarm |
|---|---|---|
| How you start it | Pick it in the model picker | Type `/swarm` (built-in skill, "Preview & Quota Heavy") |
| Shape | One parent conversation with subagents nested under it | A coordinator plus members, each in its own conversation |
| Coordination | Parent writes API contracts and file ownership, waits for subagents, integrates and reviews | A shared Board with @mentions, a Members list with exclusive directories, a Graph with replay, a dedicated verifier and a stall monitor |
| Best for | One codebase with 3-5 separable pieces | Multi-component systems with different tools per component |
| Observed here | 4 subagents, about 17 minutes, 74 tests, no manual fixes | 9 members, about 6 minutes to build, then a live-run feedback loop to make it actually work |

## Quotas observed

At the end of the session (Google AI Pro): Gemini models **weekly 90%** remaining and **five-hour 67%** remaining; Claude and GPT models and Gemini 4 Argon untouched at 100%. So Neon High/Low/Medium, the Orchestrator run, the 9-member swarm, the live pipeline runs, the browser subagent and the customizations together used about 10% of the weekly and 33% of the five-hour Gemini quota.

## How the course video itself was made

`course-build/` has the scripts used for this video: real continuous screen recordings with ffmpeg `gdigrab`, narration written after recording from what actually happened (`segments.json`), Kokoro `am_michael` TTS (`tts.py`), title cards (`cards.py`), an OCR privacy scan of every recording (`scan.py`) and of the final video (`fscan.py`), the renderer with privacy masks, cuts and speed-ups (`render.py`), and the per-minute RMS check (`check.py`). Long waits were cut and some silent stretches were sped up (at most 1.5x); the narration says when a wait was trimmed. The account name and email in Settings were masked, a desktop toast was blurred, and the Windows folder picker was cut.
