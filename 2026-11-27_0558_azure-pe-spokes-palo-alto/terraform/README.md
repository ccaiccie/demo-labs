# Terraform test lab: private endpoints in spoke VNets through a Palo Alto hub

Builds the lecture topology so you can prove, with real traffic, that private endpoint connections from spoke workloads go through the VM-Series. Flip three variables to see the bypass, the asymmetric-return problem, and the NSG behaviour.

> **Cost:** the VM-Series (PAYG bundle license + Standard_D3_v2) is billed by the hour. Run `terraform destroy` when you finish.
> **Status:** `terraform validate` passes with Terraform 1.17.2 and azurerm 4.81.0. It hasn't been deployed end to end in Azure, so treat the first apply as a test run.

## What it deploys

| Network | Subnets | Contents |
|---|---|---|
| Hub 10.0.0.0/16 | snet-mgmt 10.0.0.0/24, snet-untrust 10.0.1.0/24, snet-trust 10.0.2.0/24 | VM-Series (mgmt 10.0.0.4, untrust 10.0.1.4, trust 10.0.2.4), internal Standard LB with HA ports, frontend 10.0.2.100 |
| Spoke 1 10.1.0.0/16 | snet-app 10.1.1.0/24, snet-pe 10.1.2.0/24 | vm1 10.1.1.4, private endpoints for storage account 1 (blob) and the key vault |
| Spoke 2 10.2.0.0/16 | snet-app 10.2.1.0/24, snet-pe 10.2.2.0/24 | vm2 10.2.1.4, private endpoint for storage account 2 (blob) |

Also included: hub-spoke peering (no spoke-to-spoke peering), the `privatelink.blob.core.windows.net` and `privatelink.vaultcore.azure.net` zones linked to all three VNets, and storage accounts and the vault with public network access disabled. Each app subnet gets a route table with BGP propagation off:

| Route | Next hop | Created when |
|---|---|---|
| other spoke's /16 | 10.0.2.100 | always (plain hub-and-spoke) |
| own snet-pe /24 | 10.0.2.100 | `steer_through_firewall = true` |

`snet-pe` has `private_endpoint_network_policies = "Enabled"`, so the /24 route overrides each endpoint's /32. A 10.0.0.0/8 or 0.0.0.0/0 route wouldn't, because the route must be at least as long as the VNet's own prefix.

## Variables you'll change

| Variable | Default | Meaning |
|---|---|---|
| `steer_through_firewall` | `true` | `false` removes the own-PE-subnet routes: same-spoke traffic goes direct |
| `snat_mode` | `firewall_snat` | `disable_snat_on_pl` tags the firewall trust NIC with `disableSnatOnPL=true` and lets the NSG allow the client subnets |
| `lock_pe_subnets_with_nsg` | `true` | NSG on snet-pe: allow TCP 443 from the firewall path, deny other VirtualNetwork sources |

## Deploy

Prerequisites: Azure CLI (logged in), Terraform 1.6 or later, Python 3, and an SSH key.

```bash
az vm image terms accept --publisher paloaltonetworks --offer vmseries-flex --plan bundle1
cp terraform.tfvars.example terraform.tfvars   # fill in subscription, password, SSH key, your IP
terraform init
terraform apply
```

Then configure the firewall (about 10 minutes after the VM boots):

```bash
ssh labadmin@$(terraform output -raw firewall_mgmt_url | sed 's#https://##')
configure
# paste panos/fw-config.set (skip the NAT rule if snat_mode = disable_snat_on_pl)
commit
```

Check that the ILB backend is healthy in the portal (Load balancer > Insights or Metrics > Health Probe Status).

## Test

```bash
./tests/run-tests.sh
```

The script runs `curl https://<fqdn>/` from vm1 and vm2 against all three endpoints, using Run Command. It also prints each VM's effective routes. Any HTTP status means TCP and TLS reached the endpoint; you'll usually get 400 to 404 because there are no credentials. `000` means the connection never completed.

| Setting | vm1 → blob1 / vault (same spoke) | vm2 → vault (cross spoke) | On the firewall |
|---|---|---|---|
| steer = true, firewall_snat, NSG on | HTTP 4xx | HTTP 4xx | sessions for both, source NAT 10.0.2.4 |
| steer = false, NSG on | 000 (NSG drops source 10.1.1.4) | HTTP 4xx | cross-spoke only |
| steer = false, NSG off | HTTP 4xx: **bypass** | HTTP 4xx | cross-spoke only |
| disable_snat_on_pl, steer = true | HTTP 4xx | HTTP 4xx | real client IPs |

Firewall checks:

```
show session all filter destination 10.1.2.4
Monitor > Traffic:  ( addr.dst in 10.1.2.0/24 ) or ( addr.dst in 10.2.2.0/24 )
```

Effective routes on vm1 with steering on: `10.1.2.x/32 InterfaceEndpoint` is **Invalid**, and `10.1.2.0/24 VirtualAppliance 10.0.2.100` is **Active**.

Change a variable and `terraform apply` again to move between rows. Route changes take effect within a minute or two.

## Destroy

```bash
terraform destroy
```

## Files

| File | Purpose |
|---|---|
| `versions.tf` | Terraform and provider versions, provider features |
| `variables.tf` | Inputs and test toggles |
| `main.tf` | All resources |
| `outputs.tf` | Firewall URL, test VM names, endpoint FQDNs and IPs |
| `panos/fw-config.set` | PAN-OS set commands: interfaces, probe profile, zones, routes, rules, NAT, intrazone override |
| `tests/run-tests.sh` | Connectivity and route tests |
