# Google Antigravity 2.33 + Gemini 4 Neon: agents, subagents, Orchestrator and /swarm

Dated lab folder for the Network Technician channel: `2026-11-19-antigravity-agents-swarm`.

Video: coming soon.

This is a long, hands-on course (about 85 minutes) done live on a Windows 11 workstation with **Google Antigravity 2.33.0** signed in to a Google AI Pro account. Everything on screen really happened: the prompts, the waiting, the failures and the fixes. It covers:

- First launch, onboarding and the interface (conversations, projects, Automations, Customizations)
- Settings: permissions, models and usage, browser, conversations and the customization token budget
- Models and thinking levels: Gemini 4 Neon Low / Medium / High / Extra, and **Orchestrator (Neon)**
- Project 1: a Cisco syslog triage tool built with Neon High, verified in the terminal, then fixed with Neon Low
- The Review tab, a `.gitignore` and a clean commit made by the agent
- **Orchestrator with four parallel subagents** building a config-backup auditor (diff + security audit + HTML report + tests, 74 tests pass)
- The built-in browser and the browser subagent (with the URL permission prompt)
- Project rules, reusable skills, Automations and MCP
- What the whole session actually used from the weekly and five-hour quota

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
| `netops-tools/reports/` | The HTML report generated during the session |

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
| 1:01:11 | Built-in browser and browser subagent |
| 1:07:08 | Project rules, reusable skills, Automations, and MCP |
| 1:17:18 | What the session actually used: quotas |
| 1:24:42 | Outro |

## Requirements to reproduce

- Windows 10/11 with Google Antigravity 2.x installed (user install) and a Google account. Free quota is enough for the small tasks; `/swarm` is marked "Preview & Quota Heavy".
- Python 3.11+ on Windows (`python` on PATH), Git for Windows.

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

### 6. Built-in browser and browser subagent

New Conversation, Neon Medium. Ask the agent to use the browser subagent and the built-in browser to test a small local web app on `127.0.0.1`: open it, read what is on the page, click a button, wait for the results, report them in a table and say if anything looks wrong in the UI, without editing any files.

Antigravity asks "Allow executing actions on this URL?"; we allowed only that local URL, only in this conversation. The subagent drove the page, reported every result, found no console errors and pointed out one real UI issue (a value wrapping on narrow cards) with a CSS suggestion (`white-space: nowrap`).

### 7. Rules and skills

Neon Low, using the built-in `agy-customizations` skill: create an always-on workspace rule for the project's conventions (for example: never show API keys, secrets or emails in output) and a reusable skill, then show the files and where Antigravity loads them from.

Findings: rules live in `.agents/rules/*.md` (`trigger: always_on`), skills in `.agents/skills/NAME/SKILL.md`. Only the skill's name and description are injected up front; the full file loads on demand. A new skill appears as `/NAME` only in a **new** conversation. In a rule check the model followed one convention and missed another, so back important conventions with tests: rules guide, tests enforce.

## Orchestrator vs /swarm

| | Orchestrator (Neon) | /swarm |
|---|---|---|
| How you start it | Pick it in the model picker | Type `/swarm` (built-in skill, "Preview & Quota Heavy") |
| Shape | One parent conversation with subagents nested under it | A coordinator plus members, each in its own conversation |
| Coordination | Parent writes API contracts and file ownership, waits for subagents, integrates and reviews | A shared Board with @mentions, a Members list with exclusive directories, a Graph with replay, a dedicated verifier and a stall monitor |
| Best for | One codebase with 3-5 separable pieces | Multi-component systems with different tools per component |
| Observed here | 4 subagents, about 17 minutes, 74 tests, no manual fixes | 9 members with a verifier and a stall monitor, about 6 minutes for a multi-component build |

## Quotas observed

At the end of the session (Google AI Pro): Gemini models **weekly 90%** remaining and **five-hour 67%** remaining; Claude and GPT models and Gemini 4 Argon untouched at 100%. So Neon High/Low/Medium, the Orchestrator run, the 9-member swarm, the browser subagent and the customizations together used about 10% of the weekly and 33% of the five-hour Gemini quota.
