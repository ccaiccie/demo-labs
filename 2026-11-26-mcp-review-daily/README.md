# Safe Read-Only Practice Lab: NetBox MCP Server (v1.3.0+)

This practice lab lets a network technician try the official **NetBox Labs `netbox-mcp-server`** safely in read-only mode against an existing lab or demo NetBox instance, then tear down and revoke access cleanly.

- **Intended public repo (when published):** `https://github.com/ccaiccie/demo-labs`
- **Folder name:** `2026-11-26-mcp-review-daily`
- **Official server repository:** `https://github.com/netboxlabs/netbox-mcp-server`

## Prerequisites

1. A non-production or lab NetBox instance you are authorized to query.
2. `uv` / `uvx` installed (`https://docs.astral.sh/uv/`).
3. An MCP-compatible client (such as Claude Desktop, Claude Code, or Codex).

## Security Guardrails Before You Start

- **Run v1.3.0 or later:** `v1.3.0` (Nov 20, 2026) binds pass-through sessions to the NetBox user and rejects malformed tokens. `v1.4.0` (Nov 25, 2026) adds Python 3.15 support and CI updates.
- **Read-only NetBox API token only:** Even though `netbox-mcp-server` only exposes four read-only tools, create a dedicated NetBox API token with **Write enabled = unchecked (read-only)**.
- **Never commit tokens to Git.** Store your token in local environment variables or a local, untracked client config file.

## Step 1: Create a Dedicated Read-Only NetBox API Token

1. Sign in to your lab NetBox UI.
2. Go to **Profile -> API Tokens -> Add a token**.
3. Uncheck **Write enabled** (read-only).
4. Set a clear description such as `mcp-practice-lab-readonly` and an expiration date.
5. Copy the token value into a temporary local note or shell variable.

## Step 2: Launch and Smoke-Test with `uvx`

Run the official server directly without cloning the repo (pinning `>=1.3.0` or `1.4.0`):

### PowerShell (Windows)
```powershell
$env:NETBOX_URL = "https://your-lab-netbox.example.com/"
$env:NETBOX_TOKEN = "your-readonly-netbox-token"
uvx "netbox-mcp-server>=1.3.0"
```

### Bash (Linux / macOS)
```bash
NETBOX_URL="https://your-lab-netbox.example.com/" \
NETBOX_TOKEN="your-readonly-netbox-token" \
uvx "netbox-mcp-server>=1.3.0"
```

Press `Ctrl+C` after confirming the server starts without token or connection errors.

## Step 3: Wire Into Your MCP Client

Copy `mcp-client-config.example.json` into your MCP client configuration and replace the placeholder URL and read-only token.

## Step 4: Safe Read-Only Test Prompts

Once connected, test all four read-only tools:

1. **Get objects with filters (`netbox_get_objects`):**
   - *"List devices in site LAB-01 with status active."*
2. **Get object by ID (`netbox_get_object_by_id`):**
   - *"Show the full NetBox record for device ID 1."*
3. **Search objects (`netbox_search_objects`):**
   - *"Search NetBox for prefix 10.10.0.0/16 or rack R01."*
4. **Read changelogs (`netbox_get_changelogs`):**
   - *"Show the most recent NetBox changelog entries and who made them."*

## Teardown & Cleanup

When you finish testing, remove local credentials and revoke the token:

1. **Remove the `netbox` entry** from your local MCP client config file and restart your MCP client.
2. **Clear shell environment variables:**
   - PowerShell: `Remove-Item Env:NETBOX_URL, Env:NETBOX_TOKEN -ErrorAction SilentlyContinue`
   - Bash: `unset NETBOX_URL NETBOX_TOKEN`
3. **Revoke the API token in NetBox:**
   - Go to **Profile -> API Tokens**, locate `mcp-practice-lab-readonly`, and **Delete** it.
4. *(Optional)* Clear the `uv` cache if you no longer want the package cached locally:
   - `uv cache clean netbox-mcp-server`
