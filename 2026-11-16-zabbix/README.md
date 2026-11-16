# Zabbix 7.0 LTS monitoring lab (2026-11-16)

Hands-on lab for the **Network Technician** YouTube demo: stand up Zabbix in Docker, fix the
default "Zabbix server" agent interface, add a Linux host by hand, read latest data, build a
custom item and trigger, raise and resolve a real problem, and add a dashboard graph.

## What is in this folder

| File | Purpose |
|------|---------|
| `docker-compose.yml` | PostgreSQL 16, Zabbix server 7.0.32, Zabbix web (nginx), and two Zabbix agent 2 containers |
| `.env` | Lab-only database credentials (change them for anything real) |

Containers:

| Service | Container | Notes |
|---------|-----------|-------|
| `postgres` | `zbx-postgres` | Zabbix database (volume `zbx-db`) |
| `zabbix-server` | `zbx-server` | Listens on 127.0.0.1:10051; config cache refresh 10 s for a snappy lab |
| `zabbix-web` | `zbx-web` | Web UI on **http://127.0.0.1:8088** |
| `zabbix-agent` | `zbx-agent` | Agent for the built-in "Zabbix server" host (DNS name `zabbix-agent`) |
| `lab-agent` | `zbx-lab-agent` | Second Linux agent you add by hand as host `lab-agent` |

Port 8088 is used because 8080 and 3000 were already taken on the demo PC. Change the left side
of `"8088:8080"` if it clashes on yours.

## Requirements

- Docker Engine with the Compose plugin (Docker Desktop or Docker inside WSL 2 works)
- About 1.5 GB of free disk for the images

## Steps

1. Clone and start the stack:

   ```bash
   git clone https://github.com/ccaiccie/demo-labs.git
   cd demo-labs/2026-11-16-zabbix
   docker compose up -d
   docker compose ps
   ```

   Wait until `curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8088/` prints `200`
   (the server creates the database schema on first start, about 30-60 seconds).

2. Open http://127.0.0.1:8088 and sign in as **Admin** / **zabbix**.

3. **Fix the built-in host.** Data collection > Hosts > *Zabbix server*. Its agent interface
   points at `127.0.0.1`, which inside the server container is the server itself, so the
   ZBX availability badge turns red ("cannot connect"). In the Interfaces row type DNS name
   `zabbix-agent`, click **DNS** under *Connect to*, then **Update**. The badge turns green.

4. **Add a host.** Data collection > Hosts > **Create host**:
   - Host name: `lab-agent`
   - Templates: `Linux by Zabbix agent`
   - Host groups: `Linux servers`
   - Interfaces > Add > Agent: DNS name `lab-agent`, Connect to **DNS**, port `10050`
   - Click **Add**, then wait for the ZBX badge to turn green.

5. **Latest data.** Monitoring > Latest data, filter Hosts = `lab-agent`, Apply. Open the
   *Graph* link next to **CPU utilization**.

6. **Custom item.** Hosts > lab-agent > Items > **Create item**:
   - Name: `Alert flag file exists`
   - Key: `vfs.file.exists[/tmp/alert.flag]`
   - Update interval: `10s`

7. **Trigger.** Hosts > lab-agent > Triggers > **Create trigger**:
   - Name: `Alert flag file present on lab-agent`, Severity **High**
   - Expression: `last(/lab-agent/vfs.file.exists[/tmp/alert.flag])=1`

8. **Raise a problem** from the terminal, then check Monitoring > Problems:

   ```bash
   docker compose exec lab-agent touch /tmp/alert.flag
   ```

9. **Dashboard.** Dashboards > Global view > Edit dashboard > Add > Type **Graph**,
   host pattern `lab-agent`, item pattern `CPU utilization`, Add, **Save changes**.

10. **Resolve it** and watch the problem flip to RESOLVED:

    ```bash
    docker compose exec lab-agent rm /tmp/alert.flag
    ```

11. Clean up:

    ```bash
    docker compose down        # keeps the zbx-db volume
    docker compose down -v     # also deletes the database volume
    ```

## Troubleshooting

- **ZBX badge red on "Zabbix server"**: the interface still says 127.0.0.1; switch it to DNS
  `zabbix-agent` (step 3).
- **New host stays grey**: give it up to a minute; the server refreshes its configuration cache
  every 10 s in this lab and agent checks run every minute.
- **Port 8088 in use**: change `"8088:8080"` in `docker-compose.yml`.

Images: official `zabbix/zabbix-server-pgsql`, `zabbix/zabbix-web-nginx-pgsql`,
`zabbix/zabbix-agent2` (tag `alpine-7.0.32`) and `postgres:16-alpine`.
