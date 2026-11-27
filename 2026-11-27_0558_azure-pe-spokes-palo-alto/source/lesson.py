"""Private endpoints in spoke VNets forced through a Palo Alto hub: each step = one diagram state + one narration clip."""
from diagrams import BASE

CHAPTERS = ["Intro", "Problem", "Rule", "Flows", "Same spoke", "Symmetry", "Cross spoke", "On-prem", "PAN-OS", "Guardrails", "Lab", "Testing"]
FULL = ["Introduction", "Why traffic bypasses the firewall", "The routing rule that fixes it", "Three flows to cover",
        "Same-spoke traffic", "Keeping the return path symmetric", "Cross-spoke traffic", "On-premises traffic",
        "Palo Alto configuration", "DNS, guardrails and other layouts", "The Terraform test lab", "Testing and troubleshooting"]

STEPS = []


def S(ch, d, add=(), hl=None, say=""):
    STEPS.append(dict(ch=ch, d=d, add=list(add), hl=None if hl is None else list(hl), say=say.strip(), drop=[], all=False))


S(0, "title", ["t1", "t2", "ti1", "ti2", "ti3", "ti4"], [], """
Your private endpoints don't sit in a dedicated network. Each spoke keeps its own, right next to the workloads that use them.
And the requirement is that every connection to them goes through the Palo Alto firewall in the hub. If that's your setup and the traffic keeps skipping the firewall, this lecture is for you.""")
S(0, "title", ["t3"], ["t3"], """
We'll see exactly why the traffic bypasses the firewall, the one routing rule that fixes it, how to keep the return path symmetric, the PAN-OS configuration,
and finally a Terraform lab you can deploy to prove each piece with real tests.""")

S(1, "problem", BASE + ["udr1", "udr2"], ["hub", "fw", "ilb"], """
Here's the topology. The hub, 10.0.0.0/16, has a VM-Series firewall in the trust subnet at 10.0.2.4, behind an internal load balancer with an HA ports rule.
Its frontend, 10.0.2.100, is the next hop for every route we'll write.""")
S(1, "problem", [], ["sp1", "sp2"], """
Two spokes are peered to the hub. Each spoke has an app subnet with a test VM, and a separate subnet just for private endpoints.
Spoke 1 has endpoints for a storage account and a key vault. Spoke 2 has one for its own storage account.""")
S(1, "problem", ["e_byp", "rt"], ["vm1", "pe1b", "e_byp", "rt"], """
Now look at vm1 talking to the blob endpoint in its own spoke. Its effective routes show why the firewall never sees it.
The endpoint created a slash 32 route, next hop InterfaceEndpoint. Everything else in the spoke is VnetLocal. Your default route to the firewall loses to both, because the longest prefix always wins.""")
S(1, "problem", ["why"], ["why"], """
So there are two separate causes. Inside a VNet, subnet-to-subnet traffic is delivered directly, with no appliance in the path.
And each private endpoint injects a slash 32 into its own VNet and into every peered VNet. A default route can never beat a slash 32.""")

S(2, "rule", ["rt"], ["rt"], """
Here's the rule that fixes it. With network policies turned on for the endpoint subnet, a user-defined route can override the endpoint's slash 32,
but only if its prefix is at least as long as the address space of the VNet where the endpoint lives. Spoke 1 is a slash 16.
So 0.0.0.0/0 doesn't work. 10.0.0.0/8 doesn't work either, and that's the one that catches most people. 10.1.0.0/16 works, and so does the endpoint subnet, 10.1.2.0/24.""")
S(2, "rule", ["pol"], ["pol"], """
The switch is a property called privateEndpointNetworkPolicies, and it goes on the subnet that hosts the endpoints, not on the client subnet.
RouteTableEnabled lets routes override the slash 32. NetworkSecurityGroupEnabled makes NSGs apply to the endpoints. Set it to Enabled to get both. In Terraform it's one line on the subnet.""")
S(2, "rule", ["tip"], ["tip"], """
The endpoint subnet route is the sweet spot. It's one route per spoke instead of one per endpoint, so you stay far below the 400 route limit.
App-to-app traffic inside the spoke stays local, and any new endpoint dropped into that subnet is covered automatically.""")

S(3, "flows", BASE, [], """
There are three flows to cover, and each one needs its route in a different place.""")
S(3, "flows", ["f1", "f2", "f3"], ["f1", "f2", "f3"], """
Flow one, a VM reaching an endpoint in its own spoke. Flow two, a VM in spoke 2 reaching the vault endpoint in spoke 1.
Flow three, on-premises clients reaching an endpoint in spoke 2 through the ExpressRoute or VPN gateway.""")
S(3, "flows", ["fl"], ["fl"], """
Same spoke needs the endpoint subnet route on the app subnet. Cross spoke needs the remote spoke's prefix on the app subnet.
On-premises needs the spoke prefixes on a route table attached to the GatewaySubnet. Let's take them one at a time.""")

S(4, "same", BASE + ["udr1", "e_byp"], ["udr1"], """
Flow one. On spoke 1's app subnet, the route table rt-spoke1-app gets a route for 10.1.2.0/24, the endpoint subnet, with next hop 10.0.2.100. Turn off gateway route propagation on it.""")
S(4, "same", ["s1", "s2", "s3", "rt"], ["s1", "s2", "s3", "rt"], """
Now vm1's packet to the blob endpoint goes across the peering to the load balancer, then to the firewall, and from the firewall to the endpoint.
The same table also carries the route to spoke 2 and, if you want internet egress inspected, a default route.""")
S(4, "same", ["eff"], ["eff"], """
Check the effective routes on vm1 again. The endpoint's slash 32 now shows as Invalid, and your slash 24 is the active route.
The VNet's own slash 16 is still VnetLocal, so the app tiers talk to each other directly.""")

S(5, "symm", BASE + ["udr1", "s1", "s2", "s3", "ret"], ["ret", "pe1b"], """
Getting the packet to the firewall is half the job. The endpoint has to reply through the firewall too.
Without help, the endpoint sees vm1's real address and replies straight back inside the spoke. The firewall sees half a conversation and drops the session.""")
S(5, "symm", ["tb"], ["tb", "s3"], """
There are two fixes. One is source NAT on the firewall toward the endpoint subnets, so the endpoint replies to the firewall's trust address.
The other is the disableSnatOnPL tag on the firewall's NICs. The platform then returns endpoint traffic to the firewall and keeps the real client IP, which is nicer for logging.""")
S(5, "symm", ["nsgn", "nsg1"], ["nsgn", "nsg1"], """
Watch the NSG on the endpoint subnet. It matches the source address that arrives at the endpoint.
Allow only the firewall works only when you use SNAT. Without SNAT, the NSG can't tell a firewalled packet from a bypass, so it has to allow the client subnets, and the route becomes your real control.""")

S(6, "cross", BASE + ["udr2", "c1", "c2", "c3"], ["udr2", "c1", "c2", "c3"], """
Flow two, cross spoke. In a plain hub and spoke, the spokes are peered only to the hub, so spoke 2 has no route to spoke 1 at all except the one you give it.
rt-spoke2-app sends 10.1.0.0/16 to the load balancer, and the firewall forwards to the vault endpoint.""")
S(6, "cross", ["cn"], ["cn"], """
The hub learns spoke 1's prefix and every endpoint slash 32 over its peering, so the firewall can reach the endpoints directly.
Add the mirror route on spoke 1, 10.2.0.0/16 to the load balancer, so traffic in the other direction is inspected too.""")
S(6, "cross", ["mesh"], ["mesh"], """
One warning. If spokes are peered directly, or joined in a Virtual Network Manager mesh or connected group, every endpoint slash 32 propagates into the other spokes.
The same rule applies. The route must be at least as long as the remote spoke's VNet prefix, and network policies must be on.""")

S(7, "onprem", BASE + ["gwudr", "o1", "o2", "o3"], ["gwudr", "o1", "o2", "o3"], """
Flow three, on-premises. Traffic arrives at the gateway in the GatewaySubnet. The gateway's effective routes include each spoke prefix and every endpoint slash 32, all learned over peering.
So the GatewaySubnet gets its own route table, rt-gateway, that sends traffic to the firewall.""")
S(7, "onprem", ["gt"], ["gt"], """
Its routes are the spoke address spaces, 10.1.0.0/16 and 10.2.0.0/16, to the load balancer. A single 10.0.0.0/8 route is too short, and the endpoint slash 32s would still win.
Keep gateway route propagation on, and never put a default route on the GatewaySubnet.""")
S(7, "onprem", ["od"], ["od"], """
Two more pieces. The spokes peer with use remote gateways, so on-premises learns their prefixes.
And on-premises DNS forwards the public zones, blob.core.windows.net and vault.azure.net, to the DNS Private Resolver's inbound IP, so names resolve to the endpoint addresses.""")

S(8, "panos", ["pfw", "cfg"], ["cfg"], """
On the firewall, keep it one-armed on the trust interface. Ethernet 1/1 is untrust, ethernet 1/2 is trust.
A static route sends 10.0.0.0/8 out ethernet 1/2 to the subnet gateway, 10.0.2.1. A host route and a management profile answer the load balancer probe from 168.63.129.16.
Then add one security rule from the app subnets to the endpoint subnets, plus the source NAT rule.""")
S(8, "panos", ["why"], ["why"], """
Because traffic enters and leaves on ethernet 1/2, the firewall sees it as trust to trust, which is intrazone. PAN-OS allows intrazone traffic by default, so override intrazone-default to deny and log.
Otherwise any spoke reaches any endpoint and nothing is logged. With two firewalls, the HA ports rule keeps each flow on one firewall in both directions.""")

S(9, "guard", ["g1"], ["g1"], """
Now lock it down so it can't drift. Put an NSG on every endpoint subnet. Use Azure Policy to deny endpoint subnets without network policies.
And don't forget App Service and Functions. Their VNet integration subnet is a client subnet too, so it needs the same route table, with all outbound traffic routed into the VNet.""")
S(9, "guard", ["g2"], ["g2"], """
DNS doesn't change the path, but names must resolve privately. Keep the privatelink zones in one place, link them to the hub or to every spoke,
and point the firewall's own DNS at the resolver so FQDN objects match the private addresses.""")
S(9, "guard", ["g3"], ["g3"], """
And if you can ever move endpoints, there are other layouts. A dedicated endpoint spoke needs just one route and is Microsoft's most scalable pattern.
Virtual WAN with routing intent attracts private traffic to a supported firewall in the virtual hub, with no routes to maintain by hand.""")

S(10, "lab", BASE + ["udr1", "udr2", "nsg1", "nsg2", "gwudr"], [], """
Now let's prove it. The Terraform lab builds exactly this topology: the hub with a VM-Series and the internal load balancer, two spokes with test VMs,
two storage accounts and a key vault with public access disabled, their private endpoints, DNS zones, route tables and NSGs.""")
S(10, "lab", ["files"], ["files"], """
main.tf builds the Azure side. panos/fw-config.set is the firewall configuration you paste into the CLI and commit.
tests/run-tests.sh runs curl from both VMs and shows their effective routes.""")
S(10, "lab", ["tog"], ["tog"], """
Three variables turn it into an experiment. steer_through_firewall adds or removes the endpoint subnet routes. snat_mode switches between firewall SNAT and the disableSnatOnPL tag.
And lock_pe_subnets_with_nsg adds the endpoint subnet NSG.""")

S(11, "test", ["mx"], ["mx"], """
Here's what to expect. With steering on, SNAT and the NSG, both VMs get an HTTP 4xx back. That means TLS reached the endpoint, and the firewall shows each session.
Turn steering off with the NSG still on, and vm1 times out to its own endpoints, because the NSG drops a source that isn't the firewall. Turn the NSG off as well, and you see the bypass.""")
S(11, "test", ["tr"], ["tr"], """
If it doesn't work, check in this order. Network policies on the endpoint subnet, the route prefix length, and the route table on the right subnet.
A session that times out after the firewall means the return path is asymmetric. If names resolve to a public IP, a zone link is missing.
Destroy the lab when you're done, because the firewall is billed by the hour. The diagrams, script and Terraform are in the demo-labs repository. Thanks for watching.""")
