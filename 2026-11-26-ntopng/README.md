# 2026-11-26 ntopng Community: real-time traffic monitoring with nDPI

A small lab that runs **ntopng Community** (official `ntop/ntopng` image) against a dedicated Docker bridge
with a few containers generating realistic traffic. You will see live flows, hosts, nDPI application
detection, interface charts, host details, a real flow alert, and the REST API with `curl`.

Everything stays on the lab bridge `br-ntoplab` (10.77.40.0/24). The generators only make a few normal
DNS lookups and HTTPS GETs to public sites (example.com, wikipedia, github, cloudflare, debian) so that
nDPI has more than one application to classify.

## What is in the folder

| Path | Purpose |
|------|---------|
| `docker-compose.yml` | ntopng, nginx web server, dnsmasq DNS server, iperf3 server, three client containers |
| `tools/Dockerfile` | Alpine image with curl, iperf3, dig, ping, nmap used by the clients |
| `scripts/traffic.sh` | Traffic generator loop (profiles `office` and `engineering`) |
| `scripts/trigger.sh` | TCP connect sweep of the lab web server from the idle host `gen-c` (creates the alert) |
| `scripts/ntopng_api.py` | Small standard-library helper around the REST API (summary, flows, hosts, l7, alerts) |
| `scripts/make-payload.sh` | Creates the 12 MB `backup.bin` file served by the web container (not committed) |
| `.env.example` | Variables used by the helper scripts (copy to `.env`, never commit it) |

| Container | Address | Role |
|-----------|---------|------|
| `ntl-web` | 10.77.40.10 | nginx, serves `/` and `/backup.bin` |
| `ntl-dns` | 10.77.40.11 | dnsmasq, `web.lab.test` and `iperf.lab.test`, forwards the rest |
| `ntl-iperf` | 10.77.40.12 | `iperf3 -s` |
| `ntl-gen-a` | 10.77.40.21 | traffic profile `office` |
| `ntl-gen-b` | 10.77.40.22 | traffic profile `engineering` (bulk download, iperf3) |
| `ntl-gen-c` | 10.77.40.23 | idle until you run the trigger |
| `ntopng-lab` | host network | ntopng, captures `br-ntoplab`, UI on http://127.0.0.1:3010 |

## Steps

1. Create the payload and start the lab (needs Docker with the compose plugin; the subnet 10.77.40.0/24 and port 3010 must be free):

   ```bash
   sh scripts/make-payload.sh
   docker compose up -d --build
   docker compose ps
   ```

2. Open http://127.0.0.1:3010 and log in as `admin` / `admin`. ntopng forces you to change the default
   password on first login. Pick your own and keep it out of git.

3. Put the credentials in a git-ignored `.env` and load them (used by the helper and the curl examples):

   ```bash
   cp .env.example .env      # edit NTOPNG_ADMIN_PASSWORD
   set -a; . ./.env; set +a
   ```

4. Look around the UI (give the generators a minute first):
   * Dashboard: Top Flow Talkers, Top Hosts, Top Applications, Traffic Classification.
   * Flows > Live Flows: protocol column, the DPI badge, filters (Application = DNS / HTTP), the search box
     (`5201` finds the iperf3 flows), the magnifier button for flow details.
   * Network > Hosts: sort by Total Bytes, open a host, then its Apps and Flows tabs.
   * Network > Interface Details: Traffic Breakdown, the Apps tab (nDPI per interface), the chart tab.
   * Developer > REST API: the swagger page.

5. REST API with curl (the helper calls the same endpoints):

   ```bash
   ng() { curl -s -u "$NTOPNG_ADMIN_USER:$NTOPNG_ADMIN_PASSWORD" "$NTOPNG_URL/lua/rest/v2/$1"; }
   ng get/ntopng/interfaces.lua | python3 -m json.tool
   ng 'get/interface/data.lua?ifid=0' | python3 -m json.tool | head -40
   ng 'get/interface/l7/stats.lua?ifid=0&ndpistats_mode=count' | python3 -m json.tool
   ng 'get/flow/active.lua?ifid=0&currentPage=1&perPage=10'
   ng 'get/host/active.lua?ifid=0&currentPage=1&perPage=10'

   python3 scripts/ntopng_api.py summary
   python3 scripts/ntopng_api.py flows 6
   python3 scripts/ntopng_api.py hosts 6
   python3 scripts/ntopng_api.py l7
   python3 scripts/ntopng_api.py alerts 30
   ```

6. Trigger an alert. The idle host sweeps the first 500 TCP ports of the lab web server:

   ```bash
   cat scripts/trigger.sh
   docker exec ntl-gen-c sh /scripts/trigger.sh
   ```

   In the UI open Alerts > Explorer > Flow, switch the status button from Require Attention to All, refresh
   the time range and sort by Score (highest first). The top alert is **Probing Attempt**, client 10.77.40.23,
   server 10.77.40.10. The same alerts come back from
   `ng 'get/flow/alert/list.lua?ifid=0&status=any&epoch_begin=<start>&epoch_end=<end>&currentPage=1&perPage=3000'`.

## What we observed

* ntopng 7.0 Community, one interface (`br-ntoplab`), reachable only on 127.0.0.1:3010.
* nDPI labels DNS, HTTP, TLS and ICMP flows from their content (DPI badge). The iperf3 flows on port 5201
  show up as `TargusDataspeed` **without** the DPI badge: that is a port-based guess, not a content match.
* The default Require Attention filter in the Alerts Explorer stayed empty in this lab; the All filter shows the alerts.
* The port sweep from `gen-c` produced about 500 `Probing Attempt` flow alerts (score 100 or more), and gen-c's host score jumped to the tens of thousands.
* The top bar shows an Upgrade to Pro/Enterprise button; this lab uses the Community edition only.
* When the container starts, ntopng warns that the bridge receives packets larger than the 1518 byte MTU
  (GRO/TSO offload on the host). Totals are still fine for a demo; for accuracy turn offloads off on the capture interface.

## Clean up

```bash
docker compose down -v
```

This removes the lab containers, the `ntoplab` network and the ntopng data volume. It does not touch other containers.
