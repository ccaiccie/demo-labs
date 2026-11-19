# Nod (n8n Labs personal AI agent): Windows desktop app + self-hosted Docker server

Video: https://youtu.be/wLwix_CaK4k

Hands-on lab for **[Nod](https://nod.n8n.io)**, the open-source (Apache 2.0) personal agent from n8n Labs, released as a
research preview. Nod gets its own sandboxed computer (shell, files and a real browser), remembers what you tell it,
runs scheduled jobs, and is designed to **ask before it sends, buys or deletes anything you didn't ask for**.

- Docs: https://nod.n8n.io/docs/
- Source: https://github.com/n8n-io/nod
- Version tested: desktop app **v0.8.4** (`nod-v0.8.4`), server built from source at commit `2201eee3`
- Recorded: 2026-11-18

## Lab layout

| Machine | Role | Notes |
| --- | --- | --- |
| Windows desktop ("aidesktop"), standard user | Nod desktop app | **Not a local administrator**, so WSL 2 (and therefore Docker) cannot be installed |
| Windows PC ("MYDELL2") with WSL 2 Ubuntu 24.04 + Docker Engine | Nod self-hosted server (Docker Compose) | Server binds only to `127.0.0.1:4310` |
| Tailscale (private tailnet) | Transport between the two | Small relays on both ends, see below |

```
Nod desktop app ──> http://localhost:4310 (relay.ps1 on the desktop)
                    └─ Tailscale ──> <docker-host-tailscale-ip>:8095 (relay.py, allow-list = desktop's Tailscale IP)
                                     └─> 127.0.0.1:4310  Nod server (Docker Compose in WSL)
```

### Why the server runs on another machine (gotcha #1)

On Windows the desktop app's **Local** mode runs its runtime inside **WSL 2**. On the demo desktop the app's
startup log showed `Local runtime failed. phase=runtime code=NOD_WSL_REQUIRED`, and installing WSL as a standard user fails:

```
PS> winget install --id Microsoft.WSL --source winget --accept-source-agreements --accept-package-agreements
Installer failed with exit code: 0x80073d28 : The package installation failed because administrator
privileges are required. Please contact an administrator to install this package.
```

**WSL/Docker on that desktop needs admin rights**, and the lab deliberately changes no UAC, registry or policy settings.
So the Nod engine runs as a self-hosted Docker server on a second machine that already has WSL 2 + Docker, and the
desktop app uses **Connect to a server**. If you are an administrator, `wsl --install` plus a reboot lets you use Local mode instead.

## 1. Download and verify the Windows installer

1. Download `nod-Setup-x64.exe` (about 358 MB) from https://nod.n8n.io or the
   [v0.8.4 release](https://github.com/n8n-io/nod/releases/tag/nod-v0.8.4).
2. Verify it ([scripts/verify-installer.ps1](scripts/verify-installer.ps1)):

```
SHA256  : 67338CB5C5D118BB34A3E86FC467D04E64BD2302FA1895490F2CD0897C1B8E7E   (matches the GitHub release digest)
Status  : Valid
Signer  : CN=n8n GmbH, O=n8n GmbH, L=Berlin, S=Berlin, C=DE
Admin   : False
```

3. Run it. It is a per-user NSIS installer (installs to `%LOCALAPPDATA%\Programs\nod`, no admin prompt). Unpacking
   takes several minutes. Leave **Run Nod** checked and click **Finish**.

## 2. Self-hosted server (on the Docker host, inside WSL Ubuntu)

Build from source, exactly as in the [self-host docs](https://nod.n8n.io/docs/deploy/self-host/):

```bash
git clone https://github.com/n8n-io/nod.git
cd nod/deployment/self-host
sh setup.sh                         # creates a private .env: NOD_AUTH_TOKEN, NOD_VAULT_KEY, NOD_POSTGRES_PASSWORD (never printed)
docker compose up -d --build --wait # first build takes a while
```

Model provider (no secrets in this repo): append your key to the **server's** private `.env` and restart, so the key never
touches the desktop and never appears on screen:

```bash
chmod 600 .env
# add a line OPENAI_API_KEY=<your key> with an editor (not with echo, so it stays out of shell history)
docker compose up -d --wait
```

Nod then shows an **OpenAI** connection under Settings > Models (default model in this lab: GPT-6.1 Sol). You can
instead connect a provider during onboarding (30+ providers, ChatGPT Plus/Pro sign-in, or local models via Ollama,
LM Studio, vLLM, llama.cpp).

Health check ([scripts/server-check.sh](scripts/server-check.sh) prints variable *names* only):

```
PORT=4310
NOD_BIND_ADDRESS=127.0.0.1
NOD_PUBLIC_URL=http://localhost:${PORT}
SERVICE             STATUS                    PORTS
postgres            Up (healthy)              5432/tcp
runtime             Up
server              Up (healthy)              127.0.0.1:4310->4310/tcp
workspace-network   Up (healthy)
browser             Up (healthy)
workspace           Up
server-1  | Nod is ready at http://localhost:4310
HTTP 200
```

Six containers: PostgreSQL, the server, the runtime, a hardened **workspace** container where Nod runs commands, a
**workspace-network** firewall sidecar, and a dedicated **browser** container. Idle memory was well under 1 GB.

## 3. Connect the desktop to the server

Nod only accepts an **HTTPS** public URL or **plain HTTP on localhost** (`NOD_PUBLIC_URL`), so the docs suggest an SSH
tunnel (`ssh -L 4310:127.0.0.1:4310 user@server`). In this lab SSH to the Windows Docker host was not available, so two tiny relays were used instead:

- On the Docker host: [scripts/relay.py](scripts/relay.py) listens on the host's **Tailscale** address, port 8095, accepts
  only the desktop's Tailscale IP, and forwards to `127.0.0.1:4310`.
  `python relay.py <docker-host-tailscale-ip> 8095 127.0.0.1 4310 <desktop-tailscale-ip>`
- On the desktop (no admin): [scripts/relay.ps1](scripts/relay.ps1) listens on `127.0.0.1:4310` and forwards to the host relay.
  `powershell -ExecutionPolicy Bypass -File relay.ps1 -RemoteHost <docker-host-tailscale-ip>`

Check: `Test-NetConnection <docker-host-tailscale-ip> -Port 8095 -InformationLevel Quiet` returns `True`, and
`(Invoke-WebRequest http://localhost:4310 -UseBasicParsing).StatusCode` returns `200`.

In the app: **Connect to a server** > server address `http://localhost:4310` > paste the `NOD_AUTH_TOKEN` from the server's
`.env` into the masked token field. (The token grants full access to your assistant. Treat it like a password.)
Stop both relays when you are done.

## 4. First run

- Onboarding happens in chat: where you want help (Work), what you do (Engineering), company size (Just me).
- Settings > General: Appearance **Light**, Font size **150%** (Ctrl + / Ctrl = does not zoom the app; use the setting).
- Settings > Models (connections, Add connection list), Voice & audio, Memory (Save new notes, Include sensitive details), Privacy & data (usage-data toggle).

## 5. Prompts used and results

| # | Feature | Prompt | Result |
| --- | --- | --- | --- |
| 1 | Plan + web research | `First give me a 3-step plan, then do it: research the Nod research preview from n8n Labs on the web. When was it released, what license is it under, and which AI providers can it use? Give a short answer with source links.` | 3-step plan, then: released Nov 10 2026 (research preview), Apache License 2.0, OpenAI/ChatGPT, Anthropic, Gemini/Vertex, OpenRouter, Bedrock, Azure OpenAI, Cloudflare, DeepSeek, Groq, Mistral, xAI, OpenAI-compatible and local models, each with a source link |
| 2 | Files + shell | `In your own workspace, create a file called router-hardening.md with a 10-item checklist for securing a home router. Then run a shell command to count its lines and show me where the file is.` | File created and attached in chat with preview; `wc -l` = 12 lines; path `/workspace/<id>/router-hardening.md` (server-side sandbox) |
| 3 | Browser form | `Open https://httpbin.org/forms/post in your browser. It is a public test form. Fill in the pizza order with customer name Network Technician, a medium size, bacon and extra cheese, then submit it and tell me what the server returned.` | Submitted (explicitly requested, so no prompt); showed httpbin's echoed JSON: custname, size medium, toppings bacon + cheese |
| 4 | Caution | `Tidy up your workspace: remove any files you think we no longer need.` | Deleted nothing; kept the checklist and its internal `.nod` folder |
| 5 | Asks before acting | `Find the cheapest registrar price for a .com domain like networktech-lab.com and buy it for me.` | Created a tracked task with a plan (compare, confirm domain with owner, private sign-in/payment), compared IONOS / Spaceship / Namecheap incl. renewal prices, then **stopped and asked which exact domain to buy**. Nothing purchased |
| 6 | Memory | `No need to buy a domain, that was just a test. Please remember this for the future: my YouTube channel is called Network Technician, I make daily videos on AWS, Azure, GCP and network security, and I prefer short answers with source links.` | 4 confirmed notes in Settings > Memory (About you / Preferences / Routines) |
| 7 | Recall | `What do you know about me so far?` | Recalled channel, topics, preference and onboarding answers; noted it doesn't know my name |
| 8 | Scheduling | `Every weekday at 8 AM, check the Nod releases page on GitHub at github.com/n8n-io/nod/releases and tell me in one line if there is a new version.` | Baseline v0.8.4; schedule "Check Nod releases weekdays at 8 AM" (~$1.37-1.55/month est.), with Run now / Edit / Ask Nod / Delete and self-written instructions ("Do not download, install, or update anything") |
| 9 | Rules | Rules button (sends `Show my rules`), then `Add a rule: always ask me before you delete any file or spend any money.` | No rules at first; then "Rule saved" |
| 10 | Approval via rule | `Delete router-hardening.md from your workspace.` then `Yes, go ahead and delete it.` | **"Your rule requires a confirmation before deletion. Should I delete router-hardening.md?"** Deleted only after "yes" and verified |
| 11 | Skills | `Save this as a reusable skill called YouTube description: when I give you a video topic, write a two-sentence description and five hashtags. Then use it for a video about installing Nod.` | Skill `youtube-description` saved (Settings > Memory > Skills shows its steps) and applied |
| 12 | Tour | Apps, Channels, Usage, Vault | Apps: hundreds of integrations + Connect MCP (none connected in this lab). Channels: Telegram, WhatsApp. Usage: per-request cost, ~$1.02 of a $200 limit. Vault: logins and cards (approve each payment with its security code) |
| 13 | Cleanup | Scheduled > trash icon > **Delete schedule** | Recurring job removed so it can't keep billing the API key |

## Gotchas

1. **WSL 2 needs admin.** Local mode on Windows requires WSL 2 (`NOD_WSL_REQUIRED`); a standard user gets `0x80073d28`. Use a self-hosted server or an admin account.
2. **Origin rule.** `NOD_PUBLIC_URL` must be HTTPS or HTTP on `localhost`. Connecting to `http://<lan-ip>:4310` is not allowed; tunnel to localhost instead.
3. **Onboarding stall.** After the last onboarding question the Continue button stayed disabled. **Ctrl+R** (reload) fixed it.
4. **Stalled reply.** A follow-up to a paused purchase task sat on a "thinking" status for minutes. Stopping the task, `docker restart` of the `runtime` and `server` containers, and Ctrl+R recovered it; Nod confirmed nothing was purchased.
5. **Zoom.** Ctrl + / Ctrl = does not zoom the desktop app; use Settings > General > Font size (100/110/125/150%).
6. **Explicit requests are treated as permission.** Asking it to "submit" a form submits it. Approval prompts appear for things you didn't explicitly authorise (e.g. a purchase) or that a rule covers. Add rules such as "always ask me before you delete any file or spend any money".
7. **Schedules cost money.** Each schedule shows an estimated monthly cost on your own API key. Delete demo schedules afterwards.
8. **Secrets.** `.env` holds `NOD_AUTH_TOKEN`, `NOD_VAULT_KEY`, `NOD_POSTGRES_PASSWORD` and your provider key. Keep it `chmod 600`, print only variable names, and never commit it.

## Cleanup

```bash
# on the Docker host (WSL), from nod/deployment/self-host
docker compose down          # stop; add -v ONLY if you also want to delete Nod's data volumes
```

Stop `relay.py` and `relay.ps1`, and uninstall the desktop app from Windows Settings > Apps if you no longer need it.
