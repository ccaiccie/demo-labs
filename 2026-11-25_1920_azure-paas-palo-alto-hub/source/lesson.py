"""Lecture script: each step = one diagram state + one narration clip."""

CHAPTERS = ["Intro", "Topology", "Options", "A Public", "B Svc EP", "C PE + DNS", "C Routing",
            "C PAN-OS", "D Injection", "E Outbound", "F Inbound", "G NSP", "H Platform", "Defense", "Decide"]

STEPS = []  # dicts


def S(ch, d, add=(), hl=None, say="", drop=(), all_=False):
    STEPS.append(dict(ch=ch, d=d, add=list(add), hl=None if hl is None else list(hl), say=say.strip(), drop=list(drop), all=all_))


# ---------------------------------------------------------------- 0 intro
S(0, "title", ["t1"], [], """
Welcome. In this lecture we're going to secure Azure platform services, things like Azure SQL, Storage and Key Vault,
behind a Palo Alto Networks firewall that sits in a hub virtual network.""")
S(0, "title", ["t2", "ti1", "ti2", "ti3", "ti4", "ti5", "ti6"], [], """
PaaS services are different from virtual machines. They don't live in your network by default. They have public endpoints
on the Microsoft backbone, and you have to choose how, or whether, your traffic to them goes through your firewall.""")
S(0, "title", ["t3"], ["t3"], """
So we'll walk through every option: public endpoints with IP rules, service endpoints, private endpoints,
VNet injection, VNet integration for outbound traffic, publishing apps inbound, and the Network Security Perimeter.
Then we'll compare the Palo Alto form factors, VM-Series and Cloud NGFW, and finish with a decision guide.
Along the way we'll go deep on the part that trips most people up: the routing and DNS that actually force PaaS traffic through the firewall.""")

# ---------------------------------------------------------------- 1 topology
S(1, "topo", ["hub"], ["hub"], """
Let's start with the reference topology we'll use for the whole lecture. In the middle is the hub virtual network, 10.0.0.0/16.
Everything shared lives here: the firewalls, the gateways and DNS.""")
S(1, "topo", ["suntr", "strust", "smgmt", "fw1", "fw2", "pano"], ["fw1", "fw2", "suntr", "strust", "smgmt"], """
Two Palo Alto VM-Series firewalls sit across three subnets. The management interface is in snet-mgmt, managed by Panorama.
Ethernet 1/1 is in the untrust subnet, facing the internet. Ethernet 1/2 is in the trust subnet, facing everything private:
the spokes, on-premises, and the private endpoints.""")
S(1, "topo", ["ilb", "e_ilbfw1", "e_ilbfw2", "plb", "pip", "inet", "e_inet", "e_plbfw"], ["ilb", "e_ilbfw1", "e_ilbfw2", "plb", "e_plbfw", "inet"], """
In Azure you don't run firewalls with a shared virtual MAC like on-premises. Instead you put Azure load balancers around them.
A public load balancer distributes inbound internet traffic to the untrust interfaces.
An internal Standard load balancer with an HA ports rule, frontend 10.0.2.100, distributes all private traffic to the trust interfaces.
That frontend IP is the next hop that every route in this lecture points to.""")
S(1, "topo", ["onprem", "users", "opdns", "er", "sgw", "gw", "e_op", "e_er", "e_gwilb"], ["onprem", "er", "gw", "e_gwilb"], """
On the left is on-premises, 172.16.0.0/16, connected with ExpressRoute or VPN to a gateway in the GatewaySubnet of the hub.
Traffic from on-premises arrives at that gateway, and we'll steer it to the firewall's internal load balancer.""")
S(1, "topo", ["sdns", "resolver", "zones"], ["resolver", "zones"], """
At the bottom is DNS. An Azure DNS Private Resolver gives on-premises a target IP, 10.0.3.4, that can query Azure private DNS zones.
And the private DNS zones, the privatelink zones, hold the private IP addresses of our PaaS resources. Keep these two in mind; DNS is half of this story.""")
S(1, "topo", ["sp1", "vm", "app", "udr1", "e_p1"], ["sp1", "udr1", "e_p1"], """
On the right, spoke one holds workloads: a VM at 10.1.1.10 and an App Service app. The spoke is peered to the hub,
and its route table sends the default route to the internal load balancer at 10.0.2.100.""")
S(1, "topo", ["sp2", "pesql", "peblob", "pekv", "udr2", "e_p2", "paas", "sql", "blob", "kv", "e_pl"], ["sp2", "paas", "e_pl", "pesql", "peblob", "pekv"], """
Spoke two holds private endpoints: SQL at 10.2.1.4, blob storage at 10.2.1.5 and Key Vault at 10.2.1.6.
Each private endpoint connects over Private Link to the real PaaS resource on the far right.
The goal of this lecture is simple to say and tricky to do: every flow to those PaaS resources, from spokes, from on-premises,
and from the PaaS services themselves, should be inspected and logged by the Palo Alto firewalls.""")

# ---------------------------------------------------------------- 2 options map
S(2, "options", ["oA", "oAi", "oB", "oBi", "oC", "oCi", "oD", "oDi"], [], """
Here's the map of options. The top row is about how your clients reach a PaaS resource.
Option A: keep the public endpoint and lock it down to the firewall's egress IP.
Option B: service endpoints. Option C: private endpoints, which is the main event and the default for production.
Option D: VNet injection, where a dedicated version of the service runs inside your own subnet.""")
S(2, "options", ["oE", "oEi", "oF", "oFi", "oG", "oGi", "oH", "oHi"], ["oE", "oF", "oG", "oH"], """
The bottom row covers the other directions and the platform choice.
Option E: outbound traffic from PaaS, like an App Service calling the internet or your database.
Option F: inbound publishing, getting internet users to an app safely.
Option G: the Network Security Perimeter, for the public side of PaaS that can't go private.
And H: which Palo Alto form factor carries all of this. These options aren't exclusive; a real design usually combines C, E and F.""")

# ---------------------------------------------------------------- 3 option A
S(3, "public", ["sp1", "vm", "udr", "hub", "ilb", "fw", "pip", "e1", "e2", "e3"], ["vm", "ilb", "fw", "pip", "e1", "e2", "e3"], """
Option A: the public endpoint. The App VM resolves the storage account's normal public name and connects to a public IP.
Its default route sends the packet to the internal load balancer, the VM-Series inspects it, and then source-NATs it to the firewall's egress public IP,
20.55.10.7, out of the untrust interface.""")
S(3, "public", ["bb", "e4", "stg", "blob", "rules", "e5"], ["bb", "e4", "e5", "blob", "rules"], """
The packet travels the Microsoft backbone to the storage account's public endpoint. On the storage account,
under Networking, you set public access to selected networks and add one IP rule: allow 20.55.10.7.
Because every request now carries the firewall's address, only traffic that went through your firewall is accepted.""")
S(3, "public", ["bad", "e6"], ["bad", "e6"], """
Anyone else on the internet hits the same endpoint and is refused by the IP rule. On the firewall side, you can use App-ID,
URL filtering on the storage account's FQDN, and Threat Prevention, because the flow is plain HTTPS leaving through your egress.""")
S(3, "public", ["pc"], ["pc"], """
The upside: no DNS changes, and it works with every service. The downsides are real, though. The endpoint stays internet-facing.
Every workload behind the firewall shares that one source IP, so the IP rule trusts all of them equally.
There's no private path from on-premises. And unless the firewall restricts which storage accounts can be reached, data can be copied to anyone else's account.
Use it as a stepping stone, or for services that don't support Private Link.""")

# ---------------------------------------------------------------- 4 option B
S(4, "svcep", ["bad", "bsub", "bvm", "bfw", "bblob", "b2"], ["bad", "bsub", "b2"], """
Option B: virtual network service endpoints. A service endpoint extends your subnet's identity to a service like Storage or SQL,
so the service can say: only accept traffic from this subnet. Traffic still goes to the public endpoint, but over an optimized backbone route,
and the source is your private address. The classic mistake is turning the endpoint on in the workload subnet.""")
S(4, "svcep", ["b1", "brt"], ["b1", "brt"], """
Look at the effective routes. The default route points at the firewall, but enabling the service endpoint adds the service's prefixes
with a next hop of VirtualNetworkServiceEndpoint. Those prefixes are more specific than the default route, so they win.
Storage traffic leaves directly and never touches the Palo Alto. You've just built a firewall bypass.""")
S(4, "svcep", ["good", "gvm", "gsub", "gfw", "gblob", "g1", "g2"], ["good", "gsub", "g1", "g2"], """
The right way: leave service endpoints off in the spokes, and enable them on the subnet where traffic leaves the firewall.
For a VM-Series that's the untrust subnet, the egress interface. The spoke sends traffic to the firewall with its default route,
the firewall inspects it, source-NATs to its untrust interface, and forwards it out to the storage service through the endpoint.""")
S(4, "svcep", ["grt"], ["grt"], """
Now the storage firewall gets a virtual network rule that allows only the hub's untrust subnet. The Palo Alto does the per-workload control
with App-ID and URL filtering. And add a service endpoint policy to that subnet, so traffic through it can only reach storage accounts you list.
That's your guard against exfiltration to someone else's account.""")
S(4, "svcep", ["lim"], ["lim"], """
Limits to remember: it's still the public endpoint and public DNS. On-premises can't use a service endpoint at all.
The service trusts the whole firewall subnet, so all control lives on the firewall policy. And only a subset of services support it.
Service endpoints are a fine, cheap option for Azure-only access to a few services, but for most production work, we move on to private endpoints.""")

# ---------------------------------------------------------------- 5 option C anatomy + DNS
S(5, "pe", ["vnet", "spe", "pe", "nic", "stg", "blob", "e_pl"], ["pe", "nic", "e_pl", "blob"], """
Option C: private endpoints. A private endpoint is a network interface in your subnet with a private IP, here 10.2.1.5,
that maps to one specific resource, and one sub-resource: this storage account's blob service.
Behind the scenes, Private Link carries the traffic to the service over the Microsoft backbone.
And because the endpoint maps to one resource, not to the whole service, it gives you built-in protection against data going to some other account.""")
S(5, "pe", ["pna"], ["pna"], """
On the resource, the endpoint connection must be approved, and then you set public network access to disabled.
That second step matters: creating a private endpoint does not close the public endpoint by itself. You need both.
Storage needs one endpoint per sub-resource, so blob, dfs, file, queue, table and web are separate endpoints if you use them.""")
S(5, "pe", ["sapp", "vm", "n1", "n2"], ["vm", "n1", "n2"], """
Now DNS, because applications keep using the normal name. The app looks up stgdemo dot blob dot core dot windows dot net.
Public DNS answers with a CNAME to the privatelink name: stgdemo dot privatelink dot blob dot core dot windows dot net.
That redirection happens for everyone in the world, the moment the private endpoint exists.""")
S(5, "pe", ["zone", "n3", "e_vmpe"], ["zone", "n3", "e_vmpe"], """
If the asking VNet is linked to the private DNS zone privatelink dot blob dot core dot windows dot net, the zone answers with an A record:
10.2.1.5. The client connects to a private IP, and nothing in the application changes.""")
S(5, "pe", ["n4"], ["n4"], """
Anyone not linked to the zone follows the CNAME to the public IP, and is refused because public access is off.
So when a private endpoint "doesn't work", the first question is always: did the client get the private IP?""")
S(5, "dns", ["hub", "res", "azdns", "zones", "d3", "d4"], ["res", "azdns", "zones", "d3", "d4"], """
In a hub-and-spoke design we centralize that DNS. The privatelink zones are linked to the hub. The DNS Private Resolver's inbound endpoint, 10.0.3.4,
sends queries to Azure DNS at 168.63.129.16, which consults the linked zones and returns the private IP.""")
S(5, "dns", ["onprem", "client", "opdns", "d1", "d2"], ["client", "opdns", "d1", "d2"], """
On-premises, the client asks its normal DNS server. That server has a conditional forwarder for the public zone, blob dot core dot windows dot net,
pointing at 10.0.3.4 across ExpressRoute or VPN. Forward the public zone name, not just the privatelink zone, because the client asks for the public name.
On-premises servers can't reach 168.63.129.16 directly, which is exactly why the resolver's inbound endpoint exists.""")
S(5, "dns", ["fw", "d5"], ["fw", "d5"], """
The firewall needs DNS too. If you build FQDN address objects on the Palo Alto, set the firewall's DNS server to the resolver,
so the FQDN resolves to the private IP. Otherwise the firewall resolves the public IP and your rule never matches the real traffic.""")
S(5, "dns", ["spk", "svm", "sopt", "d6"], ["svm", "sopt", "d6"], """
For the spokes you have three choices. Point their custom DNS at the resolver for one central path.
Or keep Azure-provided DNS and link the zones, or a forwarding ruleset, to each spoke.
Or point spokes at the firewall's DNS proxy, which forwards to the resolver, so every lookup is logged and filtered.""")
S(5, "dns", ["warn"], ["warn"], """
The common gotchas: forwarding only privatelink zones on-premises, pointing on-premises at 168.63.129.16, and letting every team create
its own copy of the privatelink zones. Keep one set per environment and let Azure Policy register the records automatically.""")

# ---------------------------------------------------------------- 6 routing
S(6, "route", ["sp1", "vm", "hub", "ilb", "fw", "sp2", "pe"], [], """
Now the heart of the lecture: forcing private endpoint traffic through the Palo Alto.
The App VM in spoke one wants to reach the private endpoint 10.2.1.5 in spoke two. Spoke one has a default route to the firewall. You'd think that's enough. It isn't.""")
S(6, "route", ["rtb", "byp"], ["rtb", "byp"], """
Look at the effective routes on the app subnet. There's our default route to 10.0.2.100. There's the peering route to spoke two, 10.2.0.0/16.
And there's a slash 32 route for 10.2.1.5 with next hop InterfaceEndpoint, injected by the private endpoint and propagated across the peering.
Longest prefix wins, so the slash 32 beats everything. The traffic goes straight to the endpoint and the firewall never sees it.""")
S(6, "route", ["pol"], ["pol"], """
The fix has two parts. Part one: on the subnet that hosts the private endpoints, enable private endpoint network policies.
The property is privateEndpointNetworkPolicies, set to RouteTableEnabled, or Enabled, which turns on both route tables and network security groups.
Network policies are off by default, and this setting affects every endpoint in that subnet.""")
S(6, "route", ["rta", "r1", "r2", "r3"], ["rta", "r1", "r2", "r3"], """
Part two: on the client subnet, add a user-defined route for the private endpoint range to the firewall. The rule is that the route must be
at least as specific as the address space of the VNet that holds the endpoint. Here that's 10.2.0.0/16 to 10.0.2.100.
With network policies on, that route overrides the slash 32. A default route alone will never do it.
Now the flow goes VM, internal load balancer, VM-Series, private endpoint.""")
S(6, "symm", ["sp1", "vm", "hub", "ilb", "fw1", "fw2", "sp2", "pe", "f1", "f2", "f3"], ["f1", "f2", "f3", "fw1"], """
Getting there is half the job. Now the return path. The request leaves FW1 with the original source, 10.1.1.10, to 10.2.1.4.""")
S(6, "symm", ["ret"], ["ret"], """
The private endpoint's data plane doesn't follow your route tables for its replies the way a VM would. The reply can head straight back to 10.1.1.10,
skipping the firewall, or land on the other firewall. Either way the firewall sees half a session and drops it as asymmetric.""")
S(6, "symm", ["snat", "o1"], ["snat", "o1", "fw1", "pe"], """
Option one, the classic answer: source NAT on the firewall. FW1 rewrites the source to its trust interface, 10.0.2.4.
The endpoint replies to 10.0.2.4, which can only be FW1, so the session is always symmetric.
The cost is that the PaaS logs show the firewall's address; you correlate with the firewall's traffic log to find the real client.""")
S(6, "symm", ["o2", "o3"], ["o2", "o3"], """
Option two: Microsoft now lets you drop that SNAT requirement. Add a tag named disableSnatOnPL, value true, to each firewall dataplane NIC,
or to each scale set instance. The tag is case-sensitive, and it causes a one-time reset of private endpoint flows, so do it in a maintenance window.
Either way, keep both directions on the same internal load balancer frontend, so HA ports hashing sends the flow and its reply to the same firewall.""")
S(6, "place", ["p1", "p1h", "p1fw", "p1a", "p1vm", "p1p", "p1pe1", "p1pe2", "p1e1", "p1e2", "p1n"], ["p1"], """
Where should the private endpoints live? Pattern one, which we've been using: a dedicated private endpoint spoke.
Application subnets get one route, 10.2.0.0/16 to the load balancer. DNS zone groups, NSGs and firewall address objects all live in one place,
and the security zone boundary is obvious. It scales well; you just need clear ownership of that shared VNet.""")
S(6, "place", ["p2", "p2h", "p2fw", "p2s", "p2pe", "p2a", "p2vm", "p2e1", "p2e2", "p2n"], ["p2"], """
Pattern two: endpoints in a subnet in the hub. Spokes route 10.0.4.0/24 to the load balancer, which is more specific than the hub space, so it works,
and the GatewaySubnet needs the same route for on-premises. Fewer VNets, but the hub grows, and anything else in the hub reaches the endpoints directly.""")
S(6, "place", ["p3", "p3s", "p3a", "p3vm", "p3p", "p3pe", "p3h", "p3fw", "p3e1", "p3e2", "p3n"], ["p3"], """
Pattern three: the endpoint inside the workload spoke, next to the app. Now it's subnet-to-subnet inside one VNet. You add a route on the app subnet
for the endpoint subnet, 10.1.5.0/24, to the load balancer, plus network policies on the endpoint subnet, and traffic hairpins through the hub.
It gives app teams ownership, but it's the easiest to forget, and DNS and policy sprawl across spokes. Most enterprises use pattern one, with pattern three as the exception.""")
S(6, "hybrid", ["onprem", "users", "er", "hub", "sgw", "gw", "sp2", "pe", "h0", "h1", "hb"], ["gw", "hb"], """
Now on-premises. A client at 172.16.5.20 connects over ExpressRoute. The gateway learns the spoke prefixes through peering,
so by default it sends traffic straight to the endpoint, bypassing the firewall.""")
S(6, "hybrid", ["gwudr", "ilb", "fw", "h2", "h3", "h4", "pol"], ["gwudr", "h2", "h3", "h4", "pol"], """
Associate a route table with the GatewaySubnet: 10.2.0.0/16 to 10.0.2.100. With network policies on the endpoint subnet, the slash 32 doesn't bypass it.
Now on-premises traffic goes gateway, load balancer, firewall, endpoint.""")
S(6, "hybrid", ["ret"], ["ret"], """
For the return, the firewall routes 172.16.0.0/16 out of its trust interface toward the gateway, and SNAT or the disableSnatOnPL tag keeps the endpoint side symmetric.
Two rules for GatewaySubnet route tables: never put a default route there, and don't disable gateway route propagation on it.""")

# ---------------------------------------------------------------- 7 PAN policy
S(7, "panpol", ["fw", "ifc"], ["ifc"], """
Let's configure the Palo Alto side. Interfaces: ethernet 1/1 untrust at 10.0.1.4 in zone UNTRUST, ethernet 1/2 trust at 10.0.2.4 in zone TRUST.
Static routes: the default route out of ethernet 1/1 to the untrust subnet's gateway, 10.0.1.1. All private ranges, the spokes and on-premises, out of ethernet 1/2 to 10.0.2.1.
And a route for 168.63.129.16 out of each interface to its own subnet gateway, because that's the load balancer health probe source,
plus an interface management profile allowing HTTPS only from that address, so the probes see the firewall as healthy.""")
S(7, "panpol", ["obj"], ["obj"], """
Objects: static address objects for each endpoint, or FQDN objects that resolve to private IPs because the firewall uses the resolver.
With Panorama, the Azure plugin pulls VNet, subnet and tag information from your subscriptions into Dynamic Address Groups,
so rules follow workloads as they change. And a custom URL category listing your storage and Key Vault names lets you match on the TLS server name
without decrypting.""")
S(7, "panpol", ["rules"], ["rules"], """
The security policy. Rule one allows the app subnet to the SQL endpoint with App-ID mssql-db and full threat profiles.
A note on SQL: the Proxy connection policy uses only port 1433; Redirect through a private endpoint needs a much wider port range,
so either open that range to the SQL endpoint only, or set Proxy. Rule two allows the app to blob over SSL, limited to your accounts.
Rule three allows on-premises to Key Vault. Rule four denies and logs anything else to the endpoint subnets.
Then two things people miss. Spoke-to-spoke traffic enters and leaves the same trust interface, so it's intrazone; override the intrazone default rule to deny and log.
And a NAT rule source-translates traffic to the endpoint subnets, unless you've used the disableSnatOnPL tag. TLS decryption is possible for HTTPS where clients trust your CA,
but SQL wraps TLS inside its own protocol, so control it with App-ID and addresses.""")

# ---------------------------------------------------------------- 8 VNet injection
S(8, "inject", ["hub", "ilb", "fw", "sp", "pe1", "s1", "sqlmi", "s2", "ase", "s3", "apim"], ["s1", "s2", "s3"], """
Option D: VNet injection. Some services have a dedicated tier that deploys into your own subnet: SQL Managed Instance,
App Service Environment version 3, API Management in injected mode, AKS, Databricks. Once they're in your subnet, they behave much like VMs.
A route table sends their traffic to the firewall, and other spokes reach them through the firewall like any other workload.""")
S(8, "inject", ["rules", "mgmt", "m1", "hubn", "aks"], ["rules", "mgmt", "m1", "hubn"], """
The catch is the management plane. Each service has documented routes and NSG rules it needs to talk to Azure's control plane.
SQL Managed Instance even uses service-aided subnet configuration that adds its own routes and rules; don't fight them.
On the firewall, allow each service's documented dependencies, like Entra ID, monitoring and storage, and for AKS the container registries,
and deny and log everything else. Injection gives the strongest isolation, at the highest cost and complexity.""")

# ---------------------------------------------------------------- 9 outbound
S(9, "egress", ["apps", "app", "flag"], ["app", "flag"], """
Option E covers the other direction: traffic that starts in a PaaS service. Multi-tenant App Service and Functions don't live in your VNet,
so by default their outbound calls go straight to the internet. VNet integration fixes that.""")
S(9, "egress", ["sp", "sint", "udr", "hub", "ilb", "fw", "x1", "x2", "x3"], ["sint", "udr", "x1", "x2", "x3"], """
You give the app a delegated integration subnet, delegated to Microsoft dot Web slash serverFarms, and turn on route all, which in the current API is outboundVnetRouting dot allTraffic.
Now all outbound traffic, including configuration traffic like image pulls, content share access, backups and managed identity token requests, enters the subnet.
A default route on that subnet sends it to the firewall.""")
S(9, "egress", ["inet", "paas", "sql", "kv", "x4", "x5"], ["x4", "x5", "inet", "paas"], """
The VM-Series applies App-ID and URL filtering to internet calls and source-NATs them to its public IP,
and calls to SQL or Key Vault go to their private endpoints, through the same routing we just built.""")
S(9, "egress", ["notes"], ["notes"], """
Remember to allow 443, and 445 if the app uses a content share, from the integration subnet. And VNet integration is outbound only:
users reaching the app still need a private endpoint or one of the inbound patterns next. Functions Premium and Flex, Logic Apps Standard and Container Apps follow the same idea.""")

# ---------------------------------------------------------------- 10 inbound
S(10, "inbound", ["r1", "u1", "afd", "fw1", "app1", "a1", "a2", "n1"], ["r1"], """
Option F: publishing an app to the internet. Pattern one: Azure Front Door Premium with a Private Link origin.
Front Door's WAF and edge absorb the internet, and it reaches the App Service over a Microsoft-managed private endpoint that you approve on the app.
The app has no public origin. But notice the Palo Alto isn't in the path; inspection is the WAF's job here.""")
S(10, "inbound", ["r2", "u2", "agw", "fw2", "pe2", "app2", "b1", "b2", "b3", "b4", "n2"], ["r2"], """
Pattern two: Application Gateway with WAF first, then the VM-Series, then the private endpoint. The WAF sees the real client IP and adds an X-Forwarded-For header.
A route on the Application Gateway subnet sends the backend prefix to the internal load balancer, and the firewall adds Threat Prevention and App-ID on the back leg,
SNATing toward the endpoint. This is the most common combination when you want both a WAF and the Palo Alto.""")
S(10, "inbound", ["r3", "u3", "plb", "fw3", "agw3", "app3", "c1", "c2", "c3", "c4", "n3"], ["r3"], """
Pattern three: the firewall first. The public load balancer delivers traffic to the VM-Series, which does destination NAT to a private Application Gateway or endpoint, and source NAT for symmetry.
You get one internet edge with Threat Prevention first, but the client IP only survives in the firewall logs, and seeing layer seven needs inbound decryption.
A variant chains a Gateway Load Balancer to a public frontend, so the firewall is inserted transparently.""")

# ---------------------------------------------------------------- 11 NSP
S(11, "nsp", ["nsp", "blob", "kv", "law", "in1"], ["nsp", "in1"], """
Option G: the Network Security Perimeter. Some PaaS traffic never enters your VNets, like Key Vault sending diagnostics to Log Analytics,
or services that have to stay public. A perimeter draws a boundary around those PaaS resources, and they can talk to each other inside it.""")
S(11, "nsp", ["rules", "pub", "fw", "x1", "x2"], ["rules", "x1", "x2"], """
Inbound access rules allow IP prefixes or subscriptions, for example the firewall's egress IP. Outbound rules allow FQDNs. Everyone else is denied.
Start in transition mode, which logs what would be blocked, then switch to enforced. Every allowed and denied call is logged.""")
S(11, "nsp", ["sp", "pe", "x3", "bottom"], ["x3", "bottom"], """
Private endpoint traffic isn't governed by the perimeter; that's your firewall's job. So the perimeter complements the Palo Alto:
it covers the public side and PaaS-to-PaaS calls, and the firewall covers your networks. Service coverage differs, some are generally available and some in preview, so check before relying on it.""")

# ---------------------------------------------------------------- 12 form factors
S(12, "forms", ["c1", "c1plb", "c1f1", "c1f2", "c1ilb", "c1a", "c1b", "c1c", "c1n"], ["c1"], """
Option H: which Palo Alto form factor carries all this? The VM-Series in the hub VNet is what we've used.
You run the VMs: sizing, zones, upgrades, bootstrap and scale-set autoscaling. You get full PAN-OS, GlobalProtect, decryption and every profile,
and Panorama with the Azure plugin. Run them active-active behind load balancers, or active-passive with floating IPs.""")
S(12, "forms", ["c2", "c2pub", "c2fw", "c2prv", "c2n"], ["c2"], """
Cloud NGFW for Azure in the hub VNet is the managed service. You delegate a public and a private subnet, Palo Alto runs scaling and high availability,
and spokes send traffic with a route to its private IP. Policy comes from a local rulestack, Panorama, or Strata Cloud Manager.
There are fewer knobs than full PAN-OS, so check the feature matrix against your needs.""")
S(12, "forms", ["c3", "c3hub", "c3fw", "c3a", "c3n"], ["c3"], """
And if you run Azure Virtual WAN, Cloud NGFW deploys inside the virtual hub. Routing intent sends private and internet traffic to it, with no route tables to maintain.
For private endpoints in spokes connected to that hub, enable route table network policies on their subnets. Without it, on-premises traffic to the endpoints can be asymmetric.""")

# ---------------------------------------------------------------- 13 defense + troubleshooting
S(13, "gov", ["L1", "L1i", "L2", "L2i", "L3", "L3i"], None, """
The firewall is one layer of several. Identity first: Entra ID and managed identities, and turn off shared keys and local authentication wherever you can.
Then the resource network: public access disabled, private endpoints only. Then the subnet: with network policies on,
an NSG on the endpoint subnet, using application security groups, can allow only the firewall's SNAT addresses.""")
S(13, "gov", ["L4", "L4i", "L5", "L5i", "L6", "L6i"], None, """
The Palo Alto adds App-ID, Threat Prevention, URL and FQDN control, and a deny-and-log default.
Governance keeps it true over time: Azure Policy can deny public network access, deploy private DNS zone groups for every new endpoint, and audit what's missing.
And send firewall logs to Strata Logging Service or Microsoft Sentinel, alongside Azure Monitor and perimeter access logs.""")
S(13, "trouble", ["T1", "T1i", "T2", "T2i"], None, """
When it breaks, troubleshoot in this order. One, DNS: from the client, nslookup the name. You must see the privatelink CNAME and the private IP.
Two, routes: check effective routes on the client's NIC. The endpoint prefix should point at the virtual appliance, with no active slash 32 InterfaceEndpoint route.
The endpoint's own NIC doesn't show effective routes, so always check from the client side.""")
S(13, "trouble", ["T3", "T3i", "T4", "T4i", "T5", "T5i"], None, """
Three, the firewall traffic log, filtered on the endpoint subnet: check the rule, the NAT and the session end reason. No log at all means the packet never arrived.
Four, the endpoint: connection approved, and any NSG on its subnet allowing the SNAT address. Five, symmetry: if it works with SNAT but not without,
check the disableSnatOnPL tag on every dataplane NIC.""")

# ---------------------------------------------------------------- 14 decide
S(14, "decide", ["m"], [], """
To wrap up, here's the decision guide. Public endpoints with IP rules and service endpoints are quick and cheap, but stay public and can't reach on-premises.
Private endpoints with route tables are the default for production: the traffic goes through the Palo Alto, on-premises gets a private path, and each endpoint is tied to one resource.
VNet injection is for dedicated tiers. VNet integration covers outbound traffic from PaaS. Front Door, Application Gateway or firewall DNAT publish apps.
And the perimeter covers what can't go private.""")
S(14, "decide", [], [], """
The rule of thumb: private endpoints in a dedicated spoke, network policies on, a route per endpoint prefix to the internal load balancer,
SNAT or the disableSnatOnPL tag, the DNS Private Resolver for name resolution, public access off, and Azure Policy to keep it that way.
The diagrams and the full script are in the demo-labs repository. Thanks for watching.""")
