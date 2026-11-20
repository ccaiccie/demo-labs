# Uptime Kuma hands-on lab (2026-11-19)

Self-hosted uptime and network monitoring with [Uptime Kuma](https://github.com/louislam/uptime-kuma) 2.5.12
(official image `louislam/uptime-kuma:2.5.12`), plus a handful of small local targets on a private Docker network.
Everything stays inside the lab: the only published port is the Kuma web UI on `127.0.0.1:3301`.

## What is in the lab

| Service | Image | Lab address | Used for |
|---|---|---|---|
| uptime-kuma | louislam/uptime-kuma:2.5.12 | 10.77.77.10, UI on 127.0.0.1:3301 | the monitor |
| web | nginx:1.27-alpine | 10.77.77.20 (`web`) | HTTP keyword monitor, Ping monitor |
| whoami | traefik/whoami:v1.10 | 10.77.77.21 (`whoami`) | plain HTTP monitor |
| redis | redis:7.4-alpine (with healthcheck) | 10.77.77.22 (`redis`) | TCP port monitor, Docker container monitor |
| dns | coredns/coredns:1.11.3 | 10.77.77.53 | DNS monitor against the `lab.local` zone |
| webhook | python:3.12-alpine + `webhook/receiver.py` | 10.77.77.30 (`webhook:8080`) | receives Kuma webhook notifications |

Files:

- `docker-compose.yml` - the whole lab (network `10.77.77.0/24`, named volume `kuma-data`)
- `coredns/Corefile`, `coredns/db.lab.local` - authoritative lab zone (`web.lab.local` -> 10.77.77.20, ...), no forwarding
- `web/index.html` - page that contains the keyword `LAB-WEB-OK`
- `webhook/receiver.py` - prints a short summary of each notification POST
- `scripts/backup.sh` - tars the Kuma data volume (2.x has no JSON export in Settings)

The Docker socket is mounted read-only into Kuma so the Docker Container monitor can read container state.
If 10.77.77.0/24 or port 3301 are already used on your host, change them in `docker-compose.yml`.

## Steps (what the video does)

```bash
git clone --depth 1 --filter=blob:none --sparse https://github.com/ccaiccie/demo-labs.git
cd demo-labs && git sparse-checkout set 2026-11-19-uptime-kuma && cd 2026-11-19-uptime-kuma
docker compose up -d
docker compose ps
```

1. Open http://127.0.0.1:3301 - choose **SQLite**, then create the admin account (use a lab-only password).
2. **Notification**: Add New Monitor - Set Up Notification - type **Webhook**, Post URL `http://webhook:8080/kuma`,
   Request Body **Preset - application/json** (the form will not save while it is empty), tick *Default enabled* and
   *Apply on all existing monitors*, press **Test**, then **Save**. Watch it arrive with `docker compose logs -f webhook`.
3. **Group**: monitor type *Group*, name `Lab Services`.
4. **Monitors** (interval 20 s, retries 0, group Lab Services):
   - HTTP(s) - Keyword: `http://web/`, keyword `LAB-WEB-OK`, tag `lab`
   - HTTP(s): `http://whoami/`
   - TCP Port: host `redis`, port `6379`
   - Ping: host `web`
   - DNS: hostname `web.lab.local`, resolver `10.77.77.53`, port 53, record type A
   - Docker Container: container `lab-redis`, Docker host = new host, type Socket, `/var/run/docker.sock`
5. **Break it**: `docker compose stop web` - the keyword and ping monitors and the group go DOWN and the receiver
   prints the DOWN payloads. `docker compose start web` - UP notifications follow.
6. **Status page**: Status Pages - New Status Page `Lab Network Status`, slug `lab`, add monitors, Save.
   Public page: http://127.0.0.1:3301/status/lab
7. **Maintenance**: Maintenance - Schedule Maintenance, affected monitor `Redis TCP 6379`, single 1 hour window,
   show it on the status page. `docker compose stop redis` - Redis TCP shows blue MAINTENANCE and sends no alert,
   while `Docker lab-redis` (not in the window) still alerts. `docker compose start redis`, then end the maintenance.
8. **Backup**: `bash scripts/backup.sh` - tarball of `/app/data` (kuma.db and friends).
9. Clean up: `docker compose down` (add `-v` to also delete the Kuma data volume).

## Notes

- Uptime Kuma 2.x asks for the database type on first start (SQLite, embedded MariaDB, or external MariaDB/MySQL).
- Retries 0 makes the demo fast; in production use retries 1-3 to avoid alerting on a single lost packet.
- A Docker Container monitor on a container without a healthcheck reports UP with a hint to add one; the lab's
  redis has a `redis-cli ping` healthcheck.
