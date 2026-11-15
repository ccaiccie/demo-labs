# Grafana network-monitoring lab

Local Docker Compose lab used in the walkthrough: Grafana OSS, Prometheus, node_exporter, and blackbox_exporter. This is a lab on your machine, not a production install.

Video: [Grafana and Prometheus Network Monitoring Explained Step by Step](https://youtu.be/5CA2YiSQ_68)

Lab folder: https://github.com/ccaiccie/demo-labs/tree/main/2026-11-15-grafana-network-monitoring

## What you need

- Docker Engine and Docker Compose on Linux, or on Windows inside WSL (for example Ubuntu 24.04).
- Official Linux images:
  - `grafana/grafana-oss` (this walkthrough used 13.0.2)
  - `prom/prometheus` (v3.16.0)
  - `prom/node-exporter` (v1.12.1)
  - `prom/blackbox-exporter` (v0.29.1)

ICMP probes need `cap_add: NET_RAW` on blackbox_exporter, which is already in `docker-compose.yml`.

## Run it (Linux or WSL)

```bash
git clone https://github.com/ccaiccie/demo-labs.git
cd demo-labs/2026-11-15-grafana-network-monitoring
docker compose up -d
```

On Windows with WSL2, clone or copy this folder to a path the Linux Docker engine can see (a Windows profile folder is visible as `/mnt/c/...`). From Windows you can also drive the same commands with:

```bat
wsl -e bash -lc "cd /mnt/c/path/to/demo-labs/2026-11-15-grafana-network-monitoring && docker compose up -d"
```

Stop only this stack (it will not stop other Compose projects):

```bash
docker compose down
```

## Ports and login

Grafana is published on **host port 3001** (`3001:3000`). Port 3000 is often already in use. Change the left-hand port in `docker-compose.yml` if you want a different host port.

On WSL2, the ports are published on `0.0.0.0` so Windows localhost forwarding can work. From Windows, open:

- Grafana: http://127.0.0.1:3001
- Prometheus: http://127.0.0.1:9090
- node_exporter: http://127.0.0.1:9100
- blackbox_exporter: http://127.0.0.1:9115

Use `127.0.0.1`, not `localhost`, if `localhost` resolves to IPv6 and the page times out. If Windows does not forward WSL2 ports, use the WSL address from `wsl hostname -I`.

Login (local lab only): **admin** / **labpass**. Change that password if you expose the port beyond your machine.

Grafana starts in the **light** theme (`GF_USERS_DEFAULT_THEME=light` in the compose file) so the UI is easier to read in the walkthrough. You can switch it under Preferences after login.

Inside Docker, the Prometheus data source URL is `http://prometheus:9090` (the Compose service name). Do not use `localhost` inside the Grafana container.

## node_exporter on WSL

The common recipe that bind-mounts the host root as `/host` with `rslave` failed on WSL with: `path / is mounted on / but it is not a shared or slave mount`. This compose file mounts `/proc` and `/sys` instead, and starts node_exporter with `--path.procfs` / `--path.sysfs` and `pid: host`.

On the WSL host used in the walkthrough, `eth0` / `eth1` / `eth2` were down. The dashboard filters `device=~"eth[0-9]+"`. Adjust the filter if your interface names differ (for example `ens*`, `eth3`).

## Dashboard

Import `dashboard-network-lab.json` (Dashboards → Import). Name: **Network monitoring lab**, uid `netmon-lab`. The file has a `${DS_PROMETHEUS}` input — you must map that dropdown to your Prometheus data source before Import, or Grafana shows **A data source is required**. You can also import through the Grafana API and pass the data source uid.

Panels: probe success, ICMP latency, HTTP latency and status, a five-minute failure ratio `1 - avg_over_time(probe_success[5m])`, and host interface throughput in bits per second.

## The failing probe (TEST-NET-1)

`prometheus.yml` includes a `blackbox_icmp_fail` job that probes **192.0.2.1** (TEST-NET-1). That address is reserved for documentation and is not reachable, so `probe_success` is 0 while the other probes stay at 1.

If you start without that job and add it later, keep the file bind-mounted and reload Prometheus (lifecycle is enabled in the compose file):

```bash
curl -X POST http://127.0.0.1:9090/-/reload
```

A Prometheus **target** for that job can still show **UP**. UP means Prometheus scraped blackbox_exporter successfully, not that the ICMP probe reached 192.0.2.1. Look at `probe_success` for the probe result.

## Alert used in the walkthrough

The video creates a Grafana-managed rule named **Probe failure** in folder **Network lab**, group **netmon**: `probe_success` is below 1, pending period 10 seconds, evaluation interval 1 minute. A contact point named `lab-webhook` was created (webhook `http://127.0.0.1:9/lab-alert`) but was left unused — it was not attached to a notification policy, so the rule fired in the UI without a delivered notification.

The Grafana 13 alert form also requires a folder, an evaluation group, a pending period at least as long as the evaluation interval, and a contact point. If you skip those, the form shows errors such as **Contact point is required.**

## Images and versions used in the video

| Service | Image | Host port |
|---|---|---|
| Grafana OSS | grafana/grafana-oss:13.0.2 | 3001 |
| Prometheus | prom/prometheus:v3.16.0 | 9090 |
| node_exporter | prom/node-exporter:v1.12.1 | 9100 |
| blackbox_exporter | prom/blackbox-exporter:v0.29.1 | 9115 |

## Files

- `docker-compose.yml` — official Linux images, Grafana on 3001, `NET_RAW` on blackbox, `/proc`+`/sys` for node_exporter
- `prometheus.yml` — scrape jobs, including the optional 192.0.2.1 fail target
- `blackbox.yml` — `icmp` and `http_2xx` modules
- `dashboard-network-lab.json` — dashboard with `${DS_PROMETHEUS}`
- `windows/` — unused leftovers from a Windows-binaries plan; the demonstrated path is Docker in Linux/WSL

`Dockerfile.prometheus` and `Dockerfile.blackbox` are unused leftovers. This lab bind-mounts the YAML files.
