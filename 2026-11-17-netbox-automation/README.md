# NetBox for network automation and Infrastructure as Code (2026-11-17)

Video: [NetBox Network Automation and IaC: Ansible, Jinja2, FRR Routers and Drift Detection](https://youtu.be/9zyP23RBq9I)

NetBox is the **source of truth**, not the configuration engine. This lab demonstrates the complete loop:

1. Ansible seeds site, devices, interfaces, a cable, prefixes, IPs, a config context and an interface custom field in NetBox.
2. `netbox.netbox.nb_inventory` reads that data back as a **dynamic inventory**.
3. A Jinja2 template renders FRRouting configs from those host variables.
4. Ansible compares each router's **running config** with the NetBox intent, then pushes and applies the config.
5. A change in NetBox changes the router; a manual router change is detected and repaired.
6. The API allocates a next-available IP and an event rule posts a webhook. Re-run automation to deploy that new IP.

This is real software routing: two FRRouting containers, OSPF Full neighbours, learned loopback routes and pings.
They run in WSL Docker. No hardware, licensed network OS, containerlab or nested VM is required.

## Topology and safety

```
NetBox --REST API--> nb_inventory --> Jinja2 --> Ansible --> r1 / r2 (vtysh / frr-reload)
 r1 lo 10.255.0.1/32 -- eth0 10.0.12.1/30 --- 10.0.12.2/30 eth0 -- r2 lo 10.255.0.2/32
                                      OSPF area 0
```

- Official [netbox-docker](https://github.com/netbox-community/netbox-docker) **5.1.2**, NetBox **v4.7**, PostgreSQL 18 and Valkey 9.1.
- Official [FRRouting](https://github.com/FRRouting/frr) image **quay.io/frrouting/frr:10.7.1**.
- ansible-core 2.22.0, netbox.netbox 3.24.0, pynetbox 7.9.0. Versions are pinned in `automation/requirements*`.
- Free port **8000**; browser on Windows: **http://127.0.0.1:8000**. This lab does not use ports 3000 or 8080 on the host.
- Project `nbauto`. Routers `nbauto-r1` and `nbauto-r2`. Nothing here requires stopping other stacks.
- The link bridge uses **172.30.12.0/29** for Docker's bookkeeping. `routers/start.sh` removes Docker's IPv4 addresses
  *inside these two routers*, before FRR starts. The addresses you see on the routers come from NetBox.
- The automation container has the Docker socket mounted. **That grants host-level control. Trusted local lab only.**
  On hardware, use SSH/network_cli, appropriate network modules and scoped credentials rather than this Docker connection.
- All passwords in `env/` are upstream **lab defaults**, not production credentials. Change them for anything real.
- `--check --diff` in this playbook reads running configs, but does not apply changes; don't assume every Ansible module supports safe check mode.

## Start and create an admin

```bash
git clone https://github.com/ccaiccie/demo-labs.git netbox-automation-demo
cd netbox-automation-demo/2026-11-17-netbox-automation
docker compose up -d
# Wait: first-run DB migrations take around 6 minutes on the demo PC.
# The override gives NetBox a 600s healthcheck start period (upstream: 90s).
docker compose ps
docker compose exec netbox /opt/netbox/netbox/manage.py createsuperuser
docker compose build automation
```

Open the UI and sign in. Create a write-enabled v2 API token from your user menu (API Tokens), or provision one:

```bash
# For the disposable video lab we use username admin, password NetBoxLab2026!
# Don't put a real password in your command history.
curl -s -X POST -H 'Content-Type: application/json' \
  http://127.0.0.1:8000/api/users/tokens/provision/ \
  -d '{"username":"admin","password":"NetBoxLab2026!"}' > /tmp/nb-token.json
export NETBOX_TOKEN=$(python3 -c "import json;d=json.load(open('/tmp/nb-token.json'));print('nbt_'+d['key']+'.'+d['token'])")
# v2 tokens use Authorization: Bearer, not the legacy Token header.
```

The token is local-only and deleted with the database; never commit it. `automation` receives it through the environment.
For a real environment, use dedicated least-privilege read/write tokens, HTTPS and a secret manager.

## Seed as code and inspect the inventory

```bash
# Convenience shell function for commands in the Ansible controller.
# -q suppresses compose's transient container-create messages.
auto() { docker compose run --rm -q automation "$@"; }
auto ansible-playbook seed.yml
# Second run should have changed=0; event-rule creation is skipped if it already exists.
auto ansible-playbook seed.yml
auto ansible-inventory --graph
auto ansible-playbook show_host.yml
auto ansible-inventory --host r1 --yaml | less
```

Browse **Organization / Sites**, **Devices / Devices**, interfaces, **IPAM / Prefixes** and **IP Addresses** in the UI.
`seed.yml` demonstrates `netbox.netbox` modules; the event rule uses `uri` because this collection version has no
`netbox_event_rule` module. The seeding playbook is the baseline. If you intentionally change NetBox in the UI, don't
re-run the seed playbook unless you want to restore that baseline too.

Inventory groups include `platforms_frr`, `device_roles_router` and `sites_lab-dc1`.
`group_vars/platforms_frr.yml` selects the Docker API connection and the router container name. `nb_inventory` sets
`ansible_host` to the primary IP; the connection's `ansible_docker_host` overrides that just for the lab transport.
FRR has Python in its official image, so normal Ansible modules run inside the router containers.

## Render, push and verify

```bash
cat automation/templates/frr.conf.j2
cat automation/deploy.yml
auto ansible-playbook deploy.yml --check --diff
auto ansible-playbook deploy.yml --diff
# Allow OSPF to form and run SPF (up to ~20 seconds).
docker compose exec r1 vtysh -c 'show running-config'
docker compose exec r1 vtysh -c 'show interface brief' -c 'show ip ospf neighbor'
docker compose exec r1 vtysh -c 'show ip route ospf'
docker compose exec r1 ping -c3 -I 10.255.0.1 10.255.0.2
auto ansible-playbook deploy.yml --diff  # changed=0 on both
```

`deploy.yml` compares the **live** normalized running config with the template, not just the file on disk.
Only FRR's generated version, domainname and end lines are excluded from comparison. `frr-reload.py` applies a delta,
including deletions; a plain `vtysh -f` would merge and leave removed statements behind.
This lab template owns the router's entire FRR routing configuration. Scope ownership and review deletions before
using this pattern in a real network. Rollback, approvals and pre/post checks belong in a production pipeline.

## Change in NetBox, then detect and repair drift

In the NetBox UI, edit **r1 / eth0**: description `r1-r2 core link`, custom field **OSPF cost** `50`. Save.

```bash
auto ansible-playbook deploy.yml --check --diff --limit r1
auto ansible-playbook deploy.yml --diff --limit r1
docker compose exec r1 vtysh -c 'show ip ospf interface eth0'
docker compose exec r1 vtysh -c 'show ip route 10.255.0.2/32'
# Now deliberately bypass NetBox on r2 (out-of-band change):
docker compose exec r2 vtysh -c 'conf t' -c 'interface eth0' -c 'ip ospf cost 999' -c 'exit' -c 'ip route 192.0.2.0/24 Null0'
auto ansible-playbook deploy.yml --check --diff  # detects the drift on r2 but changes nothing
docker compose exec r2 vtysh -c 'show running-config'
auto ansible-playbook deploy.yml --diff         # removes the unapproved cost and static route
auto ansible-playbook deploy.yml --check --diff # changed=0
```

## Next-available IP and event webhook

```bash
cat automation/scripts/next_ip.py
auto python scripts/next_ip.py 10.255.1.0/24 r2 lo 'r2 service loopback'
# On a fresh database that allocates 10.255.1.1/24. API default keeps the prefix length.
# FRR OSPF advertises a loopback as a /32, even though the allocated address has a /24 mask.
docker compose logs --no-log-prefix webhook | python3 automation/scripts/webhook_log.py
auto ansible-playbook deploy.yml --diff --limit r2
docker compose exec r1 vtysh -c 'show ip route ospf'
docker compose exec r1 ping -c3 -I 10.255.0.1 10.255.1.1
```

`pfx.available_ips.create()` is a POST to `/api/ipam/prefixes/{id}/available-ips/`; it both allocates and assigns the
address in one call. Each run allocates another IP on purpose. The webhook is **notification only**: it does not apply
configuration automatically. The operator reviews and re-runs the playbook.

## Clean up

```bash
docker compose down -v --rmi local
# Removes only this stack's containers, networks and named volumes. Lab files remain.
# --rmi local skips images that have a custom tag, so remove the controller image yourself:
docker image rm nbauto-automation:lab
# Optional: docker image rm quay.io/frrouting/frr:10.7.1 (and the NetBox, Postgres and Valkey images)
```

## Troubleshooting observed while building the lab

- Inventory plugin needs **pytz** as well as pynetbox; it is included in the controller requirements.
- Modules use `device_role` for a device and capitalized `Loopback` for an IP role, even though the API fields differ.
- The inventory sets `ansible_host` to the primary IP. Use `ansible_docker_host` for the container transport, not another `ansible_host` group var.
- A manual `vtysh` change can print `% Configuration applied with notes: No changes found to be committed!` and still
  appear in `show running-config`. Trust the running config, which is what the drift check compares.
- OSPF can be Full before the first SPF installs a route. Wait a few seconds, then verify the route and ping again.
- Ansible 2.22 warns about NetBox inventory fields named `serial` and `tags` (reserved variable names). These warnings
  do not stop the playbook; don't use those fields as play keywords. The template uses only the network data it needs.

Courses: https://learn.techtohire.com
Free daily quiz: https://quiz.techtohire.com
