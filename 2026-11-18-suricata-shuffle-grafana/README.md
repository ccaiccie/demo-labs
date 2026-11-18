# 2026-11-18 Suricata + Shuffle + Grafana (local IDS lab)

Blue-team detection and response lab. A local OWASP Juice Shop victim and a local attacker generate traffic on a private Docker network. Suricata (ET Open + custom lab rules) sniffs the bridge, alerts land in `eve.json`, Promtail ships them to Loki for Grafana, and a forwarder posts alerts to a Shuffle webhook workflow plus a local case log.

**Nothing leaves your lab network. Do not point the attacker at public sites.**

## Architecture

| Component | Role | URL / notes |
|-----------|------|-------------|
| Juice Shop | Deliberately vulnerable victim | http://127.0.0.1:3200 |
| Attacker container | curl-based probe script | `docker exec ids-attacker sh /attack.sh` |
| Suricata | IDS on the `ids-lab` bridge (host net) | logs in volume `ids-lab_suricata-logs` |
| Loki + Promtail | Alert log pipeline | Loki http://127.0.0.1:3101 |
| Grafana | Dashboard (provisioned) | http://127.0.0.1:3010 (admin / labadmin) |
| Case log | Local triage sink | http://127.0.0.1:8099/cases |
| Shuffle | SOAR webhook workflow | http://127.0.0.1:3001 |

Netflow-stack Grafana on port 3000 is left untouched.

## Quick start

```bash
# 1) Detection stack
./scripts/up-ids.sh

# 2) Shuffle (first time clones the upstream repo)
./scripts/setup-shuffle.sh
# Open http://127.0.0.1:3001 — create admin user, build a Webhook workflow,
# copy the webhook URL, then:
./scripts/set-webhook.sh 'http://127.0.0.1:3001/api/v1/hooks/<YOUR_HOOK>'

# 3) Generate local attacks and watch alerts
./scripts/run-attack.sh
```

## Grafana

Sign in at http://127.0.0.1:3010 with `admin` / `labadmin`. Dashboard **Suricata IDS Lab Alerts** is provisioned under folder Suricata.

## Shuffle workflow (on camera)

1. Open http://127.0.0.1:3001 and create the first administrator account (stay on your own instance; skip the cloud onboarding).
2. Workflows -> Create Workflow -> name it `Suricata Alert Triage` -> Create from scratch.
3. Drag the **Webhook** trigger onto the canvas; it auto-connects to the default **Change Me** node (Shuffle Tools, "Repeat back to me").
4. In Change Me, set the call field to:
   `Suricata alert: $exec.signature | severity $exec.severity | src $exec.src_ip to $exec.dest_ip port $exec.dest_port`
5. Save, click the Webhook node, press **Start**, copy the Webhook URI.
6. `./scripts/set-webhook.sh '<webhook URI>'` restarts the forwarder with that URL.
7. `./scripts/run-attack.sh`, then open "Show previous workflow runs" in Shuffle - each run shows status FINISHED and the rendered alert sentence.

Helpers: `./scripts/show-alerts.sh` (alert counts per signature), `./scripts/show-cases.sh` (local case log).

Troubleshooting seen while building this lab:
- Suricata exits right away with a chown error on read-only bind mounts -> `start-suricata.sh` copies configs to `~/suricata-run`.
- Shuffle runs stay queued if `OUTER_HOSTNAME` is `127.0.0.1` -> keep upstream `shuffle-backend` (the setup script does this).
- ET rule 2034635 fires on the Python case-log banner -> suppressed in `suricata/etc/threshold.config`.

## Files

- `docker-compose.yml` — victim, attacker, Loki, Promtail, Grafana, case log, forwarder
- `suricata/rules/local.rules` — guaranteed lab signatures
- `suricata/etc/suricata.yaml` — generated from image defaults by `scripts/prepare-suricata-yaml.sh`
- `grafana/` — datasource + dashboard provisioning
- `attacker/attack.sh` — local-only probes
- `forwarder/` — eve.json → Shuffle webhook + case log
- `scripts/` — bring-up helpers

## Cleanup

```bash
docker compose -f docker-compose.yml down
docker rm -f ids-suricata 2>/dev/null || true
# Shuffle (optional):
cd shuffle && docker compose down
# Do NOT stop netflow-* containers.
```
