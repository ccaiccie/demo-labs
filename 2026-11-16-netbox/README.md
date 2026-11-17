# NetBox lab: source of truth for a small network (2026-11-16)

Hands-on lab for the Network Technician video on **NetBox** (Community v4.7) running in Docker with the
official [netbox-community/netbox-docker](https://github.com/netbox-community/netbox-docker) setup, release 5.1.2.

You build a small, realistic data center record in NetBox and then read it back over the REST API:

- a region (**US West**) and a site (**Seattle DC1**)
- a manufacturer (**Cisco**), a device type (**Catalyst 9300-24T**) with interface templates, and a device role (**Access Switch**)
- two devices, **sea-sw01** and **sea-sw02**, that get their interfaces from the device type
- a virtual interface **Vlan10** on sea-sw01
- a cable **SEA-C001** between GigabitEthernet1/0/1 on both switches, plus its cable trace
- VLAN **10 Users**, prefix **10.10.10.0/24**, and the first available IP address assigned to Vlan10
- a tag **access-layer** added to both switches with bulk edit
- an API token, the browsable REST API, and `curl` calls that read the status and allocate the next free IP

## What is in this folder

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Official netbox-docker compose file (netbox, netbox-worker, postgres, redis and redis-cache on Valkey) |
| `docker-compose.override.yml` | Lab override: publishes the UI on port **8000**, names the project `netbox-lab`, and lengthens the first-start health check |
| `env/*.env` | Official netbox-docker environment files (lab defaults, change them for anything real) |
| `configuration/` | Official netbox-docker configuration; `extra.py` has the lab additions (`ALLOWED_HOSTS`, time zone) |
| `LICENSE-netbox-docker` | Apache 2.0 licence of the netbox-docker files |

## Requirements

- Docker Engine with the Compose plugin (the video uses Docker in WSL Ubuntu 24.04 on Windows 11)
- Free TCP port 8000 on 127.0.0.1
- About 2 GB of RAM for the five containers

## Start the stack

```bash
git clone https://github.com/ccaiccie/demo-labs.git netbox-demo
cd netbox-demo/2026-11-16-netbox
docker compose up -d netbox          # starts postgres, redis, redis-cache and netbox
docker compose logs -f netbox        # first start runs the database migrations; Ctrl+C after "Initialisation is done"
docker compose up -d                 # starts netbox-worker once netbox is healthy
docker compose ps
```

The first start runs all database migrations and took about six minutes on the demo PC. The upstream health check
gives NetBox only 90 seconds, so a plain `docker compose up -d` would report `container netbox-lab-netbox-1 is unhealthy`
and skip the worker. The override in this folder raises the start period to 600 seconds so that does not happen.

## Create the first admin user

The lab sets `SKIP_SUPERUSER=true`, so no default login exists. Create one from the terminal:

```bash
docker compose exec netbox /opt/netbox/netbox/manage.py createsuperuser
```

Then open <http://127.0.0.1:8000> and sign in.

## Build the lab data (web UI)

1. **Organization > Regions > +**: `US West`.
2. **Organization > Sites > +**: `Seattle DC1`, region `US West`, facility `SEA-DC1`.
3. **Devices > Manufacturers > +**: `Cisco`.
4. **Devices > Device Types > +**: manufacturer `Cisco`, model `Catalyst 9300-24T`, height 1U.
   On the device type, **Add Components > Interfaces**: name `GigabitEthernet1/0/[1-4]`, type `1000BASE-T (1GE)`.
   The range pattern creates four interface templates at once.
5. **Devices > Device Roles > +**: `Access Switch`.
6. **Devices > Devices > +**: `sea-sw01` and `sea-sw02`, role `Access Switch`, type `Catalyst 9300-24T`, site `Seattle DC1`.
   Each device gets GigabitEthernet1/0/1-4 from the templates.
7. On sea-sw01, **Add Components > Interfaces**: `Vlan10`, type `Virtual`.
8. On sea-sw01 interfaces, use the green cable button on GigabitEthernet1/0/1 > **Interface**: B side `sea-sw02` /
   `GigabitEthernet1/0/1`, type CAT6, label `SEA-C001`, 3 meters. Then open the **Trace** button on that interface.
9. **IPAM > VLANs > +**: VLAN ID `10`, name `Users`, Site tab `Seattle DC1`.
10. **IPAM > Prefixes > +**: `10.10.10.0/24`, scope type Site, scope `Seattle DC1`, VLAN `Users`.
11. On the prefix, open the **IP Addresses** tab and click the green "available" link. Assign the address to
    `sea-sw01 > Vlan10` and tick "Make this the primary IP".
12. **Customization > Tags > +**: `access-layer`. Then **Devices > Devices**, select both switches,
    **Edit Selected**, and add the tag.

## REST API

Open <http://127.0.0.1:8000/api/> in the browser for the browsable API (it uses your login session).

For `curl`, create a token under **your user menu > API Tokens > Add a Token**. NetBox 4.7 creates v2 tokens and shows the
full header value (`Bearer nbt_...`) only once, so copy it straight away.

```bash
export NB_AUTH='Bearer nbt_xxxxxxxx.yyyyyyyy'   # paste your own value
curl -s -H "Authorization: $NB_AUTH" http://127.0.0.1:8000/api/status/ | python3 -m json.tool
curl -s -H "Authorization: $NB_AUTH" "http://127.0.0.1:8000/api/ipam/prefixes/1/available-ips/?limit=3" | python3 -m json.tool
curl -s -X POST -H "Authorization: $NB_AUTH" -H "Content-Type: application/json" \
  -d '{"description": "allocated with curl"}' \
  http://127.0.0.1:8000/api/ipam/prefixes/1/available-ips/ | python3 -m json.tool
```

The POST allocates the next free address in the prefix (10.10.10.2/24 after step 11). Prefix ID 1 is the first prefix
in a fresh database; use the number in your prefix URL if yours differs.

## Clean up

```bash
docker compose down -v   # stops the containers and deletes the lab volumes
```

## Notes

- `ALLOWED_HOSTS = ['*']` and the default passwords in `env/` are for a local lab only. Do not expose this stack to the Internet.
- NetBox prints a `LOGIN_REQUIRED is deprecated` warning on every management command. It comes from the upstream
  configuration and is harmless here.
