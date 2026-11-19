# Bifrost demo plan (on-camera script)

Target length: 15–25 minutes. Record later; this is the script for the stack already running on MYDELL2 at `/home/superuser/bifrost-demo`.

Frame: you are a network or security engineer who does not want application teams (or a chatbot) to hold the real OpenAI key, talk to every model, or spend without a cap. Bifrost is an Apache 2.0 OSS LLM/MCP gateway you self-host. One OpenAI-compatible endpoint, virtual keys with budgets and rate limits, a local Ollama fallback, a response cache, Prometheus metrics, request logs, and an MCP tool gateway in front of a read-only folder of sample router output.

Do not record until this checklist is done:

- Grok Bot stays open and minimized. No private desktop, no notifications, no other account sign-in.
- Never `cat .env`, never print `OPENAI_API_KEY`, virtual keys, the setup token, or the admin password. Source `.env` in a hidden terminal or paste the virtual key off-camera into a variable.
- Do not show the Windows Ollama window or other apps. Only the demo terminal and a browser tab to `http://127.0.0.1:8088`.
- Log in to the dashboard as `netops-admin` off-camera or with the password field masked. The password is in `.env` only.
- `VK_LIMITED` may already be at its 2-request hourly cap, and `VK_BUDGET` is currently over a lowered `0.00001` USD cap (so a 402 is immediate). Before recording, either edit those limits in the UI as part of the take, or set the rate-limit window to 1 minute so you can show two successes and a rejection in one take.

Suggested title (under 100 characters): `Bifrost Hands-On: OSS LLM Gateway with Fallback, Virtual Keys and MCP for NetOps`

## 0:00–1:30 — Intro

Say: Bifrost is Maxim AI's open-source LLM and MCP gateway, Apache 2.0, docs at docs.getbifrost.ai. We are on the free OSS image, version 2.6.0, self-hosted in Docker on this lab machine. The only paid API is a small OpenAI key already used in the n8n lab, limited to gpt-4o-mini. A local llama3.2 1B model in official Ollama is the fallback so a provider outage does not go dark.

Show the compose file in the editor (no `.env`). Point at four services: Bifrost on `127.0.0.1:8088`, Ollama and Redis on the internal network only, and a tiny MCP server that can only read a demo folder of interface and syslog samples.

## 1:30–3:00 — Prove it is up, then the UI

In the terminal:

```bash
curl -sS http://127.0.0.1:8088/health
```

Expect `{"status":"ok"}`. Open `http://127.0.0.1:8088`. Log in as `netops-admin` without reading the password aloud. Click through Providers (OpenAI + Ollama), Virtual Keys, Logs, and Settings → Caching so the audience sees the product, not just curl.

Mention: the dashboard and `/metrics` are password-protected. Inference still uses virtual keys, not the admin password, and not the real OpenAI key.

## 3:00–6:00 — OpenAI-compatible drop-in

Source variables off-camera, then:

```bash
# Unified Bifrost path (provider/model)
curl -sS http://127.0.0.1:8088/v1/chat/completions \
  -H "Authorization: Bearer $VK_NETOPS" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-4o-mini",
    "messages": [{"role": "user", "content": "In one sentence, what is a BGP hold timer?"}],
    "max_tokens": 60,
    "temperature": 0
  }'
```

Then the drop-in path an existing OpenAI app would use:

```bash
curl -sS http://127.0.0.1:8088/openai/v1/chat/completions \
  -H "Authorization: Bearer $VK_NETOPS" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "Reply with the single word pong."}],
    "max_tokens": 8,
    "temperature": 0
  }'
```

Show `scripts/sdk_chat.py` (base_url `http://127.0.0.1:8088/openai/v1`, api_key is the virtual key). If you run it, use a venv or a one-off container; do not pip-install system-wide on camera unless it is already ready.

Point out: the app never sees the real OpenAI key. It only has a virtual key you can revoke, scope, and budget.

## 6:00–9:00 — Automatic fallback

```bash
curl -sS -D - http://127.0.0.1:8088/v1/chat/completions \
  -H "Authorization: Bearer $VK_NETOPS" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/this-model-does-not-exist-xyz",
    "fallbacks": ["ollama/llama3.2:1b"],
    "messages": [{"role": "user", "content": "Say hello in five words. Do not call tools."}],
    "max_tokens": 40,
    "temperature": 0
  }'
```

The first try can take ~30 seconds while the local 1B model runs. Walk the response headers: `x-bifrost-provider: ollama`, `x-bifrost-routing-info-is-fallback: true`, `x-bifrost-fallback-index: 1`, original model versus resolved model. Say: this is what you want when a cloud provider is down, rate-limited, or a model name is wrong. Also mention the virtual key already lists OpenAI at weight 1.0 and Ollama at 0.5, so Bifrost can build a fallback chain even without a `fallbacks` array in the body.

## 9:00–12:00 — Cache

```bash
# 1) miss
curl -sS -D - -o /tmp/bf1.json -w "time=%{time_total}\n" \
  http://127.0.0.1:8088/v1/chat/completions \
  -H "Authorization: Bearer $VK_NETOPS" \
  -H "Content-Type: application/json" \
  -H "x-bf-cache-key: netops-lab" \
  -d '{"model":"openai/gpt-4o-mini","messages":[{"role":"user","content":"Name one common cause of an OSPF neighbor stuck in EXSTART, in one short sentence."}],"max_tokens":40,"temperature":0}'

# 2) direct hit — same prompt, should be milliseconds
curl -sS -D - -o /tmp/bf2.json -w "time=%{time_total}\n" \
  http://127.0.0.1:8088/v1/chat/completions \
  -H "Authorization: Bearer $VK_NETOPS" \
  -H "Content-Type: application/json" \
  -H "x-bf-cache-key: netops-lab" \
  -d '{"model":"openai/gpt-4o-mini","messages":[{"role":"user","content":"Name one common cause of an OSPF neighbor stuck in EXSTART, in one short sentence."}],"max_tokens":40,"temperature":0}'

# 3) semantic hit — similar wording
curl -sS -D - -o /tmp/bf3.json -w "time=%{time_total}\n" \
  http://127.0.0.1:8088/v1/chat/completions \
  -H "Authorization: Bearer $VK_NETOPS" \
  -H "Content-Type: application/json" \
  -H "x-bf-cache-key: netops-lab" \
  -H "x-bf-cache-type: semantic" \
  -d '{"model":"openai/gpt-4o-mini","messages":[{"role":"user","content":"In one short sentence, what often causes an OSPF neighbor to stay in the EXSTART state?"}],"max_tokens":40,"temperature":0}'
```

Call out `x-bifrost-cache-hit: true` and `x-bifrost-cache-hit-type: direct` vs `semantic`. In the UI, Settings → Caching. Explain the requirements: Redis Stack (or another vector store), a cache key or a default, and for semantic mode an embedding model. Writes are async, so the first call is always a miss. This is how you cut repeat spend on common netops questions.

## 12:00–16:00 — Virtual keys, rate limits, budgets

In the UI, open Virtual Keys. Show `netops-full`, `netops-rate-limited` (2 requests / window, OpenAI only, no MCP), and `netops-tiny-budget`.

Rate limit (use `$VK_LIMITED`). If the hourly cap is already spent, set the window to 1 minute in the UI first, wait for a reset, or create a fresh limited key on camera.

```bash
for i in 1 2 3; do
  echo "=== call $i ==="
  curl -sS -o /tmp/lim$i.json -w "http=%{http_code}\n" \
    http://127.0.0.1:8088/v1/chat/completions \
    -H "Authorization: Bearer $VK_LIMITED" \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"openai/gpt-4o-mini\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with the single word ok$i.\"}],\"max_tokens\":6,\"temperature\":0}"
  cat /tmp/lim$i.json; echo
done
```

Expect 200, 200, then a 429 / rate-limited body on the third call.

Budget (use `$VK_BUDGET`). The lab key is currently over a 0.00001 USD cap, so one uncached call should 402 immediately:

```bash
curl -sS -D - http://127.0.0.1:8088/v1/chat/completions \
  -H "Authorization: Bearer $VK_BUDGET" \
  -H "Content-Type: application/json" \
  -H "x-bf-cache-no-store: true" \
  -d '{"model":"openai/gpt-4o-mini","messages":[{"role":"user","content":"Reply with the single word ok."}],"max_tokens":8,"temperature":0}'
```

Expect HTTP 402 and `type: budget_exceeded`. Say: always send `x-bf-cache-no-store: true` when you are testing spend, because a cache hit does not add usage and will fool you.

This is the security punchline: a help-desk bot, a ticket workflow, or a junior tool gets a virtual key, not the master credential, and it cannot run away with the bill or call models you did not allow.

## 16:00–18:30 — Metrics and logs

In the UI, open Logs and click a chat request (fallback, cache hit, or the MCP call). Then in the terminal, without printing the password:

```bash
# password is read from the environment, not typed on screen
curl -sS -u "$BIFROST_ADMIN_USERNAME:$BIFROST_ADMIN_PASSWORD" \
  http://127.0.0.1:8088/metrics | grep -E '^bifrost_(cost_total|input_tokens_total|active_requests)' | head
curl -sS -u "$BIFROST_ADMIN_USERNAME:$BIFROST_ADMIN_PASSWORD" \
  'http://127.0.0.1:8088/api/logs?limit=5'
```

Show that unauthenticated `/metrics` is 401. Mention: scraper API-key auth is an Enterprise option; OSS uses the dashboard admin Basic auth (or a later authenticated session). We did not add Grafana here because port 3000 is already taken by the netflow stack.

## 18:30–23:00 — MCP gateway for NetOps

Show `mcp-netops/demo-data/interfaces.txt` (Gi0/2 administratively down). Then:

```bash
curl -sS http://127.0.0.1:8088/mcp \
  -H "Authorization: Bearer $VK_NETOPS" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

Tools are prefixed (`netops-get_interface_brief`, and so on). Then call one:

```bash
curl -sS http://127.0.0.1:8088/mcp \
  -H "Authorization: Bearer $VK_NETOPS" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"get_interface_brief","arguments":{}}}'
```

Finally let the model use the tool:

```bash
curl -sS http://127.0.0.1:8088/v1/chat/completions \
  -H "Authorization: Bearer $VK_NETOPS" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-4o-mini",
    "messages": [{"role": "user", "content": "Use the available tools to read the sample interface brief and tell me which interface is administratively down. One short sentence."}],
    "max_tokens": 80,
    "temperature": 0
  }'
```

Expect: GigabitEthernet0/2 is administratively down. Say: the model never got a shell on the box. Bifrost connected to a local MCP server that can only read a demo folder. That is the pattern for wrapping show commands, a CMDB, or a syslog store without handing the LLM the keys to production.

## 23:00–25:00 — OSS limits and close

Recap: one drop-in endpoint, local fallback, cache, virtual keys with rate limits and budgets, metrics, logs, MCP. All of that is OSS.

What we did not turn on, because it is Enterprise or out of scope: business units, SSO/SCIM, RBAC, HA mesh, the Datadog plugin, scraper API keys, audit-log packs. SQLite is fine for a single OSS instance; Enterprise wants PostgreSQL.

Send people to https://github.com/maximhq/bifrost and https://docs.getbifrost.ai. Lab folder will be `2026-11-19-bifrost` in demo-labs after the video is published. Standard channel close.

## Recording pitfalls (off-camera)

- Do not use port 8080, 3000, 4310, 5678, or 8090; Bifrost is on 8088.
- Do not stop netflow-stack, Nod, n8n, or the Colmena nodes.
- If Bifrost is slow to answer `/health` after a restart, wait; SQLite log migrations can take 20–30 seconds.
- If a cache demo does not hit, wait two seconds after the first call (async write) and confirm the `x-bf-cache-key` header or the default key.
- If Ollama is slow, say so; the 1B model is the point (local, free, fallback), not the quality of the prose.
