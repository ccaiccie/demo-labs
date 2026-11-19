# n8n + OpenAI: AI triage for network device logs

Lab for the Network Technician video of 2026-11-19. A router or switch log arrives at an
n8n webhook (directly over HTTP, or as real syslog over UDP through a tiny forwarder).
The n8n OpenAI node (gpt-4o-mini) classifies it and returns JSON with the severity, a
summary, the likely cause and suggested CLI checks. A Switch node then routes it:

| AI `action`     | n8n branch      | What happens |
|-----------------|-----------------|--------------|
| `open_incident` | Open incident   | POST to the mock NetOps receiver, which opens a ticket (INC-1001, ...) |
| `block_ip`      | Block source IP | POST to the receiver, which adds the attacker IP to a simulated firewall blocklist |
| `log_only`      | Log event       | POST to the receiver, which appends it to the event log |

The webhook answers the sender with the result of the last node, so the device or script
that sent the log gets the AI verdict and the ticket number back.

```
 send-log.sh ---- HTTP POST ----> Webhook -> OpenAI gpt-4o-mini (JSON) -> Switch --+--> Open incident   --> receiver /incident (ticket)
 send-syslog.sh -- UDP 5514 --> syslog-forwarder -- HTTP --^                      +--> Block source IP --> receiver /block    (blocklist)
                                                                                  +--> Log event       --> receiver /log      (event log)
```

Everything binds to 127.0.0.1 and all traffic stays on the local Docker network. The only
outbound call is n8n to the OpenAI API.

## What is in this folder

| File | Purpose |
|------|---------|
| `docker-compose.yml` | n8n 2.48.6 (official image), `netops-receiver` and `syslog-forwarder` |
| `.env.example` | Template for your private `.env` (encryption key and your OpenAI key). No secrets in git. |
| `receiver/receiver.py` | Mock NetOps system: tickets, blocklist and event log, with a web page on port 8090 |
| `forwarder/forwarder.py` | Syslog to webhook forwarder: UDP 5514 in, HTTP POST to n8n out |
| `senders/send-log.sh` | Sends one log as JSON to the webhook and pretty-prints the reply |
| `senders/send-syslog.sh` | Sends one real RFC 3164 syslog packet to UDP 5514 |
| `senders/sample-logs.txt` | The sample Cisco-style logs used in the video |
| `workflow/network-log-triage.json` | The finished n8n workflow, exported with credentials removed |

## Requirements

- Docker with the compose plugin (the video uses Docker Engine inside WSL 2 on Windows 11)
- An OpenAI API key. Each log costs a fraction of a cent with gpt-4o-mini.
- Free local ports 5678 (n8n), 8090 (receiver) and UDP 5514 (syslog)
- `curl` and `python3` for the sender scripts

## Steps

1. Create your private `.env`:
   ```bash
   cp .env.example .env
   sed -i "s/^N8N_ENCRYPTION_KEY=.*/N8N_ENCRYPTION_KEY=$(openssl rand -hex 24)/" .env
   nano .env          # paste your OpenAI key on the OPENAI_API_KEY line
   chmod 600 .env
   ```
   The OpenAI key is not passed to any container. You paste it once into the n8n credential
   dialog, where n8n stores it encrypted with `N8N_ENCRYPTION_KEY`.
2. Start the stack: `docker compose up -d` then `docker compose ps`.
3. Open http://127.0.0.1:5678 and create the local owner account (use a lab-only account).
4. Build the workflow (or import `workflow/network-log-triage.json` from the workflow menu and pick your own OpenAI credential):
   - **Webhook**: POST, path `netlog`, Respond `When Last Node Finishes`.
   - **OpenAI > Message a model**: new OpenAI credential, model `gpt-4o-mini`, prompt
     `Device: {{ $json.body.host }}` and `Log: {{ $json.body.message }}` (expression),
     Options: Instructions (the triage prompt below), Output Format `JSON Object`, Temperature `0.2`.
   - **Switch**: three rules on `{{ $json.output[0].content[0].text.action }}` equal to
     `open_incident`, `block_ip` and `log_only`, renamed `incident`, `block` and `log`.
   - **HTTP Request** on each output: POST to `http://netops-receiver:8090/incident`, `/block` or `/log`,
     Send Body JSON with two fields: `log` = `{{ $('Webhook').item.json.body }}` and
     `verdict` = `{{ $('Message a model').item.json.output[0].content[0].text }}`.
5. Test: click **Execute workflow**, then send a log to the test URL:
   ```bash
   N8N_URL=http://localhost:5678/webhook-test/netlog ./senders/send-log.sh core-rtr1 \
     '%BGP-5-ADJCHANGE: neighbor 203.0.113.9 Down BGP Notification sent, hold time expired'
   ```
6. **Publish** the workflow, then use the production URL (the default in `send-log.sh`):
   ```bash
   ./senders/send-log.sh edge-fw1 '%SEC_LOGIN-4-LOGIN_FAILED: Login failed [user: admin] [Source: 198.51.100.77] [localport: 22] (20 attempts in 60 seconds)'
   ./senders/send-syslog.sh dist-sw2 '%SYS-1-CPURISINGTHRESHOLD: Threshold: Total CPU Utilization(Total/Intr): 97%/41%'
   docker logs syslog-forwarder --tail 4
   ```
7. Watch the results at http://127.0.0.1:8090 and in n8n under **Executions**.

### Triage prompt (OpenAI node Instructions)

```
You are a senior network operations engineer. Triage the network device log you receive and reply with JSON only, using exactly these keys: severity (critical, warning or info), category (interface, routing, security, hardware, config or other), summary (one sentence), likely_cause, suggested_checks (array of up to 4 CLI commands to run on the device), action and source_ip. Set action to block_ip only for brute force or attack activity from an outside IP address, and put that address in source_ip. Set action to open_incident for outages or anything critical, such as a BGP or OSPF neighbor down, high CPU or a failed power supply. Otherwise set action to log_only. Use an empty string for source_ip when there is none.
```

## Troubleshooting (all seen in the video)

| Symptom | Cause | Fix |
|---------|-------|-----|
| `404 The requested webhook "POST netlog" is not registered` | Production URL called before the workflow was published | Click **Publish** (test URLs only work right after **Execute workflow**) |
| `{"code":0,"message":"No item to return was found"}` | The Switch sent the item to an output with nothing connected (block branch not built yet) | Add a node on every Switch output, then publish again |
| Test URL returns 404 | The test URL listens for one call only after **Execute workflow** | Click **Execute workflow** again, then resend |

## Safety notes

- Keep your API key out of git and off screen: `.env` is in `.gitignore` and is `chmod 600`.
- The exported workflow contains only a credential name, never the key.
- The blocklist is simulated. Before you let an AI verdict change a real firewall, add a
  human approval step and an allowlist, and test with lab addresses (the samples use the
  RFC 5737 documentation ranges 198.51.100.0/24 and 203.0.113.0/24).

## Clean up

```bash
docker compose down        # stop, keep data
docker compose down -v     # stop and delete the n8n database and receiver data
```

## Links

- n8n: https://n8n.io  |  docs: https://docs.n8n.io  |  source: https://github.com/n8n-io/n8n
- Courses: https://learn.techtohire.com  |  Daily quiz: https://quiz.techtohire.com  |  https://www.techtohire.com
