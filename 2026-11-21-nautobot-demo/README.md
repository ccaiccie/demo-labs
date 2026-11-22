# Nautobot 3.2.9 Local NetOps Lab — Comprehensive Review & Hands-On Demo

A self-contained, local Docker Compose lab running **Nautobot 3.2.9** (official container images only) with realistic synthetic NetOps fixtures (RFC 5737 IPv4 prefixes, RFC 6996 private ASNs, `lab.internal` hostnames), an internal Git repository Data Source, idempotent REST API seeding, GraphQL queries, Config Context merging, and Celery Job execution.

Video: [Nautobot 3.2.9 Deep Dive & NetOps Lab: APIs, GraphQL, Git, Jobs vs NetBox](https://youtu.be/7T3CtKCReLY)

---

## 1. What Nautobot Is & Why Network Engineers Use It

**Nautobot** (maintained by Network to Code) is an open-source **Network Source of Truth (NSoT)** and **Network Automation Platform**. Originally forked from NetBox in 2021, Nautobot has evolved into an automation-first platform with its own data model, native GraphQL API, built-in Git-backed Data Sources, first-class Celery Jobs, and an enterprise-focused App ecosystem.

Network engineers use Nautobot to:
- **Centralize authoritative network state**: model hierarchical Locations, Devices, Interfaces, VLANs, IPAM Prefixes/IPs, Circuits, Roles, Statuses, and Custom Fields in one schema-enforced database.
- **Drive automation from Git + APIs**: expose intended state over both REST (`/api/`) and GraphQL (`/api/graphql/`), merge hierarchical Config Contexts (local + Git-backed), and execute Python automation Jobs asynchronously via Celery workers.
- **Validate and audit compliance**: enforce strict status/relationship modeling and run repeatable Python Jobs (such as inventory and IPAM audits) with persistent `JobResult` logs.

> **Why this lab is Nautobot-first:** While NetBox is widely covered as a DCIM/IPAM source of truth, this lab focuses specifically on Nautobot 3.x's automation platform capabilities—hierarchical Locations, GraphQL, Git Repository Data Sources, Config Context merging, and Celery Jobs—built and tested end-to-end on the current stable **Nautobot 3.2.9** release.

---

## 2. Architecture & Exact Container Images

Nautobot is a **Django** web application backed by **PostgreSQL** (or MySQL) for persistent relational state, **Redis** for caching and Celery message brokering, and **Celery** (`celery_worker` + `celery_beat`) for asynchronous Jobs, Git synchronization, and scheduled tasks.

This lab adds a lightweight internal `git-server` container serving a bare Git repository built from `./testdata/git-repo` over internal HTTP so Nautobot can sync a real Git Data Source without external internet access or credentials.

| Service | Image | Role in Lab | Healthcheck |
| --- | --- | --- | --- |
| `nautobot` | `networktocode/nautobot:3.2.9-py3.12` | Django/uWSGI web UI, REST API, GraphQL API | HTTP `GET http://127.0.0.1:8080/health/` |
| `celery_worker` | `networktocode/nautobot:3.2.9-py3.12` | Asynchronous Jobs & Git sync (`--concurrency=2`) | `nautobot-server celery inspect ping -t 5` |
| `celery_beat` | `networktocode/nautobot:3.2.9-py3.12` | Periodic task scheduler for Nautobot Jobs | `nautobot-server health_check` |
| `db` | `postgres:16-alpine` | Primary relational database | `pg_isready` |
| `redis` | `redis:7-alpine` | Cache & Celery broker (`--appendonly yes`) | `redis-cli ping` |
| `git-server` | `python:3.12-alpine` | Local bare Git repo over HTTP for Data Source sync | HTTP `GET .../nautobot-lab-repo.git/info/refs` |
| `volume_init` | `python:3.12-alpine` | One-shot init container setting UID `999:999` on shared volumes | Completes before `nautobot` starts |

Shared Docker named volumes:
- `postgres_data` — PostgreSQL data directory
- `redis_data` — Redis AOF persistence
- `nautobot_git` — Shared Git checkout directory (`/opt/nautobot/git`) mounted into `nautobot`, `celery_worker`, and `celery_beat`
- `nautobot_media` — Shared media storage (`/opt/nautobot/media`)

---

## 3. Ports & Bind Addresses

To keep the lab isolated to the local machine and avoid conflicts with common host ports, only the Nautobot web service is published on loopback:

| Service | Host Binding | Container Port | Notes |
| --- | --- | --- | --- |
| `nautobot` | `127.0.0.1:8081` | `8080/tcp` | Web UI, `/api/`, `/api/docs/`, `/api/graphql/`, `/graphql/`, `/health/` |
| `db` | Internal only | `5432/tcp` | Not published on host (avoids host port `5432`) |
| `redis` | Internal only | `6379/tcp` | Not published on host |
| `git-server` | Internal only | `8000/tcp` | Reached by Nautobot/Celery at `http://git-server:8000/nautobot-lab-repo.git` |
| `celery_worker` / `celery_beat` | Internal only | — | No host ports published |

---

## 4. Short Runbook

### Prerequisites
- Docker Engine with Docker Compose v2 (tested on WSL2 Docker).
- Python 3.10+ on the host to run the fixture seeder and hands-on test suite.

### 1. Configure Environment
Copy `.env.example` to `.env` and fill in local-only placeholder credentials (never commit `.env` to version control):

```bash
cp .env.example .env
```

See `.env.example` for all required variables (`NAUTOBOT_DB_PASSWORD`, `NAUTOBOT_REDIS_PASSWORD`, `NAUTOBOT_SECRET_KEY`, and initial superuser bootstrap variables).

### 2. Start the Lab Stack
```bash
docker compose up -d
docker compose ps
```

Wait until all 6 long-running services (`db`, `redis`, `git-server`, `nautobot`, `celery_worker`, `celery_beat`) report `(healthy)`. Initial database migrations on first boot take roughly 1–2 minutes.

### 3. Set Up Python Test Virtualenv & Seed Fixtures
```powershell
python -m venv tests\.venv
.\tests\.venv\Scripts\pip install -r tests\requirements.txt
.\tests\.venv\Scripts\python.exe testdata\seed_nautobot.py
```

`testdata/seed_nautobot.py` is fully idempotent: running it again reports `0` created and `0` updated across all 22 resource types.

### 4. Run the Full Hands-On Test Suite
```powershell
.\tests\.venv\Scripts\python.exe tests\run_hands_on_tests.py
```

This verifies `/health/`, `/api/status/`, idempotent seeding, `pynautobot` REST API reads and live CRUD cleanup, GraphQL queries, Git Repository Data Source sync, Config Context merging, Git-synced Celery Job execution, and container CLI checks.

### 5. Stop & Clean Up
```bash
# Stop containers while preserving lab data volumes
docker compose down

# Or stop and remove all lab containers and volumes (full reset)
docker compose down -v
```

---

## 5. What We Observed

Every figure and output below was directly observed against the running lab at `http://127.0.0.1:8081` and captured under `evidence/`.

### Runtime Version & Health
- **HTTP Health**: `GET http://127.0.0.1:8081/health/` -> `HTTP 200`
- **API Auth**: Unauthenticated `GET http://127.0.0.1:8081/api/` -> `HTTP 403`; token-authenticated `GET /api/` and `GET /api/status/` -> `HTTP 200`
- **Observed `/api/status/`** (`evidence/api-status.json`):
  - `nautobot-version`: `3.2.9`
  - `django-version`: `5.2.19`
  - `python-version`: `3.12.16`
  - `celery-workers-running`: `1`
  - `installed-apps`: `41` core/dependency apps
  - `nautobot-apps`: `{}` / `plugins`: `{}` (pure official image)
- **Container Status** (`evidence/docker-ps.txt`): All 6 running services (`nautobot`, `celery_worker`, `celery_beat`, `db`, `redis`, `git-server`) reported `Up ... (healthy)`.
- **CLI Checks** (`evidence/nautobot-cli-checks.txt`):
  - `nautobot-server --version` -> `Nautobot version: 3.2.9`, `Django version: 5.2.19`, `Configuration file: /opt/nautobot/nautobot_config.py`
  - `nautobot-server check` -> `System check identified no issues (0 silenced).`
  - `nautobot-server celery inspect ping -t 10` -> `celery@99d037af6f15: OK pong` (`1 node online.`)

### Seeded Inventory & Object Counts (`evidence/pynautobot-rest-output.txt`)
All synthetic lab objects use RFC 5737 documentation subnets (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`), RFC 6996 private ASNs (`64512`, `65001`), and `.lab.internal` FQDNs:

| Resource | Observed Count | Details |
| --- | ---: | --- |
| Location Types | `2` | `Region`, `Site` (nested under `Region`) |
| Locations | `3` | `US-West` -> `dc-west-01`, `branch-sea-01` |
| Manufacturers | `3` | `Arista`, `Cisco`, `Juniper` |
| Platforms | `3` | `arista_eos`, `cisco_ios`, `juniper_junos` |
| Device Types | `3` | `DCS-7050SX3-48YC8`, `C9300-48P`, `EX4300-48T` |
| Devices | `5` | `core-sw-01/02`, `edge-rtr-01` (`dc-west-01`); `acc-sw-01/02` (`branch-sea-01`) |
| Interfaces | `15` | 3 per device (uplinks, interconnects, `Loopback0`) |
| Prefixes | `3` | `192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24` |
| IP Addresses | `8` | All assigned to device interfaces; primary IPv4 set on all 5 devices |
| VLANs | `3` | VLAN `100` (`MGMT-DC-WEST`), `200` (`TRANSIT-CORE`), `300` (`BRANCH-ACCESS`) |
| Circuit Providers | `1` | `LabTel Transit` (ASN `64512`) |
| Circuit Types | `2` | `Dark Fiber`, `DIA` |
| Circuits | `1` | `LAB-CKT-0001` (10G A/Z terminations at `dc-west-01` and `branch-sea-01`) |
| Statuses | `22` | Built-in Nautobot statuses |
| Roles | `23` | Built-in roles + `Core Switch`, `Access Switch`, `Edge Router` |
| Tags | `4` | `lab-core`, `lab-access`, `lab-edge`, `managed-by-nautobot` |
| Custom Fields | `3` | `asset_tag` (text), `maintenance_window` (select, 3 choices), `cost_center` (text) |
| Config Contexts | `2` | Global `lab-base-services` (weight 1000) + Git-backed `dc_west_bgp.json` (weight 1500) |

### REST (`pynautobot`) & GraphQL API Verification
- **`pynautobot 3.2.0` Live CRUD** (`evidence/pynautobot-rest-output.txt`): Created, updated, verified, and cleanly deleted a temporary Tag (`smoke-test-temp`) and a temporary RFC 5737 Prefix (`198.51.100.240/28`).
- **GraphQL API (`POST /api/graphql/`)** (`evidence/graphql-output.json`): A single GraphQL query returned all 5 devices with nested `status`, `role`, `device_type.manufacturer`, `platform`, `location.parent`, `primary_ip4`, `interfaces.ip_addresses`, `tags`, `_custom_field_data` (`cf_asset_tag`, `cf_maintenance_window`), and rendered `config_context`.

### Git Repository Data Source Sync & Config Context Merge (`evidence/git-sync-and-job-output.txt`)
- Registered Git Repository `Lab Git Data Source` pointing to `http://git-server:8000/nautobot-lab-repo.git` (branch `main`, `provided_contents: ["extras.configcontext", "extras.job"]`).
- Sync Job completed with `JobResult` status `SUCCESS` at commit `cee5a116f753af51102863e48c9bc0231ab170b0`, automatically refreshing `dc_west_bgp.json` and registering `LabInventoryAuditJob`.
- Verified rendered `config_context` on `core-sw-01.lab.internal` merged both sources cleanly:
  - From global `lab-base-services`: `domain_name` (`lab.internal`), `dns_servers` (`192.0.2.53`), `ntp_servers` (`192.0.2.123`, `192.0.2.124`), `syslog_servers` (`192.0.2.200`).
  - From Git-backed `dc_west_bgp.json` (scoped to `dc-west-01`, weight 1500): `bgp.local_asn` (`65001`), `bgp.router_id_prefix` (`198.51.100.0/24`), and 3 BGP peers (`core-sw-02.lab.internal`, `edge-rtr-01.lab.internal`, `labtel-transit-gw` ASN `64512`).
  - Meanwhile, branch devices in `branch-sea-01` (such as `acc-sw-01.lab.internal`) received only `lab-base-services` without the `dc-west-01` BGP block.

### Celery Job Execution (`evidence/git-sync-and-job-output.txt`)
- Enabled and executed the Git-synced `Lab Inventory Audit` job (`lab_git_data_source.jobs.lab_inventory_audit.LabInventoryAuditJob`) via REST API.
- Celery worker completed the job with `JobResult` status `SUCCESS` and 9 log entries:
  ```text
  Summary: total=5, compliant=5, missing_primary_ip4=0, non_rfc5737=0
  ```
  All 5 active devices passed (`PASS_RFC5737`).

---

## 6. Key Nautobot Apps (Ecosystem & Honest Lab Status)

This lab intentionally runs the **pure official `networktocode/nautobot:3.2.9-py3.12` image** with **no third-party Nautobot Apps installed** (`PLUGINS = []`, observed `plugins: {}` in `/api/status/`). Installing Apps requires building a custom image or installing Python packages into the Nautobot environment and adding them to `PLUGINS` in `nautobot_config.py`.

Three flagship Network to Code Apps commonly paired with Nautobot in production are:

| Nautobot App | What It Does | PyPI Latest & Compatibility with Nautobot 3.2.9 (Python 3.12) | Installed in This Lab? |
| --- | --- | --- | --- |
| **Nautobot Golden Config** (`nautobot-golden-config`) | Configuration backups, intended config generation (Jinja2 + GraphQL + Config Contexts), compliance diffing, and remediation | `3.1.0` — declares `nautobot>=3.1.0,<4.0.0`, Python `>=3.10,<3.15` (compatible) | **No** (pure official image) |
| **Nautobot Device Onboarding** (`nautobot-device-onboarding`) | Discovers live network devices over SSH/NAPALM/Netmiko/Nornir and populates Nautobot DCIM/IPAM records automatically | `5.6.0` — declares `nautobot>=3.1.0,<4.0.0`, Python `>=3.10,<3.15` (compatible) | **No** (pure official image) |
| **Nautobot SSoT** (`nautobot-ssot`) | Single Source of Truth synchronization framework (DiffSync-based) to sync data between Nautobot and external systems (ServiceNow, Infoblox, ACI, Arista CloudVision, etc.) | `4.8.0` — declares `nautobot>=3.1.0,<4.0.0`, Python `>=3.10,<3.15` (compatible) | **No** (pure official image) |

---

## 7. Fair Review & Nautobot vs. NetBox Comparison

### Strengths Observed in This Lab
- **Automation-native core features**: GraphQL (`/api/graphql/` + interactive GraphiQL at `/graphql/`), Git Repository Data Sources, Config Context merging, and Celery Jobs all work out of the box on the official image without installing plugins.
- **Flexible Location hierarchy**: Replacing rigid Region/Site/Location tiers with user-defined `LocationType` hierarchies (`Region -> Site`) made modeling `US-West -> dc-west-01 / branch-sea-01` clean and consistent across devices, prefixes, VLANs, and circuits.
- **Rich observability & auditability**: Every Git sync and custom Job writes structured logs to persistent `JobResult` records, and `/api/status/` + `/health/` + `nautobot-server check` make health verification straightforward.
- **Strong Python SDK & API docs**: `pynautobot 3.2.0` worked cleanly against Nautobot 3.2.9, and interactive OpenAPI/Swagger documentation is built in at `/api/docs/`.

### Limits & Operational Gotchas Observed in This Lab
- **Celery default concurrency on high-core hosts**: Running `nautobot-server celery worker` without `--concurrency` defaults to spawning one prefork worker per host CPU core. On an 80-core host this consumed over 10 GiB of RAM and stalled worker startup until `--concurrency=2` was added explicitly in `docker-compose.yml`.
- **Nautobot 3.x API filter strictness**: Some REST endpoints enforce strict filter field names (for example, `extras/custom-fields/` rejects `?key=...` with HTTP 400 and expects `?label=...`, and `circuits/circuit-terminations/` filters by `circuit` rather than `circuit_id`). Automation scripts ported from older versions or NetBox need careful testing against the OpenAPI schema.
- **Multi-container footprint & first-boot time**: Running Nautobot properly requires 5 core containers (`nautobot`, `celery_worker`, `celery_beat`, `db`, `redis`) plus shared volume permissions (`UID 999`), and initial Django migrations take 1–2 minutes before `/health/` turns green.
- **App installation requires custom builds**: Flagship features like Golden Config, Device Onboarding, and SSoT are separate Apps rather than built into the base image, so production teams typically maintain a custom Dockerfile extending `networktocode/nautobot`.

### Nautobot vs. NetBox — Architectural & Workflow Comparison

| Dimension | Nautobot 3.2.9 | NetBox (4.x) |
| --- | --- | --- |
| **Primary Focus** | Network Source of Truth **+** Network Automation Platform | Network Source of Truth (DCIM / IPAM) with extensibility |
| **Background Task Engine** | **Celery** (`celery_worker` + `celery_beat` + Redis) | **RQ** (`netbox-worker` + Redis) |
| **Git Data Sources** | Built-in `GitRepository` model syncing Config Contexts, Jobs, Export Templates, GraphQL Queries, and Compliance Rules | Data Sources (Git/S3/Local) for scripts, templates, and config contexts |
| **GraphQL API** | First-class, heavily used by Jobs and Apps (including saved GraphQL queries) | Supported (Strawberry GraphQL) |
| **Location Modeling** | Unified `Location` + customizable `LocationType` hierarchy | Distinct `Region`, `SiteGroup`, `Site`, and `Location` models |
| **Database Support** | PostgreSQL and MySQL | PostgreSQL only |
| **Plugin / App Ecosystem** | Deep Network to Code automation Apps (Golden Config, SSoT, Device Onboarding, ChatOps) | Large community plugin ecosystem focused on DCIM/IPAM extensions |
| **When to Choose** | You want an automation-centric platform with Git-synced Jobs, Celery workflows, SSoT integrations, and Golden Config | You want a streamlined, fast-moving DCIM/IPAM Source of Truth with a simpler worker model and broad community plugins |
