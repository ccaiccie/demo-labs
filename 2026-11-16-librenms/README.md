# LibreNMS lab: SNMP monitoring, discovery, maps and alerts (2026-11-16)

Hands-on lab for the Network Technician video on **LibreNMS** 26.10.2 running in Docker with the official
[librenms/docker](https://github.com/librenms/docker) compose example (librenms, dispatcher, MariaDB, Redis, msmtpd).

Video: Coming soon

You monitor two Linux SNMP agents that run inside the lab network:

- **snmp-sw1** answers SNMP **v2c** with the community `labpublic`
- **snmp-sw2** answers **SNMPv3 only** (authPriv, user `labv3user`, SHA + AES)
- both run **lldpd** as an AgentX subagent, so LibreNMS discovers the link between them and draws it on the network map
- a small `ping` container sends steady traffic to snmp-sw1, so its port graphs show real numbers
- a webhook echo container receives the alert notifications and prints them to its log

In the video you:

- create the admin user in the first-run installer and switch to 1-minute polling with `lnms config:set`
- add snmp-sw1 in the web UI (v2c) and snmp-sw2 with `lnms device:add` (v3)
- run `lnms device:discover` and `lnms device:poll` and read the output
- look at the device overview, ports and traffic graphs, the LLDP neighbours, the health sensors and the network map
- build an alert: an **API transport** to the webhook, an **operation**, and the **Devices up/down** rule from the collection
- stop snmp-sw1, watch the alert appear in Faults and in the webhook log, start it again and watch it recover

## What is in this folder

| File | Purpose |
|------|---------|
| `compose.yml` | Official librenms/docker example compose file, unchanged |
| `librenms.env`, `msmtpd.env` | Official example environment files, unchanged (msmtpd is not configured for real mail) |
| `.env` | Time zone, PUID/PGID and a lab-only database password |
| `compose.override.yml` | Lab additions: pins the image to 26.10.2, named volumes, the two SNMP agents, the traffic generator and the webhook; puts the syslog-ng and snmptrapd sidecars behind profiles |
| `snmpd/` | Alpine image with net-snmp and lldpd, plus the v2c and v3 agent configurations |
| `LICENSE-librenms-docker` | MIT licence of the librenms/docker files |

## Requirements

- Docker Engine with the Compose plugin, version 2.24 or newer (the override uses `!override`).
  The video uses Docker in WSL Ubuntu 24.04 on Windows 11.
- Free TCP port 8000 on 127.0.0.1
- About 2 GB of RAM

## Start the stack

```bash
git clone https://github.com/ccaiccie/demo-labs.git librenms-demo
cd librenms-demo/2026-11-16-librenms
docker compose up -d --build
docker compose ps
```

Only port 8000 is published. The SNMP agents are reachable by name (`snmp-sw1`, `snmp-sw2`) from the LibreNMS
containers. The optional syslog and trap receivers publish ports 514 and 162, so they start only when you ask:

```bash
docker compose --profile syslog --profile traps up -d
```

## First run

Open <http://127.0.0.1:8000>. The installer asks for an admin user, then **Finish Install**. Sign in with that user.

Switch to 1-minute polling before you add devices (new RRD files then use a 60-second step), and restart the dispatcher
so it picks up the new poller frequency:

```bash
docker compose exec librenms lnms config:set rrd.step 60
docker compose exec librenms lnms config:set rrd.heartbeat 120
docker compose exec librenms lnms config:set service_poller_frequency 60
docker compose restart dispatcher
```

Check SNMP from the LibreNMS container:

```bash
docker compose exec librenms snmpget -v2c -c labpublic snmp-sw1 SNMPv2-MIB::sysName.0
docker compose exec librenms snmpget -v3 -l authPriv -u labv3user -a SHA -A LabAuthPass2026 -x AES -X LabPrivPass2026 snmp-sw2 SNMPv2-MIB::sysName.0
```

## Add the devices

Web UI, **Devices > Add Device**: hostname `snmp-sw1`, SNMP version `v2c`, community `labpublic`.

CLI, SNMPv3:

```bash
docker compose exec librenms lnms device:add --v3 -u labv3user -a SHA -A LabAuthPass2026 -x AES -X LabPrivPass2026 snmp-sw2
docker compose exec librenms lnms device:discover all
docker compose exec librenms lnms device:poll all
```

The dispatcher also discovers and polls new devices on its own; the commands show you what each module finds.
Discovery reports `LLDP: 1 neighbors` on each switch and creates the link that the **Neighbours** tab and
**Maps > Network** show.

Why CDP is enabled in lldpd: a Linux bridge, such as the Docker network, does not forward LLDP frames
(destination 01:80:c2:00:00:0e). It does forward CDP frames, so `lldpd -cc` sends CDP as well and the agents still
learn each other. lldpd publishes the neighbours in the LLDP-MIB, which LibreNMS reads.

## Alerts

1. **Alerts > Alert Transports > Create alert transport**: name `lab-webhook`, type **API**, Default Alert ON,
   method POST, URL `http://webhook:8080/librenms`, header `Content-Type=application/json`, body
   `{"title": "{{ $title }}", "host": "{{ $hostname }}", "state": "{{ $state }}"}`.
2. **Alerts > Operations > Create operation**: name `Notify lab webhook`, default step 60, one segment from step 1
   to 1, start 0, step duration 60, transport `lab-webhook`. In LibreNMS 26.x a rule without an operation still raises
   alerts but sends no notification.
3. **Alerts > Alert Rules > Create rule from collection**: select **Devices up/down**, set Operation to
   `Notify lab webhook`, **Save Rule**.

Trigger and clear the alert:

```bash
docker compose stop snmp-sw1
docker compose exec librenms lnms device:poll snmp-sw1     # "Status: ALERT" for rule Devices up/down
docker compose logs webhook | grep '"body"'                # the notification arrives within about a minute
docker compose start snmp-sw1
docker compose exec librenms lnms device:poll snmp-sw1     # "Status: OK"
docker compose logs webhook | grep '"body"'                # "... recovered from Devices up/down"
```

See the alert in **Alerts > Faults** while it is active and in **Alerts > Alert History** afterwards.

## Clean up

```bash
docker compose down -v   # stops the containers and deletes the lab volumes
```

## Notes

- All passwords and the SNMP community are lab-only values. Do not expose this stack to the Internet.
- The install page shows the generated `APP_KEY`. In a real installation, save it: LibreNMS needs it to decrypt
  stored secrets.
