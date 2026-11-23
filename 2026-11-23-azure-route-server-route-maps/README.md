# Control Hybrid Path Selection with Route Maps in Azure Route Server

Terraform practice lab for the **Network Technician** lesson on **Azure Route Server Route Maps** and deterministic hybrid path selection (ExpressRoute primary -> Site-to-Site VPN secondary -> NVAs tertiary).

## Official References

- Microsoft Tech Community blog: [Control hybrid path selection with route maps in Azure Route Server](https://techcommunity.microsoft.com/t5/azure-networking-blog/control-hybrid-path-selection-with-route-maps-in-azure-route/ba-p/4575141)
- Microsoft Learn: [About route maps for Azure Route Server](https://learn.microsoft.com/en-us/azure/route-server/route-maps-about)
- Microsoft Learn: [Configure route maps for Azure Route Server](https://learn.microsoft.com/en-us/azure/route-server/route-maps-configure)
- Microsoft Learn: [Prepend routes by using route maps for Azure Route Server](https://learn.microsoft.com/en-us/azure/route-server/route-maps-prepend)

## What This Lab Builds

In the `hub100` virtual network (`10.100.0.0/16`):

- **Azure Route Server (`rs1`)** in `RouteServerSubnet` (`10.100.1.0/24`) with:
  - `branch_to_branch_traffic_enabled = true` (route exchange enabled)
  - `hub_routing_preference = "ASPath"` (select shortest AS path across all connections)
- **Active-Active VPN Gateway (`vpn-gw`)** in `GatewaySubnet` (`10.100.0.0/24`) with BGP enabled (ASN `65515`) and two Local Network Gateways (`192.168.20.1` and `192.168.20.2`, ASN `65020`) advertising `10.20.0.0/24`
- **Optional ExpressRoute Gateway (`er-gw`)** toggled by `enable_expressroute_gateway = true`
- **Two Linux NVA VMs (`nva100-1`, `nva100-2`)** in `NvaSubnet` (`10.100.2.0/24`) with IP forwarding enabled and BGP connections (`azurerm_route_server_bgp_connection`, ASN `100`) to `rs1`
- **Workload VM (`vm-workload`)** in `WorkloadSubnet` (`10.100.10.0/24`) for effective-route and failover verification

## Prerequisites

- Terraform `>= 1.6.0`
- Azure CLI (`az login` and target subscription selected)
- An SSH public key and lab IPsec pre-shared key (copy `terraform.tfvars.example` to `terraform.tfvars`)

## Deploy

```bash
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your SSH key, PSK, and on-prem lab peer IPs
terraform init
terraform plan
terraform apply
```

## Verify Baseline Routes (Before Route Maps)

1. Check routes learned by the VPN gateway:
```bash
az network vnet-gateway list-learned-routes \
  --resource-group rg-ars-routemaps-lab \
  --name vpn-gw \
  --output table
```

2. Check routes Route Server learns from each NVA (`nva100-1` and `nva100-2`):
```bash
az network routeserver peering list-learned-routes \
  --resource-group rg-ars-routemaps-lab \
  --routeserver rs1 \
  --name nva100-1 \
  --query "RouteServiceRole_IN_0[].{Prefix:network,NextHop:nextHop,SourcePeer:sourcePeer,ASPath:asPath,Weight:weight}" \
  --output table
```

3. Check Route Server effective routes (the authoritative view of Azure-to-on-prem path selection):
```bash
az network vhub get-effective-routes \
  --resource-group rg-ars-routemaps-lab \
  --name rs1 \
  --resource-type RouteTable \
  --resource-id "$(az network routeserver show -g rg-ars-routemaps-lab -n rs1 --query id -o tsv)" \
  --query "value[].{addressPrefixes:join(', ',addressPrefixes),asPath:asPath,nextHopType:nextHopType,nextHops:join(', ',nextHops)}" \
  --output table
```

Before route maps are applied:
- ExpressRoute (`er-gw`): AS path `{12076, 12076}` (length 2)
- VPN (`vpn-gw`): AS path `{65020}` (length 1) — **wins baseline**
- NVAs (`nva100-1`, `nva100-2`): AS path `{100, 65020}` (length 2)

## Apply Inbound Route Maps (Portal / PowerShell)

> **Honest Terraform Provider Gap:** In `hashicorp/azurerm` 4.x, `azurerm_route_server` supports `hub_routing_preference = "ASPath"` and `azurerm_route_server_bgp_connection`, but attaching Route Maps to Azure Route Server ExpressRoute/VPN gateway connections is currently managed through the **Azure Portal** (and BGP peering route maps via Azure Portal or Azure PowerShell `Az.Network 8.2.0+`).

1. **VPN Inbound Route Map (`rm-vpn-in`):**
   - Match condition: Route Prefix `Contains` `10.20.0.0/24` (or match all)
   - Action: `Add` AS Path `65020,65020` (prepends AS 65020 twice -> resulting AS path `{65020, 65020, 65020}`, length 3)
   - Apply in the **Inbound** direction to the **VPN gateway connection** in Route Server `rs1` -> **Route Maps** / **Connections Dashboard**.

2. **NVA Inbound Route Map (`rm-nva-in`):**
   - Match condition: Route Prefix `Contains` `10.20.0.0/24`
   - Action: `Add` AS Path `100,100` (prepends AS 100 twice -> resulting AS path `{100, 100, 100, 65020}`, length 4)
   - Apply in the **Inbound** direction to BGP peerings `nva100-1` and `nva100-2`.

3. **ExpressRoute (`er-gw`):**
   - No route map needed; AS path stays `{12076, 12076}` (length 2), making ExpressRoute Path 1 (primary).

## Guardrails & Reserved ASNs

- Never prepend Azure-reserved ASNs: public `8074`, `8075`, `12076`; private `65515`, `65517`, `65518`, `65519`, `65520`.
- Do not prepend private ASNs on ExpressRoute connections (ExpressRoute strips private ASNs).
- Only 2-byte ASNs are supported by Route Maps.
- Route Server Routing Preference and inbound route maps control **Azure-to-on-premises** traffic only; align on-premises BGP Local Preference to prevent asymmetric routing across stateful firewalls.

## Cost Notes & Cleanup

Azure Route Server, Active-Active VPN Gateway, ExpressRoute Gateway, and VMs incur hourly charges while deployed. Tear down immediately after testing:

```bash
terraform destroy
```
