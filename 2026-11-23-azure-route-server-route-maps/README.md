# Control Hybrid Path Selection with Route Maps in Azure Route Server

Terraform topology starter for the **Network Technician** lesson on **Azure Route Server Route Maps** and deterministic hybrid path selection (ExpressRoute primary -> Site-to-Site VPN secondary -> NVAs tertiary).

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
- **Active-Active VPN Gateway (`vpn-gw`)** in `GatewaySubnet` (`10.100.0.0/24`) with BGP enabled (ASN `65515`) and two Local Network Gateways (`192.168.20.1` and `192.168.20.2`, ASN `65020`) configured with the benchmark prefix `10.20.0.0/24` as a static address space; no remote BGP speakers are created
- **Optional ExpressRoute Gateway (`er-gw`)** toggled by `enable_expressroute_gateway = true`
- **Two Linux NVA VMs (`nva100-1`, `nva100-2`)** in `NvaSubnet` (`10.100.2.0/24`) with IP forwarding enabled and BGP connections (`azurerm_route_server_bgp_connection`, ASN `100`) to `rs1`
- **Workload VM (`vm-workload`)** in `WorkloadSubnet` (`10.100.10.0/24`) for effective-route and failover verification

## Prerequisites

- Terraform `>= 1.6.0`
- Azure CLI (`az login` and target subscription selected)
- An SSH public key and lab IPsec pre-shared key (copy `terraform.tfvars.example` to `terraform.tfvars`)

## Before deployment: cost and missing peers

**This starter does not reproduce three-way failover by itself.** Route Server, the VPN gateway, VMs, and associated public IPs can incur charges even when no BGP peers are up. ExpressRoute is disabled by default. Enabling `enable_expressroute_gateway` creates a billable gateway and its public IP, but no ExpressRoute circuit, private peering, or connection to the circuit. Leave the flag off unless you have those lab prerequisites and have approved the cost.

To reproduce the full example, supply and verify these pieces before comparing paths:

- **ExpressRoute:** An operational circuit with Azure private peering, a connection to this VNet gateway, and a peer advertising `10.20.0.0/24`.
- **VPN:** Configured remote IPsec and BGP peers advertising the benchmark prefix. Both shipped Local Network Gateway objects include `var.onprem_prefix` as a static address space. For a BGP-only withdrawal test, first eliminate that static fallback for the benchmark prefix in your lab design and verify that the VPN route was actually learned through BGP.
- **NVAs:** Install and configure a BGP daemon in each Linux guest. Azure creates only its side of the peering. Configure sessions to both Route Server peer IPs, verify the expected advertisement, and configure guest forwarding and a usable next hop and return path. Enabling forwarding on an Azure NIC is not sufficient by itself.
- **Packet test:** Use a reachable endpoint inside the benchmark prefix. Capture the peer-learned routes, the workload NIC's effective routes, and actual traffic before and after a controlled route withdrawal. Route Server exchanges routes; it does not forward the test packets.

Without ExpressRoute, you can test the remaining paths if their peers are configured, but you cannot prove ExpressRoute preference or failover.

## Deploy (only in an authorized lab subscription)

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

3. Check [Route Server effective routes](https://learn.microsoft.com/en-us/azure/route-server/view-route-server-effective-routes) for learned prefixes, origins, and next hops. This is control-plane information, not a packet-delivery test:
```bash
az network vhub get-effective-routes \
  --resource-group rg-ars-routemaps-lab \
  --name rs1 \
  --output json
```

Illustrative baseline, **not measured output from the shipped Terraform**. The following assumes all three transports advertise the same prefix with these AS paths:
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

In your authorized lab subscription, remove the lab resources after testing. Review the destroy plan and account for manually created resources separately; Terraform cannot clean up resources it does not manage.

```bash
terraform destroy
```
