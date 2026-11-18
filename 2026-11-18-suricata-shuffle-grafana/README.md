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
./scripts/set-webhook.sh 'http://127.0.0.1:5001/api/v1/hooks/<YOUR_HOOK>'

# 3) Generate local attacks and watch alerts
./scripts/run-attack.sh
```

## Grafana

Sign in at http://127.0.0.1:3010 with `admin` / `labadmin`. Dashboard **Suricata IDS Lab Alerts** is provisioned under folder Suricata.

## Shuffle workflow (on camera)

1. Create org admin on first visit.
2. Automate → Workflows → New.
3. Add a **Webhook** trigger; copy the URL.
4. Add nodes: Webhook → (optional) Transform / Set variable for severity tag → HTTP to `http://host.docker.internal:8099/case` or the built-in Shuffle Tools / email-like logger.
5. Start the workflow; run `./scripts/run-attack.sh`; confirm executions.

A sample exported workflow JSON lives in `shuffle-overlay/suricata-alert-triage.json` after you export it from the UI (placeholder notes included).

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
