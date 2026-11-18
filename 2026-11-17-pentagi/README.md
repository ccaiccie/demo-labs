# 2026-11-17-pentagi

Hands-on lab for the **PentAGI** demo on the Network Technician channel.

PentAGI (by **VXControl**) is an open-source, self-hosted, multi-agent AI
penetration-testing platform. You describe a target and a goal in plain
language; specialized agents plan the work, run security tools inside an
isolated Kali-based Docker sandbox, keep memory, and write a report.

- Project: https://github.com/vxcontrol/pentagi
- Docs (quick start): https://pentagi.com/docs/getting-started/quickstart/
- License: MIT (open-source edition). Enterprise edition adds extra agents and features.

## Rules of engagement (read first)

PentAGI is an **autonomous offensive-security tool**. Only ever point it at
systems you **own or are explicitly authorized to test**.

This lab is **fully self-contained**: the only target is a **local, deliberately
vulnerable practice app (OWASP Juice Shop)** that you run yourself in Docker on
the same machine. Nothing is scanned on the public internet, and the target is
reachable only inside your own Docker network. Do **not** change the target to any
host you do not own.

## What you need

- Docker Engine 20+ with Docker Compose (this lab was built on WSL2 Docker 29.9.3, x86_64)
- 2 vCPU / 4 GB RAM minimum
- ~30 GB free disk (the Kali worker image alone is ~24 GB once pulled)
- An OpenAI API key (billed usage) for the agents

## 1. Install PentAGI (manual Docker Compose)

```bash
mkdir -p ~/pentagi && cd ~/pentagi
curl -fsSL -o docker-compose.yml https://raw.githubusercontent.com/vxcontrol/pentagi/main/docker-compose.yml
curl -fsSL -o .env.example https://raw.githubusercontent.com/vxcontrol/pentagi/main/.env.example
# compose mounts these provider examples; create them so Docker does not make dirs:
touch example.custom.provider.yml example.ollama.provider.yml example.bedrock.provider.yml
cp .env.example .env
```

Edit `.env` (see `.env.example` in this folder for the keys that matter):

- `OPEN_AI_KEY=` your key (keep it secret; never commit it)
- `COOKIE_SIGNING_SALT=` `openssl rand -hex 16`
- `PENTAGI_POSTGRES_PASSWORD=` `openssl rand -hex 24`
- `DOCKER_DEFAULT_IMAGE_FOR_PENTEST=vxcontrol/kali-linux`
- `DOCKER_NETWORK=pentagi-network`  (so worker containers can reach the local target)

Bring it up:

```bash
docker compose pull
docker pull vxcontrol/kali-linux:latest   # large (~24 GB); this is the sandbox worker
docker compose up -d
docker compose ps
```

The UI is on **https://localhost:8443** (self-signed cert; accept the warning).
Default login **admin@pentagi.com** / **admin** - change the password immediately.

The interactive installer (`sudo ./installer`) is the other supported path and is
what the source video used; manual Compose is used here because it is easier to
reproduce and to document.

## 2. Stand up the local practice target

The included `victim/docker-compose.yml` runs OWASP Juice Shop on the same
`pentagi-network` that PentAGI attaches its workers to, so the worker can reach it
by hostname. It is also published on `127.0.0.1:3100` so you can open it in a
browser. (Host port 3000 is avoided on purpose - it is in use on the build machine.)

```bash
cd victim
docker compose up -d
# verify locally:
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3100/        # 200
# verify a Kali worker on the network can reach it by name:
docker run --rm --network pentagi-network vxcontrol/kali-linux \
  curl -s -o /dev/null -w "%{http_code}\n" http://juiceshop:3000/       # 200
```

The target address to give PentAGI is therefore **http://juiceshop:3000**.

## 3. Run an Automation flow

In the UI: **Flows -> New Flow -> Automation**, pick the OpenAI provider, and set the
target to `http://juiceshop:3000`. A narrow, authorized prompt (combining the
source video's request with the authorization language that produced results):

```text
This is my own, locally hosted, deliberately vulnerable practice app (OWASP Juice Shop)
that I am authorized to test. The target is http://juiceshop:3000 only.
You are authorized to send harmless proof-of-concept payloads and marker-based tests only.
Please test it for OWASP Top 10 vulnerabilities and summarize confirmed findings
with reproduction steps and raw evidence.
```

PentAGI builds a plan, then its agents work in the Kali sandbox (terminal,
Chromium, Python, curl, etc.). Watch the **Terminal, Agents, Searches,
Screenshots,** and **Report** tabs.

### Honest note on results

Automation mode is **conservative**. In the source review, the first runs reported
**no confirmed findings** until the prompt was tightened to explicitly authorize
proof-of-concept tests - and even then some classes (e.g. XXE) were reported but not
proven. Treat the output as a starting point that **needs human validation**; do not
read "nothing confirmed" as "the app is secure." The vendor also recommends
**Assistant** mode to steer the assessment interactively.

## 4. Cleanup

```bash
cd ~/pentagi && docker compose down            # stop PentAGI (keep data)
cd victim && docker compose down               # stop the practice target
# add -v to either to also remove volumes
```

## Links

- PentAGI: https://github.com/vxcontrol/pentagi - docs: https://pentagi.com/docs/getting-started/quickstart/
- OWASP Juice Shop: https://github.com/juice-shop/juice-shop
- Courses: https://learn.techtohire.com - Quizzes: https://quiz.techtohire.com
