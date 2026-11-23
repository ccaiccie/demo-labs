# Install Log — MYDELL2 (NetBox + Terraform + Lab Firewall)

Date: 2026-11-22  
Host: MYDELL2 (Windows 11 + WSL2 Ubuntu-24.04)  
Workspace: `E:\antigravity\netbox-terraform`

## 1. Pre-Existing Local Tools Verified
- **Windows Terraform**: `Terraform v1.17.2` (`windows_amd64`) — already installed via WinGet.
- **WSL2 Ubuntu-24.04**: `Linux MYDELL2 6.6.87.2-microsoft-standard-WSL2`, Python 3.12.3.
- **Docker Engine (in WSL2)**: `Docker version 29.9.3`, `Docker Compose version v5.7.0`.
- **Cached Official NetBox Image**: `netboxcommunity/netbox:v4.7-5.1.2` (`v4.7.5-5.1.2`), `postgres:16-alpine`, `valkey/valkey:9.1-alpine`, `alpine:3.22`.
- **Port Check**: Verified `8080` (netflow-goflow2), `8081` (nautobot), `8088` (listening), `8443` (pentagi), `5432` (pgvector) are in use. Selected `127.0.0.1:8000` for NetBox (free) and kept PostgreSQL/Valkey internal to the Docker Compose network.

## 2. Terraform CLI Installed in WSL2
Installed official HashiCorp Linux amd64 binary into `~/.local/bin/terraform` inside WSL2 Ubuntu-24.04 so `docker` and `terraform` run in the same POSIX shell:
```bash
mkdir -p ~/.local/bin
curl -fsSL https://releases.hashicorp.com/terraform/1.17.2/terraform_1.17.2_linux_amd64.zip -o /tmp/terraform.zip
python3 -m zipfile -e /tmp/terraform.zip ~/.local/bin
chmod +x ~/.local/bin/terraform
rm -f /tmp/terraform.zip
~/.local/bin/terraform version
# Output: Terraform v1.17.2 on linux_amd64
```
Note: `unzip` was not installed in Ubuntu-24.04; used `python3 -m zipfile -e` cleanly instead.

## 3. Terraform Providers Installed (`terraform init`)
Initialized `terraform/` with:
- `e-breuninger/netbox` `v6.0.1`
- `hashicorp/local` `v2.9.1`

## 4. Docker Compose Stack (`docker/docker-compose.yml`)
Deployed:
- `nb-tf-netbox` (`netboxcommunity/netbox:v4.7-5.1.2`) on `http://127.0.0.1:8000`
- `nb-tf-worker` (`netboxcommunity/netbox:v4.7-5.1.2` running `rqworker`)
- `nb-tf-postgres` (`postgres:16-alpine`) on native Docker volume `netbox-postgres-data`
- `nb-tf-redis` & `nb-tf-redis-cache` (`valkey/valkey:9.1-alpine`)
- `nb-tf-fw-edge-01` (custom `alpine:3.22` + `nftables` + `iproute2` + `tcpdump` + `bash` + `curl`, `NET_ADMIN` capability) acting as the live edge firewall target.

## 5. Issues Encountered & Fixes (Phase A Off-Camera)
1. **Docker internal NAT table in `nftables`**: `flush ruleset` inside the firewall container would remove Docker's `table ip nat` DNS rules. Fixed by scoping `templates/nftables.tftpl` to `table inet lab_fw` + `delete table inet lab_fw` before recreating `table inet lab_fw`.
2. **CRLF line endings on Windows-authored shell scripts**: Stripped `\r` with `sed -i 's/\r$//'` before building/running inside Alpine and WSL2.
