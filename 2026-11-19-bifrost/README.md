# Bifrost OSS LLM/MCP gateway lab

Dated lab folder for the Network Technician channel: `2026-11-19-bifrost`.

Bifrost is an Apache 2.0 open-source LLM and MCP gateway from Maxim AI. This lab runs the official OSS image in Docker, not an Enterprise trial. It is aimed at network and security engineers who want one self-hosted, OpenAI-compatible endpoint with:

- A real OpenAI model (`gpt-4o-mini`) and a local Ollama fallback (`llama3.2:1b`)
- Automatic failover when the primary model or provider fails
- Direct and semantic response caching (Redis Stack)
- Virtual keys with request rate limits and USD budgets
- Prometheus metrics and request logs
- An MCP gateway in front of a read-only folder of sample router output

Upstream: [github.com/maximhq/bifrost](https://github.com/maximhq/bifrost) and [docs.getbifrost.ai](https://docs.getbifrost.ai).

## Ports

Everything published to the host is bound to `127.0.0.1` only.

| Port | Service |
|---|---|
| `127.0.0.1:8088` | Bifrost UI, API, `/health`, `/metrics`, `/mcp` (container port 8080) |

Ollama and Redis stay on the Compose network. This lab does not publish `11434`, because a host Ollama install may already be using it. Bifrost reaches Ollama at `http://ollama:11434` with `allow_private_network: true`. Do not use host ports 3000, 3001, 4310, 5678, 5514, 8080, or 8090; those are reserved by other stacks on the lab machine.

## Quick start

```bash
cp .env.example .env
chmod 600 .env
# Put a real OPENAI_API_KEY in .env. Generate the other values:
#   openssl rand -hex 32   # encryption key and setup token
#   echo sk-bf-netops-$(openssl rand -hex 16)
# Set a strong BIFROST_ADMIN_PASSWORD. Never commit .env.

docker compose up -d --build
docker exec bifrost-ollama ollama pull llama3.2:1b
curl -sS http://127.0.0.1:8088/health
```

Open `http://127.0.0.1:8088`. Create the first dashboard admin (OSS v2.6.0 requires `BIFROST_SETUP_TOKEN`):

```bash
# The token must be sent in this header. Also keep log_retention_days >= 1.
source .env
curl -sS -X PUT http://127.0.0.1:8088/api/config \
  -H "Content-Type: application/json" \
  -H "X-Bifrost-Setup-Token: $BIFROST_SETUP_TOKEN" \
  -d "{
    \"client\": {\"enable_logging\": true, \"log_retention_days\": 30, \"enforce_auth_on_inference\": true},
    \"auth_config\": {
      \"is_enabled\": true,
      \"admin_username\": \"$BIFROST_ADMIN_USERNAME\",
      \"admin_password\": \"$BIFROST_ADMIN_PASSWORD\",
      \"setup_token\": \"$BIFROST_SETUP_TOKEN\",
      \"disable_auth_on_inference\": true
    }
  }"
```

`disable_auth_on_inference: true` means chat calls keep using virtual keys. The admin password protects the dashboard, `/metrics`, and `/api/logs`.

A first chat call:

```bash
source .env
curl -sS http://127.0.0.1:8088/v1/chat/completions \
  -H "Authorization: Bearer $VK_NETOPS" \
  -H "Content-Type: application/json" \
  -d '{"model":"openai/gpt-4o-mini","messages":[{"role":"user","content":"Reply with pong"}],"max_tokens":8}'
```

Python SDK drop-in (from the host):

```python
from openai import OpenAI
client = OpenAI(base_url="http://127.0.0.1:8088/openai/v1", api_key=VK_NETOPS)
```

See `DEMO-PLAN.md` for the full on-camera flow (fallback, cache, limits, MCP).

## Layout

- `docker-compose.yml` — Bifrost v2.6.0, official Ollama 0.12.10, Redis Stack 7.4.0-v8, local MCP server
- `config/config.json` — providers, virtual keys, cache, MCP, logging (no secret values; all `env.*` references)
- `mcp-netops/` — read-only Streamable-HTTP MCP server and sample `show` / syslog files
- `scripts/sdk_chat.py` and `scripts/pull-ollama-model.sh`

## Security notes

- Secrets live only in `.env` (chmod 600). Never put API keys in `config.json` or compose.
- Inference requires a virtual key (`enforce_auth_on_inference`).
- MCP tools are deny-by-default on a virtual key; only `VK_NETOPS` is allowed to call the netops client.
- The MCP server cannot write, and it cannot read outside `demo-data`.
- The official Bifrost image has no `npx`/`python`, so this lab does not use STDIO MCP inside that container.
- Pin `pydantic==2.11.7` with `mcp==1.19.0` (newer pydantic breaks that MCP release).
- An Ollama key cannot list both `*` and named models in the same whitelist.
- Do not show keys on screen or in logs.

## OSS versus Enterprise

This lab stays on the public `maximhq/bifrost` image. Virtual keys, budgets, rate limits, caching, MCP, logs, and Prometheus metrics are OSS. Enterprise-only items we did not enable: business units, SSO/SCIM, RBAC, HA mesh, Datadog plugin, scraper API-key auth, projects, and CADF audit packs. SQLite is OSS-only and is what this single-instance lab uses.

## License

Bifrost is Apache 2.0. Sample router output in `mcp-netops/demo-data` is fictional lab data.
