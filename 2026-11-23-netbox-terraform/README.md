# Using Terraform with NetBox to Standardize Network & Firewall Configuration

A beginner-friendly, end-to-end local lab demonstrating how to combine **NetBox** (Network Source of Truth) with **Terraform** (Infrastructure as Code) to manage network inventory, generate standardized multi-vendor firewall configurations, push rules to a live lab firewall, and automatically detect and remediate configuration drift.

## Architecture

```
  Terraform HCL (.tf)
        │
        ├──► e-breuninger/netbox provider ──► NetBox (http://127.0.0.1:8000)
        │                                     Site, VLANs, Prefixes, Devices,
        │                                     Interfaces, IP Addresses
        │
        └──► templatefile() ──► Standardized Firewall Configs
                                 ├── generated/fw-edge-01.nft           (Live Linux nftables)
                                 ├── generated/fw-edge-01-vyos.cfg      (VyOS CLI)
                                 └── generated/fw-edge-01-fortigate.conf (FortiGate CLI)
                                           │
                                           ▼
                                  nb-tf-fw-edge-01 (Live Lab Firewall Container)
```

## Repository Layout

| Path | Purpose |
|---|---|
| `docker/docker-compose.yml` | Runs NetBox (`v4.7-5.1.2`), PostgreSQL 16, Valkey 9.1, NetBox RQ Worker, and `nb-tf-fw-edge-01` (Alpine + `nftables` + `iproute2`). |
| `docker/Dockerfile.firewall` | Builds the lightweight live lab firewall container (`nb-tf-fw-edge-01`). |
| `docker/.env.example` | Sample local environment variables (copy to `docker/.env`). |
| `terraform/versions.tf` | Terraform and provider version constraints (`e-breuninger/netbox ~> 6.0`, `hashicorp/local ~> 2.5`). |
| `terraform/provider.tf` | NetBox provider configuration (reads `NETBOX_SERVER_URL` and `NETBOX_API_TOKEN` from environment). |
| `terraform/variables.tf` | Input variables for Site, VLANs, RFC 5737 Prefixes, Gateway IPs, and Firewall Policies. |
| `terraform/netbox_inventory.tf` | Declares Site, VLANs, Prefixes, Manufacturers, Device Types, Device Roles, Devices (`fw-edge-01`, `sw-core-01`), Interfaces, and IP Addresses in NetBox. |
| `terraform/firewall_config.tf` | Builds normalized address objects & policies from NetBox resources, renders `nftables`, VyOS, and FortiGate configs, and applies the live `nftables` ruleset to `nb-tf-fw-edge-01`. |
| `terraform/templates/` | `nftables.tftpl`, `vyos.tftpl`, and `fortigate.tftpl` templates. |
| `terraform/outputs.tf` | Summary outputs for Site, Prefixes, Firewall Interfaces, and generated config paths. |
| `scripts/load-env.sh` | Exports `NETBOX_SERVER_URL` and `NETBOX_API_TOKEN` from `docker/.env` without printing secrets. |
| `scripts/apply-firewall.sh` | Validates (`nft -c -f`) and applies (`nft -f`) the generated ruleset + interface IPs on `nb-tf-fw-edge-01`. |
| `scripts/check-firewall.sh` | Displays live interfaces and `nftables` ruleset on `nb-tf-fw-edge-01`. |
| `scripts/simulate-drift.sh` | Simulates out-of-band manual drift in NetBox and injects a rogue Telnet rule on `nb-tf-fw-edge-01`. |
| `INSTALL_LOG.md` | Step-by-step installation log on MYDELL2. |

## Quick Start

### 1. Start NetBox and the Lab Firewall
```bash
cd docker
cp .env.example .env   # edit passwords/tokens if desired
docker compose up -d --build
```
Wait for `nb-tf-netbox` to report `healthy` (first-time DB migration takes ~3-5 minutes; subsequent restarts take ~15 seconds):
```bash
docker ps --filter "name=nb-tf-"
```
Open NetBox in your browser at `http://127.0.0.1:8000` (user: `admin`).

### 2. Initialize and Apply Terraform
```bash
source scripts/load-env.sh
cd terraform
terraform init
terraform plan
terraform apply -auto-approve
```

### 3. Inspect Generated Configs and Live Firewall
```bash
cat terraform/generated/fw-edge-01.nft
cat terraform/generated/fw-edge-01-vyos.cfg
cat terraform/generated/fw-edge-01-fortigate.conf
bash scripts/check-firewall.sh
```

### 4. Demonstrate Configuration Drift & Remediation
```bash
bash scripts/simulate-drift.sh
bash scripts/check-firewall.sh   # notice ROGUE_MANUAL_TELNET rule
cd terraform
terraform plan                   # Terraform detects the manual NetBox drift
terraform apply -auto-approve    # Restores NetBox and re-applies clean firewall rules
bash ../scripts/check-firewall.sh
```

## Cleanup
```bash
cd docker
docker compose stop
# Or to remove containers and volumes completely:
# docker compose down -v
```
