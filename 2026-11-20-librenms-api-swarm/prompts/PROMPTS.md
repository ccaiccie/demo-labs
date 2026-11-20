# Prompts Used to Build This Lab

This file records the prompts and follow-up fix instructions executed in order to build, test, verify, and document the `librenms-api` Docker Compose NetOps lab. All local lab defaults use synthetic RFC 5737 addresses and non-sensitive placeholders; no real secrets or tokens are included.

---

## 1. Initial Lab Goal (`/swarm` Request Scope)

Build a reproducible, API-first LibreNMS NetOps lab on Windows + WSL Docker as a follow-on to a basic LibreNMS install, focusing on:

- REST API v0 bulk device onboarding (`POST /api/v0/devices`)
- Multi-subnet SNMPv2c auto-discovery across three internal RFC 5737 Docker networks (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`)
- Automated NetOps alert rule pack loading (`POST /api/v0/rules`)
- Local HTTP webhook alert delivery to an internal `webhook-receiver` container (`http://webhook-receiver:8080/alert`)
- Strict host port isolation: compose project `librenms-api`, LibreNMS web UI published only on `http://127.0.0.1:8012`, no other host ports published, forbidden ports avoided, and `netflow-stack` left untouched
- Grounded documentation, observed evidence outputs, and lab walkthrough text

---

## 2. Docker Compose Stack & Lab Services (`@compose`)

> Research official LibreNMS Docker docs (`librenms/docker`, `librenms/librenms` image, `mariadb`, `redis`, dispatcher/sidecar requirements) and build a reproducible local NetOps Docker Compose lab for Windows + WSL Docker.
>
> Constraints:
> - Compose project name: `librenms-api` (`name: librenms-api` in `docker-compose.yml`).
> - Official images only (`librenms/librenms`, `mariadb:10.11`, `redis:7-alpine`, `alpine:3.20` with `net-snmp`, `python:3.12-alpine`).
> - Publish LibreNMS web UI only on `127.0.0.1:8012` (mapping to container port `8000`). Publish no other host ports.
> - Healthchecks on core services (DB, Redis, LibreNMS, dispatcher, webhook receiver, SNMP agents).
> - Internal Docker networks using RFC 5737 subnets:
>   - `lab_mgmt` (DB, Redis, LibreNMS, dispatcher, `webhook-receiver`)
>   - `lab_core` (`192.0.2.0/24`): LibreNMS (`192.0.2.2`), dispatcher (`192.0.2.3`), `core-rtr-01` (`192.0.2.11`), `core-sw-01` (`192.0.2.12`)
>   - `lab_branch` (`198.51.100.0/24`): LibreNMS (`198.51.100.2`), dispatcher (`198.51.100.3`), `br-rtr-01` (`198.51.100.11`), `br-sw-01` (`198.51.100.12`)
>   - `lab_edge` (`203.0.113.0/24`): LibreNMS (`203.0.113.2`), dispatcher (`203.0.113.3`), `edge-fw-01` (`203.0.113.11`), `edge-ap-01` (`203.0.113.12`)
> - Each SNMP agent runs `snmpd` with distinct `sysName`, `sysDescr`, `sysLocation`, `sysContact` and community `lab-ro-community` (SNMPv2c).
> - Local `webhook-receiver` container on `lab_mgmt` listening on internal port `8080` (`http://webhook-receiver:8080/alert`) that logs incoming alert webhook JSON payloads to stdout and `/tmp/alerts.jsonl` and returns HTTP 200.

---

## 3. Synthetic NetOps Fixtures (`@testdata`)

> Research official LibreNMS REST API v0 schemas (`POST /api/v0/devices`, `POST /api/v0/rules`, alert transport provisioning, and auto-discovery `nets` / SNMP community configuration) and create clean, synthetic lab fixtures under `fixtures/` using RFC 5737 IPs and `*.lab.internal` hostnames only:
> - `fixtures/devices.json`: 4 bulk-add devices (`core-rtr-01`, `core-sw-01`, `br-rtr-01`, `br-sw-01`)
> - `fixtures/discovery.json`: 3 RFC 5737 subnets (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`), SNMPv2c community `lab-ro-community`, and expected edge targets (`edge-fw-01`, `edge-ap-01`)
> - `fixtures/alert-rules.json`: 4 practical NetOps alert rules (`Lab: Device Down`, `Lab: High CPU Utilization`, `Lab: Port Operational Down`, `Lab: Deterministic Webhook Test`)
> - `fixtures/alert-transport.json`: `lab-local-webhook` (`api` transport targeting `http://webhook-receiver:8080/alert`)

---

## 4. End-to-End Automation & Live Testing (`@tests`)

> Write reproducible automation and test scripts under `scripts/` and execute real hands-on tests against the running `librenms-api` Docker Compose stack on Windows + WSL Docker:
> 1. Verify WSL Docker reachability without touching `netflow-stack`.
> 2. Start `docker compose -p librenms-api up -d --build` and wait for healthy containers and `http://127.0.0.1:8012`.
> 3. Bootstrap the LibreNMS admin user (`labadmin`) and provision a Laravel Sanctum API token (redacted as `<REDACTED_TOKEN>` in logs).
> 4. Bulk-add devices from `fixtures/devices.json` via `POST /api/v0/devices` and verify via `GET /api/v0/devices`.
> 5. Configure auto-discovery subnets and SNMPv2c community credentials from `fixtures/discovery.json`, scan `203.0.113.0/24`, and verify `edge-fw-01` and `edge-ap-01` are auto-discovered and polled.
> 6. Load alert rules from `fixtures/alert-rules.json` via `POST /api/v0/rules` and verify via `GET /api/v0/rules`.
> 7. Provision the local webhook transport (`lab-local-webhook`), link it to the lab alert rules via LibreNMS 26.11 alert operations, evaluate alerts, and confirm JSON payloads arrive in `librenms-api-webhook:/tmp/alerts.jsonl`.

---

## 5. Follow-Up Fix Prompt — `snmpd` Duplicate Config Flag (`@tests` -> `@compose`)

During initial stack bring-up, all 6 SNMP agent containers crash-looped with:

```text
/etc/snmp/snmpd.conf: line 11: Error: includeAllDisks already specified.
Error opening specified endpoint "udp:161"
```

Follow-up fix prompt:

> `snmpd -f -Lo -c /etc/snmp/snmpd.conf` loads `/etc/snmp/snmpd.conf` twice (default config path plus `-c`) unless `-C` ("do not read the default configuration files") is passed. Update `configs/snmpd/Dockerfile` to include `-C` (`["snmpd", "-f", "-Lo", "-C", "-c", "/etc/snmp/snmpd.conf"]`) so we can rebuild and re-test.

Resolution: `configs/snmpd/Dockerfile` was updated with `-C`, the stack was rebuilt, and all 11 containers reached `healthy`.

---

## 6. Evidence Collection (`@evidence`)

> Collect real, observed raw command outputs and LibreNMS web UI screenshots from the running `librenms-api` stack and save them under `evidence/` (with any API token redacted as `<REDACTED_TOKEN>`):
> - `evidence/docker-compose-ps.txt`
> - `evidence/api-system.json`
> - `evidence/api-devices.json`
> - `evidence/api-rules.json`
> - `evidence/discovery-config.txt`
> - `evidence/webhook-alerts.jsonl`
> - `evidence/run-all-output.txt`
> - `evidence/screenshots/` (`01-devices.png`, `02-alert-rules.png`, `03-alert-transports.png`, `04-active-alerts.png`) from `http://127.0.0.1:8012`.

---

## 7. Documentation & Walkthrough Text (`@docs`)

> Grounded strictly in the observed results and captured `evidence/` files, write:
> - `README.md` (overview, topology and port map, exact WSL runbook, observed results including the `snmpd -C` fix and LibreNMS 26.11 schema notes, known limits, and links to `evidence/`)
> - `prompts/PROMPTS.md` (ordered record of prompts and follow-up fixes, no secrets)

## 8. Follow-Up Prompt After Manual Verification (new conversation, Gemini 4 Neon Medium)

> ﻿I checked the running librenms-api stack myself and found two problems:
> 1) The two auto-discovered edge devices are named by Docker reverse DNS (librenms-api-edge-ap-01.librenms-api_lab_edge, librenms-api-edge-fw-01.librenms-api_lab_edge) while the API-added devices are named by IP. Make discovered devices consistent (named by IP), fix the lab config/scripts so a fresh run does the same, and rename or re-add the two existing edge devices.
> 2) The webhook receiver keeps growing: 174 then 180 POSTs a minute later for the same 6 open alerts of "Lab: Deterministic Webhook Test". Stop the repeat notifications (rule delay/interval/count or a better test rule) in fixtures and scripts and apply it to the running stack.
> Then prove a real outage end to end: stop container librenms-api-edge-fw-01, poll and run alerts until "Lab: Device Down" (critical) opens for that device and its payload reaches the webhook receiver, start the container again and show the recovery. Only touch the librenms-api project and its containers, never netflow-stack. Update README.md and narration.txt with the observed results and show me the outputs.
