# Batfish Network CI/CD Pre-Merge Validation Lab

This repository is a self-contained local network CI/CD lab using [Batfish](https://www.batfish.org/) to validate Cisco IOS-style router configurations before changes are merged to `main`.

## What Batfish Is

[Batfish](https://www.batfish.org/) is an open-source offline network configuration analysis engine. Given a snapshot of device configuration files, Batfish parses the configs, builds a mathematical model of the control plane (OSPF, BGP, static routing) and data plane (FIBs, ACLs, packet forwarding), and answers programmatic queries through `pybatfish` — without booting virtual routers or touching production hardware.

In a Git-based network workflow, Batfish acts as a pre-merge gate: every branch is validated against automated `pytest` assertions for clean parsing, undefined references, BGP session compatibility and establishment, ACL policy enforcement, and end-to-end reachability before merging.

## Lab Topology

The snapshot in `snapshots/lab/configs/` defines four Cisco IOS-style (`version 15.2`) routers using RFC 5737 documentation prefixes (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`), RFC 1918 transit links (`10.10.x.x/30`), and private ASNs (`65100`, `65200`, `65300`).

```text
  Branch LAN                                                                     Server LAN
192.0.2.0/24                                                                   203.0.113.0/24
     | Gi0/0 (.1)                                                                   | Gi0/1 (.1)
+------------+  10.10.12.0/30  +-----------+  10.10.23.0/30  +-----------+  10.10.34.0/30  +----------+
| branch-rtr |-----------------| core-rtr1 |-----------------| core-rtr2 |-----------------| edge-rtr |
|  AS 65100  | Gi0/1     Gi0/0 |  AS 65200 | Gi0/1     Gi0/0 |  AS 65200 | Gi0/1     Gi0/0 | AS 65300 |
| Lo0: .100.1|     eBGP        | Lo0:.100.2| OSPF 1 area 0   | Lo0:.100.3|     eBGP   [IN] |Lo0:.100.4|
+------------+                 +-----------+  + iBGP (Lo0)   +-----------+          EDGE_IN +----------+
```

| Router | ASN | Loopback0 | Interfaces | Routing & Policy |
| --- | --- | --- | --- | --- |
| `branch-rtr` | `65100` | `198.51.100.1/32` | `Gi0/0` `192.0.2.1/24` (Branch LAN), `Gi0/1` `10.10.12.1/30` | eBGP to `10.10.12.2` (AS `65200`); advertises `192.0.2.0/24` and `198.51.100.1/32` |
| `core-rtr1` | `65200` | `198.51.100.2/32` | `Gi0/0` `10.10.12.2/30`, `Gi0/1` `10.10.23.1/30` | OSPF 1 area 0 (`198.51.100.2/32`, `10.10.23.0/30`); eBGP to `10.10.12.1` (AS `65100`); iBGP to `198.51.100.3` (`update-source Loopback0`, `next-hop-self`) |
| `core-rtr2` | `65200` | `198.51.100.3/32` | `Gi0/0` `10.10.23.2/30`, `Gi0/1` `10.10.34.1/30` | OSPF 1 area 0 (`198.51.100.3/32`, `10.10.23.0/30`); iBGP to `198.51.100.2` (`update-source Loopback0`, `next-hop-self`); eBGP to `10.10.34.2` (AS `65300`) |
| `edge-rtr` | `65300` | `198.51.100.4/32` | `Gi0/0` `10.10.34.2/30` (`EDGE_IN` inbound), `Gi0/1` `203.0.113.1/24` (Server LAN) | eBGP to `10.10.34.1` (AS `65200`); advertises `203.0.113.0/24` and `198.51.100.4/32` |

### `EDGE_IN` Extended ACL (`edge-rtr`, inbound on `GigabitEthernet0/0`)

- Permits BGP TCP `179` in both directions on `10.10.34.0/30`.
- Permits HTTPS TCP `443` from `192.0.2.0/24` to `203.0.113.0/24`.
- Permits ICMP from `192.0.2.0/24` to `203.0.113.0/24`.
- Explicitly denies Telnet TCP `23` from `192.0.2.0/24` to `203.0.113.0/24`.
- Permits metrics TCP `8443` from `192.0.2.0/24` to `203.0.113.0/24` (added on `feat/allow-metrics-port` and merged to `main`).
- Ends with explicit `deny ip any any`.

## Ports & Runbook

`docker-compose.yml` runs `batfish/allinone:latest` as container `batfish-lab` with ports bound strictly to loopback:

- `127.0.0.1:9996` — Batfish v2 REST API (used by the Docker healthcheck at `http://127.0.0.1:9996/v2/version`).
- `127.0.0.1:9997` — Batfish coordinator/work port.
- Jupyter port `8888` is **not** published.

### Start Batfish

From WSL (`Ubuntu-24.04`) in the repository directory:

```bash
docker compose up -d
```

### Check Container Health and API Version

```bash
docker ps --filter name=batfish-lab
curl -s http://127.0.0.1:9996/v2/version
```

The healthcheck probes `http://127.0.0.1:9996/v2/version` every 10 seconds until it returns HTTP `200` and Docker reports `(healthy)`.

### Create Python Virtual Environment and Run the Pipeline

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
bash ci/run_pipeline.sh
```

`ci/run_pipeline.sh` uses `.venv/bin/pytest` automatically when `.venv` exists (falling back to `pytest` on `PATH`). You can override `BATFISH_HOST` (default `127.0.0.1`) or `SNAPSHOT_DIR` (default `snapshots/lab`) via environment variables.

### Stop Batfish

```bash
docker compose down
```

## Pre-Merge CI Pipeline Flow

1. **GitHub Actions workflow (`.github/workflows/batfish.yml`)**:
   - Triggers on `push` and `pull_request` targeting `main`.
   - Starts `batfish/allinone:latest` as a service container exposing ports `9996` and `9997`.
   - Sets up Python `3.11`, installs `requirements.txt` (`pybatfish`, `pytest`), waits up to 60 seconds for TCP `9997` and HTTP `200` on `127.0.0.1:9996/v2/version`, and runs `bash ci/run_pipeline.sh`.
2. **Local runner (`ci/run_pipeline.sh`)**:
   - Mirrors the workflow steps locally: verifies TCP reachability on `9996` and `9997`, confirms HTTP `200` on `/v2/version`, executes `pytest -v --tb=short tests/test_network.py`, prints `=== PIPELINE RESULT: PASS ===` or `FAIL`, and exits with pytest's return code.
3. **Validation checks (`tests/test_network.py`)**:
   - `test_no_parse_warnings_or_init_issues` — queries `fileParseStatus` (all files `PASSED`) and `initIssues` (empty).
   - `test_no_undefined_references` — queries `undefinedReferences` (empty).
   - `test_bgp_sessions_compatible_and_established` — queries `bgpSessionCompatibility` (6 rows, all `UNIQUE_MATCH`) and `bgpSessionStatus` (6 rows, all `ESTABLISHED`).
   - `test_edge_acl_permits_https_and_denies_telnet` — runs `testFilters` on sample flows (`192.0.2.50 -> 203.0.113.10` TCP `443` `PERMIT` and TCP `23` `DENY`) and exhaustive `searchFilters` across `192.0.2.0/24 -> 203.0.113.0/24` on `edge-rtr` `EDGE_IN`.
   - `test_branch_to_server_reachability_and_traceroute` — runs `traceroute` (`192.0.2.50 -> 203.0.113.10:443`) and `reachability` (`actions="FAILURE"` across `203.0.113.0/24`, `actions="SUCCESS"` across `203.0.113.1-203.0.113.254`) starting at `branch-rtr[GigabitEthernet0/0]`.

Reusable unified diff patches for all four lab scenarios are stored under `snapshots/changes/`.

## What We Observed

All eight live pipeline runs were executed against `batfish/allinone:latest` (`2026.08.27.3685`) with Python `3.12.3` and `pytest 9.2.0`. Raw command outputs are stored under `evidence/`.

| # | Evidence File | Branch & Commit | Change Tested | Exit | Pytest Result | Observed Detail |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `evidence/01-baseline-pass.txt` | `main` (`1a144e0`) | Baseline 4-router snapshot | `0` | 5 passed in `13.96s` | Clean parse, 6/6 BGP established, `EDGE_IN` and reachability pass |
| 2 | `evidence/02-good-change-pass.txt` | `feat/allow-metrics-port` (`9623f15`) | Add `permit tcp ... eq 8443` to `EDGE_IN` on `edge-rtr.cfg` | `0` | 5 passed in `13.71s` | Good change passes all checks; merged to `main` (`1a7632a`) |
| 3 | `evidence/03-bad-acl-fail.txt` | `change/acl-block-https` (`d7a04c3`) | Change HTTPS `443` rule in `EDGE_IN` from `permit` to `deny` | `1` | 2 failed, 3 passed in `20.38s` | `testFilters` reports `DENY` on `edge-rtr` `EDGE_IN`; `traceroute` reports `disposition=DENIED_IN` at `edge-rtr` |
| 4 | `evidence/04-bad-acl-fix-pass.txt` | `change/acl-block-https` (`c0119ed`) | Restore HTTPS `443` `permit` in `EDGE_IN` | `0` | 5 passed in `14.07s` | All checks pass; merged to `main` (`369f36e`) |
| 5 | `evidence/05-bad-bgp-fail.txt` | `change/bgp-peer-as-mismatch` (`9d7717f`) | Change `core-rtr1` neighbor `10.10.12.1` `remote-as` from `65100` to `65199` | `1` | 2 failed, 3 passed in `20.28s` | `bgpSessionCompatibility` reports `HALF_OPEN` on `branch-rtr` and `core-rtr1`; `traceroute` reports `disposition=NO_ROUTE` at `branch-rtr` |
| 6 | `evidence/06-bad-bgp-fix-pass.txt` | `change/bgp-peer-as-mismatch` (`6423176`) | Restore `remote-as 65100` on `core-rtr1.cfg` | `0` | 5 passed in `13.05s` | All checks pass; merged to `main` (`499359d`) |
| 7 | `evidence/07-bad-route-fail.txt` | `change/missing-server-route` (`a236b3b`) | Remove `network 203.0.113.0 mask 255.255.255.0` from `edge-rtr.cfg` | `1` | 1 failed, 4 passed in `20.88s` | Parse, BGP, and ACL checks still pass, but `traceroute` catches `disposition=NO_ROUTE` at `branch-rtr` |
| 8 | `evidence/08-bad-route-fix-pass.txt` | `change/missing-server-route` (`fe6352f`) | Restore `network 203.0.113.0 mask 255.255.255.0` on `edge-rtr.cfg` | `0` | 5 passed in `13.28s` | All checks pass; merged to `main` (`b86d1ba`) |

### Preserved Git Branch History (`evidence/git-log-graph.txt`)

```text
*   b86d1ba (HEAD -> main) Merge branch 'change/missing-server-route': restore server subnet route
|\
| * fe6352f (change/missing-server-route) fix(bgp): restore 203.0.113.0/24 network advertisement on edge-rtr
| * a236b3b change(bgp): drop 203.0.113.0/24 advertisement on edge-rtr
|/
*   499359d Merge branch 'change/bgp-peer-as-mismatch': restore core-rtr1 BGP peer AS
|\
| * 6423176 (change/bgp-peer-as-mismatch) fix(bgp): restore remote-as 65100 for branch-rtr on core-rtr1
| * 9d7717f change(bgp): set mismatched remote-as 65199 on core-rtr1
|/
*   369f36e Merge branch 'change/acl-block-https': restore EDGE_IN HTTPS permit
|\
| * c0119ed (change/acl-block-https) fix(acl): restore HTTPS 443 permit in EDGE_IN
| * d7a04c3 change(acl): block HTTPS 443 in EDGE_IN
|/
*   1a7632a Merge branch 'feat/allow-metrics-port': allow metrics TCP 8443
|\
| * 9623f15 (feat/allow-metrics-port) feat(acl): permit TCP 8443 metrics from branch to server subnet
|/
* 1a144e0 feat: add Batfish compose lab, baseline 4-router configs, and CI pipeline
* 16205ae chore: initial .gitignore
```

The raw evidence logs were then committed on `main` (`3cb1c62`).

## Known Limits

- **Static configuration modeling vs. live forwarding**: Batfish models control-plane and data-plane behavior strictly from configuration files. It does not detect hardware or ASIC bugs, transceiver/physical-layer failures, runtime memory exhaustion, or dynamic routing state injected by external peers not modeled in the snapshot.
- **Port `9996` vs. port `9997` behavior**: In `batfish/allinone:latest` (`2026.08.27.3685`), the HTTP v2 REST API (`/v2/version`) is served on port `9996`, while port `9997` does not serve HTTP inside the container. Accordingly, the Docker healthcheck probes `http://127.0.0.1:9996/v2/version`, while `ci/run_pipeline.sh` checks TCP reachability on both `9996` and `9997` plus HTTP `200` on `9996`.
- **Subnet `.0` and `.255` dispositions**: Batfish classifies traffic to subnet network and broadcast addresses (`.0` and `.255`, such as `203.0.113.0` and `203.0.113.255`) as `EXITS_NETWORK` rather than `DELIVERED_TO_SUBNET`. For that reason, `tests/test_network.py` checks `actions="SUCCESS"` against usable host addresses `203.0.113.1-203.0.113.254` while checking `actions="FAILURE"` across the full `203.0.113.0/24` prefix.

## Ad-hoc Questions with `ci/explore.py`

`ci/explore.py` is a small helper for diagnosing a failing pipeline run. It loads the same snapshot and prints one Batfish answer as a table:

```bash
.venv/bin/python ci/explore.py nodes                               # nodeProperties
.venv/bin/python ci/explore.py edges                               # layer3Edges
.venv/bin/python ci/explore.py bgp                                 # bgpSessionCompatibility
.venv/bin/python ci/explore.py routes 203.0.113.0/24               # routes for one prefix
.venv/bin/python ci/explore.py acl 443                             # testFilters on edge-rtr EDGE_IN
.venv/bin/python ci/explore.py trace 192.0.2.50 203.0.113.10 443   # traceroute hop by hop
```

Observed in the walkthrough (replaying the four patches from `snapshots/changes/` on fresh branches):

- Baseline, good change and every fix: `5 passed`, `=== PIPELINE RESULT: PASS ===`.
- `02-bad-acl-block-https.patch`: 2 failed, 3 passed; `acl 443` returned `DENY` on `deny tcp 192.0.2.0 0.0.0.255 203.0.113.0 0.0.0.255 eq 443`; traceroute `DENIED_IN` after `branch-rtr -> core-rtr1 -> core-rtr2 -> edge-rtr`.
- `03-bad-bgp-peer-as.patch`: 2 failed, 3 passed; `bgp` showed `HALF_OPEN` for branch-rtr/core-rtr1 (remote AS `65199`); traceroute `NO_ROUTE` at `branch-rtr`.
- `04-bad-missing-route.patch`: 1 failed, 4 passed; `routes 203.0.113.0/24` returned only the connected route on `edge-rtr`; traceroute `NO_ROUTE` at `branch-rtr`.
