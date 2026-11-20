# Google Antigravity agents and /swarm build a NetOps incident bot

Hands-on lab from the video: Google Antigravity 2.33 with Gemini 4 Neon builds a small syslog-driven incident bot for network engineers, using a workspace rule and skill, the Orchestrator with subagents, `/swarm`, and the browser subagent. A real bug (a dropped Cisco config-change line) is found and fixed.

What the bot does:

- Listens for syslog over UDP (Cisco IOS and FortiGate formats) on `127.0.0.1:5515`.
- Parses each line into a normalized event and correlates events into incidents:
  - `INTERFACE_FLAP` (medium): 3 or more up/down changes of one interface within 120 s
  - `BGP_NEIGHBOR_DOWN` (critical): opens on neighbor Down, resolves automatically on Up
  - `AUTH_BRUTE_FORCE` (high): 5 or more failed logins from one source IP within 60 s, across vendors
  - `CONFIG_CHANGE` (low): `%SYS-5-CONFIG_I`, one incident per host (added by the bug fix)
- Stores events and incidents in SQLite (Docker named volume).
- Serves a REST API and a dashboard on `http://127.0.0.1:8097`.

Python 3.12 standard library only. Sample data uses documentation IP ranges (RFC 5737) and made-up hostnames. Everything binds to 127.0.0.1.

## Folder contents

| Path | What it is |
|------|------------|
| `netops-incident-bot/` | The project as built in the video (final state, after the fix) |
| `netops-incident-bot/.agents/rules/netops-lab.md` | Always-on workspace rule (ports, bindings, stdlib only, tests, no secrets, RFC 5737 data) |
| `netops-incident-bot/.agents/skills/replay-check/SKILL.md` | Reusable skill: tests, Docker check, replay, query the API |
| `netops-incident-bot/incidentbot/` | `models.py`, `parser.py`, `correlator.py`, `store.py`, `server.py`, `web/` |
| `netops-incident-bot/samples/` | `cisco_edge.log` and `fortigate.log` (20 lines total) |
| `netops-incident-bot/tools/replay.py` | UDP syslog replayer |
| `netops-incident-bot/tests/` | 104 unittest tests |
| `netops-incident-bot/Dockerfile`, `docker-compose.yml` | Container, published on 127.0.0.1:5515/udp and 127.0.0.1:8097 |
| `prompts/PROMPTS.md` | The six prompts used, in order |

## Run it

Requirements: Python 3.12 and Docker (Docker Desktop with WSL 2 on Windows works). Ports 5515/udp and 8097 must be free.

```bash
cd netops-incident-bot

# 1. unit tests (expect: Ran 104 tests ... OK)
python -m unittest discover

# 2. build and start the container
docker compose up -d --build
docker compose ps            # wait for (healthy)

# 3. replay the sample logs
python tools/replay.py samples/cisco_edge.log samples/fortigate.log
# Replayed 20 events from 2 file(s) to 127.0.0.1:5515

# 4. check the API
curl -s http://127.0.0.1:8097/api/health
# {"status": "ok", "events_count": 20, "open_incidents": 4}
curl -s "http://127.0.0.1:8097/api/incidents?status=open"
```

Then open http://127.0.0.1:8097 for the dashboard (severity cards filter the table, rows open a detail view with the correlated events and a Resolve button).

On Windows PowerShell, from the project folder, the video used `wsl -e bash -lc 'docker compose up -d --build && docker compose ps'` and:

```powershell
(irm 'http://127.0.0.1:8097/api/events?limit=50').events | Group-Object vendor,kind | Format-Table Count,Name -AutoSize
(irm 'http://127.0.0.1:8097/api/incidents').incidents | Format-Table type,severity,host,count,status -AutoSize
```

API endpoints: `GET /api/health`, `GET /api/incidents[?status=open]`, `GET /api/incidents/{id}` (with events), `GET /api/events?limit=50`, `POST /api/incidents/{id}/resolve`.

Reset to an empty database: `docker compose down -v`. Stop: `docker compose down`.

## Reproduce the build in Antigravity

1. Create an empty folder, `git init`, and open it as a project in Antigravity.
2. Prompt 1 (Neon Low): creates the `.agents` rule and the `replay-check` skill.
3. Prompt 2 (Orchestrator, Neon): the parent writes `models.py`, then three subagents (parser, correlator, SQLite store) work in parallel with exclusive file ownership; 64 tests.
4. Commit, then prompt 3 with `/swarm` (Neon Medium): service, web, docker and replayer members plus a verifier; watch the Swarm UI (Board, Members, Graph); 101 tests.
5. Commit, run Docker yourself, replay the samples. In the video: 20 lines sent, 19 events stored. The `%SYS-5-CONFIG_I` line was dropped.
6. Prompt 4: the browser subagent tests the dashboard (allow `127.0.0.1:8097` for this conversation only).
7. Prompt 5 (Neon Medium): fix the parser and add a `CONFIG_CHANGE` incident; Review the diff; 104 tests.
8. `docker compose down -v && docker compose up -d --build`, replay: 20 events, 4 open incidents, `CONFIG_CHANGE` low on lab-edge-rtr-01.
9. Prompt 6 in a new conversation: `/replay-check`. The agent asks permission before replaying into the running server.

## Notes from the run

- The agent's own shell could not reach the Docker Desktop named pipe (`docker compose ps` failed there), so Docker commands were run from the terminal tab by hand.
- Replays are not deduplicated at the event level: replaying twice gives 40 events, while incidents aggregate (counts double, no duplicate incidents).
- UI issues reported by the browser subagent (backlog): no resolved-incidents view or undo, no confirmation after Resolve, mixed timestamp formats, no view of uncorrelated events, no deep links, subtle active-filter state.
