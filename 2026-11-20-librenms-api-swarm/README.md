# LibreNMS API-First NetOps Lab (`librenms-api`)

An API-first LibreNMS NetOps lab built with Docker Compose on Windows + WSL Docker. This lab is a follow-on to a basic LibreNMS install: instead of clicking through the web UI to add hosts and rules one by one, it demonstrates repeatable automation for **REST API v0 bulk device onboarding**, **multi-subnet SNMPv2c auto-discovery**, **alert rule packs via API**, and **local HTTP webhook alert delivery**.

All lab subnets use RFC 5737 documentation ranges (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`) with synthetic `*.lab.internal` hostnames and local-only lab defaults.

---

## Topology & Ports

- **Compose project name**: `librenms-api` (`name: librenms-api` in `docker-compose.yml`)
- **Host port published (only one)**: `http://127.0.0.1:8012` -> `librenms-api-web:8000`
- **Other host ports**: None. All database, Redis, SNMPv2c (`161/udp`), and webhook (`8080/tcp`) traffic stays on internal Docker bridge networks. Existing host stacks (such as `netflow-stack`) and reserved host ports are untouched.

### Services (11 containers, official images)

| Service | Container Name | Image | Internal Networks / IPs | Role |
|---|---|---|---|---|
| `db` | `librenms-api-db` | `mariadb:10.11` | `lab_mgmt` | LibreNMS MariaDB database |
| `redis` | `librenms-api-redis` | `redis:7-alpine` | `lab_mgmt` | Cache, session, and dispatcher coordination |
| `librenms` | `librenms-api-web` | `librenms/librenms:latest` | `lab_mgmt`, `192.0.2.2`, `198.51.100.2`, `203.0.113.2` | LibreNMS web UI (`127.0.0.1:8012`) & REST API v0 |
| `dispatcher` | `librenms-api-dispatcher` | `librenms/librenms:latest` | `lab_mgmt`, `192.0.2.3`, `198.51.100.3`, `203.0.113.3` | LibreNMS sidecar polling/discovery/alerting service (`SIDECAR_DISPATCHER=1`) |
| `webhook-receiver` | `librenms-api-webhook` | `python:3.12-alpine` | `lab_mgmt` (`http://webhook-receiver:8080/alert`) | Local HTTP POST receiver logging JSONL payloads to `/tmp/alerts.jsonl` |
| `core-rtr-01` | `librenms-api-core-rtr-01` | `librenms-api-snmpd:local` (`alpine:3.20` + `net-snmp`) | `lab_core` (`192.0.2.11`) | Bulk-added SNMPv2c agent (`core-rtr-01.lab.internal`) |
| `core-sw-01` | `librenms-api-core-sw-01` | `librenms-api-snmpd:local` (`alpine:3.20` + `net-snmp`) | `lab_core` (`192.0.2.12`) | Bulk-added SNMPv2c agent (`core-sw-01.lab.internal`) |
| `br-rtr-01` | `librenms-api-br-rtr-01` | `librenms-api-snmpd:local` (`alpine:3.20` + `net-snmp`) | `lab_branch` (`198.51.100.11`) | Bulk-added SNMPv2c agent (`br-rtr-01.lab.internal`) |
| `br-sw-01` | `librenms-api-br-sw-01` | `librenms-api-snmpd:local` (`alpine:3.20` + `net-snmp`) | `lab_branch` (`198.51.100.12`) | Bulk-added SNMPv2c agent (`br-sw-01.lab.internal`) |
| `edge-fw-01` | `librenms-api-edge-fw-01` | `librenms-api-snmpd:local` (`alpine:3.20` + `net-snmp`) | `lab_edge` (`203.0.113.11`) | Auto-discovered SNMPv2c agent (`edge-fw-01.lab.internal`) |
| `edge-ap-01` | `librenms-api-edge-ap-01` | `librenms-api-snmpd:local` (`alpine:3.20` + `net-snmp`) | `lab_edge` (`203.0.113.12`) | Auto-discovered SNMPv2c agent (`edge-ap-01.lab.internal`) |

All 6 SNMP agents share the local read-only SNMPv2c community `lab-ro-community`.

---

## Short Runbook / How to Run

Run these commands from PowerShell on Windows (targeting WSL Docker in this repository):

### 1. Start the stack and run the full end-to-end automation

```powershell
wsl -e bash -lc 'cd /mnt/c/Users/superuser/ag-lab/librenms-api-swarm && bash scripts/run-all.sh'
```

`scripts/run-all.sh` runs all 6 stages in order:
1. Validates `docker-compose.yml` and starts all 11 containers (`docker compose -p librenms-api up -d --build`).
2. `scripts/bootstrap-auth.sh`: Waits for `librenms-api-web` to report `healthy`, creates the local admin user `labadmin`, provisions a Laravel Sanctum API token to `/tmp/librenms-api.token` (`0600`), and verifies `GET /api/v0/system`.
3. `scripts/bulk-add-devices.py`: Bulk-adds the 4 core and branch devices from `fixtures/devices.json` via `POST /api/v0/devices` and verifies them via `GET /api/v0/devices`.
4. `scripts/configure-discovery.sh`: Applies `fixtures/discovery.json` (`nets`, `discovery_by_ip`, `normalize_discovered_hostname_to_ip`, `autodiscovery.nets-exclude`, SNMPv2c secret credential), scans `203.0.113.0/24` with `lnms scan:network`, normalizes any Docker reverse-DNS hostnames on scanned devices to their IP via `lnms device:rename`, discovers/polls all devices, and verifies both edge devices are named by IP and up.
5. `scripts/load-alert-rules.py`: Loads the 4 NetOps alert rules from `fixtures/alert-rules.json` via `POST /api/v0/rules` and verifies them via `GET /api/v0/rules`.
6. `scripts/configure-webhook-and-test.sh`: Provisions the `lab-local-webhook` alert transport (`http://webhook-receiver:8080/alert`) and `Lab Local Webhook Operation` (with `problem` and `recovery` segments capped at `escalation_step_from=1..escalation_step_to=1` so open alerts do not spam repeat POSTs), polls `192.0.2.11`, runs `alerts.php`, and verifies JSON alert delivery in `librenms-api-webhook:/tmp/alerts.jsonl`.

### 2. Inspect the UI, stack status, and webhook log

- Open `http://127.0.0.1:8012` in a local browser (sign in with `labadmin` and the local lab password configured in `scripts/bootstrap-auth.sh`).
- Check container health and port bindings:

```powershell
wsl -e bash -lc 'cd /mnt/c/Users/superuser/ag-lab/librenms-api-swarm && docker compose -p librenms-api ps'
```

- Inspect delivered webhook JSON payloads:

```powershell
wsl -e bash -lc 'docker exec librenms-api-webhook tail -n 5 /tmp/alerts.jsonl'
```

### 3. Stop and clean up

Stop containers while keeping volumes:

```powershell
wsl -e bash -lc 'cd /mnt/c/Users/superuser/ag-lab/librenms-api-swarm && docker compose -p librenms-api down'
```

Full reset (removes containers and lab volumes):

```powershell
wsl -e bash -lc 'cd /mnt/c/Users/superuser/ag-lab/librenms-api-swarm && docker compose -p librenms-api down -v'
```

---

## What We Observed

- **Stack health (`evidence/docker-compose-ps.txt`)**: All **11/11** containers reached `(healthy)` with only `127.0.0.1:8012->8000/tcp` exposed on the host.
- **LibreNMS version & API auth (`evidence/api-system.json`)**: `GET /api/v0/system` with `X-Auth-Token: <REDACTED_TOKEN>` returned HTTP 200 (`"status": "ok"`) reporting **LibreNMS `26.11.0`**, PHP `8.4.27`, Python `3.14.10`, MariaDB `10.11.19`, RRDtool `1.10.2`, and Net-SNMP `5.9.5.2`.
- **REST API bulk onboarding (`evidence/api-devices.json`)**: `POST /api/v0/devices` onboarded 4/4 core and branch devices (`core-rtr-01.lab.internal` id=1, `core-sw-01.lab.internal` id=2, `br-rtr-01.lab.internal` id=3, `br-sw-01.lab.internal` id=4).
- **Multi-subnet SNMP auto-discovery & consistent IP naming (`evidence/discovery-config.txt`, `evidence/api-devices.json`)**: `lnms config:set` configured all three RFC 5737 subnets (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`) with `discovery_by_ip=true`. `lnms scan:network 203.0.113.0/24` scanned 254 addresses in `15.3 seconds` and auto-discovered both edge devices. Because LibreNMS 26.11's `AddScannedHost` unconditionally resolves reverse PTR records from Docker's embedded DNS (`librenms-api-edge-fw-01.librenms-api_lab_edge`, `librenms-api-edge-ap-01.librenms-api_lab_edge`), `scripts/configure-discovery.sh` normalizes scanned hostnames to IP via `lnms device:rename`, resulting in all 6 devices consistently named by IP (`192.0.2.11`, `192.0.2.12`, `198.51.100.11`, `198.51.100.12`, `203.0.113.11`, `203.0.113.12`) with `status=1` (up) and active `last_polled` timestamps.
- **Alert rule pack via API (`evidence/api-rules.json`)**: `POST /api/v0/rules` created and verified 4/4 enabled rules (`Lab: Device Down` critical, `Lab: High CPU Utilization` warning, `Lab: Port Operational Down` warning, `Lab: Deterministic Webhook Test` warning).
- **Local webhook alert delivery & repeat-notification cap (`evidence/webhook-alerts.jsonl`, `evidence/outage-recovery-test.txt`)**: Initially, the `problem` segment of `Lab Local Webhook Operation` had `escalation_step_to=null` and `default_operation_step_duration_seconds=60`, causing the 6 open `Lab: Deterministic Webhook Test` alerts to re-POST every 60 seconds. Updating `fixtures/alert-transport.json` and `scripts/configure-webhook-and-test.sh` to cap both `problem` and `recovery` segments at `escalation_step_from=1, escalation_step_to=1` (`default_operation_step_duration_seconds=300`) stopped repeat notifications immediately (verified flat at 246 lines across the `21:47 UTC` dispatcher cycle, and flat at 250 lines for 3+ minutes after recovery).
- **End-to-end real outage & recovery test (`evidence/outage-recovery-test.txt`, `evidence/webhook-alerts.jsonl`)**:
  - **Outage**: Stopping `librenms-api-edge-fw-01` and polling `203.0.113.11` marked device `id=5` down (`status=0`, `status_reason=icmp,snmp`) and opened `Lab: Device Down` (`rule_id=1`, `severity=critical`, `alert_id=7`). `alerts.php` reported `:: Transport api => OK` and delivered the JSON payload (`"rule": "Lab: Device Down"`, `"hostname": "203.0.113.11"`, `"sysName": "edge-fw-01.lab.internal"`, `"severity": "critical"`, `"state": "1"`) to `librenms-api-webhook:/tmp/alerts.jsonl`.
  - **Recovery**: Starting `librenms-api-edge-fw-01` restored SNMP within 1s; polling `203.0.113.11` returned `status=1` and cleared `Lab: Device Down` (`Active 'Lab: Device Down' alerts: 0`). `alerts.php` delivered the recovery JSON payload (`"rule": "Lab: Device Down"`, `"state": "0"`, `"title": "Device 203.0.113.11 recovered from Lab: Device Down"`) to `librenms-api-webhook:/tmp/alerts.jsonl`.

### Real Bugs Caught & Fixed

- **`snmpd` duplicate config load in `configs/snmpd/Dockerfile`**: On first boot, all 6 SNMP agent containers crash-looped with `Error: includeAllDisks already specified` and `Error opening specified endpoint "udp:161"`. Passing `-c /etc/snmp/snmpd.conf` without `-C` caused `snmpd` to load `/etc/snmp/snmpd.conf` twice (default config path plus `-c`). Adding `-C` (`ENTRYPOINT ["snmpd", "-f", "-Lo", "-C", "-c", "/etc/snmp/snmpd.conf"]`) resolved the crash loop immediately.
- **Docker reverse DNS on scanned edge devices**: LibreNMS 26.11's `lnms scan:network` (`App\Jobs\AddScannedHost`) resolves reverse PTR names from Docker's embedded DNS (`*.librenms-api_lab_edge`) even when `discovery_by_ip=true`. Adding an IP-normalization step (`lnms device:rename`) to `scripts/configure-discovery.sh` made all 6 devices consistently named by IP on both existing and fresh runs.
- **Repeat webhook notifications every 60 seconds**: In LibreNMS 26.11, notification repeat count is controlled by `alert_operation_segments.escalation_step_to` rather than `alert_rules.extra.count`. Setting `escalation_step_to=1` on both `problem` and `recovery` segments in `fixtures/alert-transport.json` and `scripts/configure-webhook-and-test.sh` stopped repeat POSTs while enabling one-shot recovery notifications.

### LibreNMS 26.11 Compatibility Details Observed Live

- **Sanctum API tokens**: LibreNMS 26.11 uses Laravel Sanctum (`$user->createToken(...)->plainTextToken`) instead of the legacy `api_tokens` table.
- **Network scanning & SNMP secrets**: `lnms scan:network` replaces the deprecated `snmp-scan.py` script, and SNMPv2c communities are stored in `App\Models\Secret` (`SecretType::SnmpCommunity`) referenced by `snmp.default_credentials`.
- **Alert operations routing**: Delivering alerts to a transport requires wiring `alert_operations`, `alert_operation_segments`, and `alert_operation_transport_map` and linking `alert_rules.alert_operation_id`.

---

## Known Limits

- **Alert transport creation is not in REST API v0**: LibreNMS REST API v0 does not expose a `POST` endpoint for creating alert transports, and `App\Models\AlertTransport` encrypts `transport_config` with Laravel application encryption. `scripts/configure-webhook-and-test.sh` provisions the transport and alert operation via PHP/Eloquent inside `librenms-api-web` rather than raw SQL.
- **Initial admin & Sanctum token bootstrap**: No admin account or API token is pre-seeded by the official `librenms/librenms` image, so `scripts/bootstrap-auth.sh` bootstraps `labadmin` via `lnms user:add` and generates a Sanctum token inside the container.
- **Lightweight SNMP agents**: The 6 simulated network devices run Alpine `net-snmp` (`snmpd`) containers rather than full router/switch operating systems. They respond to real SNMPv2c queries (system MIBs, uptime, CPU/load, disks, interfaces) for polling, discovery, and alerting, but do not run routing protocols or vendor-specific enterprise MIBs.

---

## Evidence Artifacts

### Raw Observed Outputs

- [`evidence/docker-compose-ps.txt`](evidence/docker-compose-ps.txt) — All 11 healthy containers and single `127.0.0.1:8012->8000/tcp` host binding
- [`evidence/api-system.json`](evidence/api-system.json) — `GET /api/v0/system` response (`LibreNMS 26.11.0`)
- [`evidence/api-devices.json`](evidence/api-devices.json) — `GET /api/v0/devices` response with all 6 polled devices (4 bulk-added + 2 auto-discovered)
- [`evidence/api-rules.json`](evidence/api-rules.json) — `GET /api/v0/rules` response with all 4 `Lab:` alert rules
- [`evidence/discovery-config.txt`](evidence/discovery-config.txt) — `lnms config:get nets`, `discovery_by_ip`, and `lnms scan:network 203.0.113.0/24` output
- [`evidence/webhook-alerts.jsonl`](evidence/webhook-alerts.jsonl) — Captured JSONL webhook alert payloads from `librenms-api-webhook:/tmp/alerts.jsonl` (including critical `Lab: Device Down` alert and recovery)
- [`evidence/outage-recovery-test.txt`](evidence/outage-recovery-test.txt) — Observed end-to-end outage (`docker stop librenms-api-edge-fw-01`) and recovery (`docker start librenms-api-edge-fw-01`) outputs and webhook stability checks
- [`evidence/run-all-output.txt`](evidence/run-all-output.txt) — Full redacted output of `bash scripts/run-all.sh` (`EXIT_CODE=0`)

### LibreNMS Web UI Screenshots (`http://127.0.0.1:8012`)

- [`evidence/screenshots/01-devices.png`](evidence/screenshots/01-devices.png) — Devices list showing all 6 lab devices up
- [`evidence/screenshots/02-alert-rules.png`](evidence/screenshots/02-alert-rules.png) — Alert Rules showing all 4 enabled `Lab:` rules mapped to `lab-local-webhook`
- [`evidence/screenshots/03-alert-transports.png`](evidence/screenshots/03-alert-transports.png) — Alert Transports showing `lab-local-webhook` (`POST http://webhook-receiver:8080/alert`)
- [`evidence/screenshots/04-active-alerts.png`](evidence/screenshots/04-active-alerts.png) — Active Alerts showing the 6 deterministic webhook test alerts across all 6 devices
