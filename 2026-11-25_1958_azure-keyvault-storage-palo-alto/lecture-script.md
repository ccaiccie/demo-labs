# Securing Azure Key Vault and Storage behind a Palo Alto firewall

Lecture script and notes. Video: 1080p, about 12 minutes, English subtitles in a separate SRT file. Diagrams: `azure-keyvault-storage-palo-alto-diagrams.drawio` (11 pages, Azure and draw.io network stencils).

## Chapters and narration

### 0:00 Introduction

Welcome. In this lecture we secure the two Azure platform services almost every workload depends on: Key Vault, which holds secrets, keys and certificates, and Storage, which holds blobs, data lake files and file shares. We'll put both behind a Palo Alto Networks VM-Series firewall in a hub virtual network.

This builds on the general lecture about securing PaaS behind a Palo Alto firewall. Here we go deep on what's specific to these two services: their DNS zones, their sub-resources, their firewall exceptions, the Palo Alto policy, and how to stop data leaving to someone else's account.

### 0:37 Reference topology

Here's the reference topology. The hub VNet, 10.0.0.0/16, holds two VM-Series firewalls behind an internal load balancer with an HA ports rule. Its frontend, 10.0.2.100, is the next hop for every route in this lecture.

Spoke one holds the application: a VM at 10.1.1.10 and an App Service app with VNet integration. Its route table sends the private endpoint range, 10.2.0.0/16, to the firewall.

Spoke two holds the private endpoints: the vault at 10.2.1.6, and separate endpoints for the storage account's blob, dfs and file services. Network policies are enabled on that subnet, and its network security group allows only the firewalls. Both services have public network access disabled.

On-premises connects over ExpressRoute or VPN, and its traffic is also steered to the firewall. In the DNS subnet, the DNS Private Resolver gives on-premises an address to query, 10.0.3.4, and the privatelink zones for the vault and storage are linked to the hub.

### 1:49 Control plane vs data plane

Before any firewall rules, one concept that trips people up: both services have two planes. The control plane is Azure Resource Manager, at management dot azure dot com. That's where you create the vault, change its networking and assign roles. The vault and storage firewalls don't govern it at all. Protect it with Entra ID, Conditional Access, Privileged Identity Management and resource locks.

The data plane is the service endpoint itself: reading a secret from kv-demo dot vault dot azure dot net, or uploading a blob. That's what private endpoints, the service firewalls, and our Palo Alto control.

So think of two locks on every door. The network decides where a request may come from. Identity decides who may do what. A private endpoint without role-based access still lets any workload behind the firewall read every secret. Strong roles on a public endpoint still leave the service exposed. You need both.

### 2:49 Key Vault private endpoint

Key Vault first. You create a private endpoint with the sub-resource vault, here at 10.2.1.6. It maps to this one vault, not to Key Vault as a whole.

DNS: the application keeps using kv-demo dot vault dot azure dot net. Public DNS returns a CNAME to kv-demo dot privatelink dot vaultcore dot azure dot net, and the private zone privatelink dot vaultcore dot azure dot net answers 10.2.1.6. Notice the zone is vaultcore, not vault. On-premises, forward both public zones, vault dot azure dot net and vaultcore dot azure dot net, to the resolver's inbound endpoint.

On the vault, set public network access to disabled. One subtlety: the setting "Allow trusted Microsoft services to bypass this firewall" still applies when public access is disabled. Those services reach the vault over the Microsoft backbone, without a private endpoint. Use the Azure role-based access model, give apps only Key Vault Secrets User, and turn on soft delete and purge protection, so a compromised admin can't permanently destroy keys.

So who goes through your firewall? Your VMs, App Service with VNet integration, and on-premises do, through the private endpoint. Trusted services like disk encryption, SQL transparent data encryption, Azure Backup and Application Gateway certificate retrieval do not; they're governed by roles and the bypass setting. And services not on the trusted list, like hosted Azure DevOps agents, are blocked, so run a self-hosted agent in a spoke and it goes through the firewall like any other workload.

### 4:29 Storage sub-resources

Storage is different, because one account exposes several services, and each needs its own private endpoint: blob, dfs, file, queue, table, and web for static websites.

Each has its own private DNS zone: privatelink dot blob dot core dot windows dot net, privatelink dot dfs, privatelink dot file, and so on. If the account uses read-access geo-redundant storage, the secondary endpoints are separate sub-resources too, using the same zones.

On the account: public network access disabled, shared key access off so only Entra ID identities work, anonymous blob access off, and minimum TLS 1.2. And remember: the storage firewall's IP and virtual network rules apply only to the public endpoint. Traffic through a private endpoint isn't filtered by them, which is exactly why the Palo Alto and the subnet's NSG are your controls on the private side.

The classic gotcha: you create a blob endpoint, but your analytics tool talks to the Data Lake dfs endpoint. dfs still resolves to the public address, public access is off, and you get 403 errors. Inventory every endpoint your tools call. And Azure Files from on-premises needs the file endpoint, with TCP 445 open across the link and on the firewall.

### 5:49 Routing through the firewall

Now routing. Each private endpoint injects a slash 32 route into peered networks. That beats any broader route, so by default the app goes straight to the endpoint and the firewall never sees it.

The fix: enable private endpoint network policies on the endpoint subnet, and add a route on every client subnet, and on the GatewaySubnet, for 10.2.0.0/16 to 10.0.2.100. The prefix must be at least as specific as the endpoint VNet's address space. A default route alone won't override the slash 32.

Then keep the return path symmetric: source NAT to the firewall's trust interface, or tag each firewall NIC with disableSnatOnPL equals true to keep the real client address. And close the loop with an NSG on the endpoint subnet that allows only the firewall's trust subnet, so anything that sneaks around the firewall is dropped at the endpoint.

### 6:49 Palo Alto configuration

On the Palo Alto, create address objects for each endpoint and an address group for the storage endpoints. Then create a custom URL category listing exactly your names: kv-demo dot vault dot azure dot net, and stdemo's blob and dfs names. Point the firewall's DNS at the resolver so any FQDN objects resolve to the private addresses.

Key Vault and Blob are HTTPS, so the firewall can match the TLS server name against that category without decrypting. You can decrypt if clients trust your forward-proxy certificate authority, since the Azure SDKs use the operating system's trust store. Many teams deliberately exclude the vault from decryption, because the payload is secrets. Azure Files over SMB 3 is encrypted end to end, so control it with App-ID and addresses.

The rules: one, the app and App Service integration subnets to the vault endpoint, SSL on 443, restricted to our URL category, with threat profiles and logging. Two, the app to the blob and dfs endpoints, same pattern, adding antivirus and file blocking where you decrypt. Three, on-premises file servers to the file endpoint on 445. Four, the important one: deny any other storage or vault name, and log it. Five, deny everything else to the endpoint subnets. And a NAT rule for source NAT, unless you use the tag.

### 8:14 Trusted services and exceptions

Now the traffic the firewall can't see. On the storage account's public side, the default action is deny, and you can add virtual network rules, IP rules, resource instance rules, and the trusted services exception.

A storage account using a customer-managed key reads it from Key Vault with its managed identity, through the trusted bypass. Azure Backup, Monitor and Event Grid use the trusted services exception. Services like AI Search or Data Factory can use a resource instance rule, which allows one named resource instead of every instance of a service. None of these flows enter your VNets, so the Palo Alto never sees them.

So govern them another way: prefer resource instance rules over the broad exception, give each managed identity only the data roles it needs, and turn on diagnostic logs for both services. The Network Security Perimeter, generally available for Key Vault and Storage, can replace scattered IP and instance rules with one boundary and one access log.

### 9:14 Stopping data exfiltration

Data exfiltration. Imagine a compromised workload. It can reach our storage account through the firewall, because that's allowed.

But can it upload our data to an attacker's storage account? Every storage account shares the same domain, blob dot core dot windows dot net. If your rule allows the wildcard, the answer is yes. With our rule four, the firewall denies any storage or vault name that isn't ours.

Layer the defenses: private endpoints map to one account; the Palo Alto allows only your names; service endpoint policies cover any subnet still using service endpoints; disabling shared keys and SAS tokens forces Entra ID, which you can audit; and Defender for Storage and Key Vault alerts on unusual access. Review the blocked storage names in the URL logs. They're often the first sign of a data theft attempt.

### 10:07 On-premises access

On-premises. A file server at 172.16.5.20 mounts an Azure file share. Traffic crosses ExpressRoute to the gateway, and a route on the GatewaySubnet sends the endpoint range to the firewall, which allows 445 to the file endpoint.

DNS makes it work: on-premises DNS forwards file dot core dot windows dot net, vault dot azure dot net and vaultcore dot azure dot net to the resolver at 10.0.3.4. Users mount with the normal name. Many internet providers block port 445, but over ExpressRoute or VPN to a private endpoint it's private traffic. And use identity-based SMB authentication, Entra Kerberos or Active Directory, rather than the storage account key.

### 10:56 Troubleshooting and checklist

When something fails, the error tells you where to look. Key Vault "client address is not authorized" means the name resolved to the public address. "Not an approved private link" means the endpoint is pending or belongs to another vault. Storage AuthorizationFailure usually means the wrong sub-resource, or the public endpoint. AuthorizationPermissionMismatch means the network is fine and the identity is missing a data role. A timeout with no firewall log means routing; an allowed session that ages out means asymmetry.

Here's the checklist: an endpoint for every vault and every storage sub-resource you use; zones and forwarders; network policies and an NSG on the endpoint subnet; routes on client subnets and the GatewaySubnet; SNAT or the tag; a named-account URL category with an explicit deny; public access disabled; trusted bypass only when needed; Key Vault roles, soft delete and purge protection; storage shared key and anonymous access off; Azure Policy to keep it that way; and all the logs in one place. The diagrams and script are in the demo-labs repository. Thanks for watching.

## Sources

- [Azure private endpoint DNS zone values](https://learn.microsoft.com/en-us/azure/private-link/private-endpoint-dns)
- [Key Vault network security](https://learn.microsoft.com/en-us/azure/key-vault/general/network-security)
- [Use private endpoints for Azure Storage](https://learn.microsoft.com/en-us/azure/storage/common/storage-private-endpoints)
- [Azure Storage network security](https://learn.microsoft.com/en-us/azure/storage/common/storage-network-security)
- [Best practices for storage network security](https://learn.microsoft.com/en-us/troubleshoot/azure/azure-storage/blobs/networking/best-practices-for-storage-network-security)
- [Trusted Azure services for Storage](https://learn.microsoft.com/en-us/azure/storage/common/storage-network-security-trusted-azure-services)
- [Troubleshoot 403 errors with private endpoints](https://learn.microsoft.com/troubleshoot/azure/private-link/troubleshoot-403-access-denied-private-endpoint)
- [Manage network policies for private endpoints](https://learn.microsoft.com/en-us/azure/private-link/disable-private-endpoint-network-policy)
- [Network Security Perimeter concepts](https://learn.microsoft.com/en-us/azure/private-link/network-security-perimeter-concepts)
