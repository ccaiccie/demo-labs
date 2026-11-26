from dlib import Diagram

D = {}


def table(rows, head=True, fs=15, widths=None, px=800):
    h = ['<table style="border-collapse:collapse;width:%dpx;font-size:%dpx;margin-top:6px">' % (px, fs)]
    for i, r in enumerate(rows):
        h.append("<tr>")
        for j, c in enumerate(r):
            tag = "th" if (head and i == 0) else "td"
            bg = "background:#E1DFDD;" if (head and i == 0) else ""
            wd = ("width:%d%%;" % widths[j]) if widths else ""
            h.append('<%s style="border:1px solid #A19F9D;padding:4px 6px;text-align:left;%s%s">%s</%s>' % (tag, bg, wd, c, tag))
        h.append("</tr>")
    h.append("</table>")
    return "".join(h)


# ---------------------------------------------------------------- title
d = Diagram("title"); D["title"] = d
d.note("t1", 150, 120, 1500, 200,
       '<div style="font-size:54px;font-weight:bold;color:#201F1E">Securing Azure Key Vault and Storage behind a Palo Alto firewall</div>',
       sty="none", align="center")
d.note("t2", 150, 340, 1500, 70,
       '<div style="font-size:28px;color:#605E5C">Private endpoints, DNS, routing, PAN-OS policy, exceptions and data exfiltration</div>', sty="none", align="center")
d.icon("ti1", 560, 470, "kv", "Key Vault", s=74, fs=18)
d.icon("ti2", 760, 470, "blob", "Storage account", s=74, fs=18)
d.fw("ti3", 960, 470, "VM-Series", s=76, fs=18)
d.icon("ti4", 1160, 470, "pe", "Private endpoint", s=74, fs=18)
d.note("t3", 150, 660, 1500, 120,
       '<div style="font-size:22px;color:#323130">Builds on the lecture "Securing Azure PaaS behind a Palo Alto firewall in the hub VNet". '
       'This one goes deep on the two services almost every workload uses.</div>', sty="none", align="center")

# ---------------------------------------------------------------- topology
d = Diagram("topo"); D["topo"] = d
d.group("onprem", 10, 300, 230, 300, "On-premises<br>172.16.0.0/16", "onprem")
d.icon("users", 40, 390, "users", "Users / file servers", s=50)
d.icon("opdns", 140, 480, "dnsz", "On-prem DNS", s=46)
d.icon("er", 262, 425, "er", "ExpressRoute<br>or VPN", s=46)
d.group("hub", 380, 90, 640, 760, "Hub VNet  10.0.0.0/16", "hub")
d.group("sgw", 400, 130, 190, 150, "GatewaySubnet", "subnet", fs=14)
d.icon("gw", 470, 170, "gw", "ER / VPN gateway", s=48)
d.group("strust", 610, 130, 390, 330, "snet-trust  10.0.2.0/24", "subnet", fs=14)
d.fw("fw1", 650, 180, "VM-Series<br>FW1", lpos="right")
d.fw("fw2", 850, 180, "VM-Series<br>FW2", lpos="right")
d.icon("ilb", 780, 340, "lb", "Internal LB (HA ports)<br>10.0.2.100", s=48, lw=200)
d.group("sdns", 400, 500, 600, 330, "snet-dns  10.0.3.0/24", "subnet", fs=14)
d.icon("resolver", 470, 560, "dnsr", "DNS Private Resolver<br>inbound 10.0.3.4", s=54, lw=190)
d.icon("zones", 760, 560, "dnsz", "privatelink.vaultcore.azure.net<br>privatelink.blob / dfs / file<br>.core.windows.net", s=54, lw=280)
d.group("sp1", 1080, 90, 360, 360, "Spoke 1 · App  10.1.0.0/16", "spoke")
d.icon("vm", 1120, 160, "vm", "App VM<br>10.1.1.10", s=54)
d.icon("app", 1320, 160, "app", "App Service<br>(VNet integration)", s=54, lw=140)
d.icon("udr1", 1215, 320, "udr", "UDR 10.2.0.0/16<br>→ 10.0.2.100", s=46, lw=170)
d.group("sp2", 1080, 490, 360, 360, "Spoke 2 · Private endpoints  10.2.0.0/16", "spoke")
d.icon("pekv", 1100, 570, "pe", "PE vault<br>10.2.1.6", s=48)
d.icon("peblob", 1185, 570, "pe", "PE blob<br>10.2.1.5", s=48)
d.icon("pedfs", 1270, 570, "pe", "PE dfs<br>10.2.1.7", s=48)
d.icon("pefile", 1355, 570, "pe", "PE file<br>10.2.1.8", s=48)
d.note("polnote", 1100, 700, 320, 120, "snet-pe: network policies <b>Enabled</b><br>NSG allows only firewall sources", sty="good", fs=15)
d.group("paas", 1500, 90, 290, 760, "PaaS · public access disabled", "paas")
d.icon("kv", 1615, 220, "kv", "kv-demo<br>Key Vault", s=60)
d.icon("blob", 1615, 520, "blob", "stdemo<br>Storage account", s=60)
d.edge("e_op", "onprem", "er", "", "gray", arrow=False)
d.edge("e_er", "er", "gw", "", "gray", arrow=False)
d.edge("e_gwilb", "gw", "ilb", "", "blue", ex=0.5, ey=1, nx=0, ny=0.5, pts=[(494, 369)])
d.edge("e_ilbfw1", "ilb", "fw1", "", "blue", ex=0.3, ey=0, nx=0.5, ny=1)
d.edge("e_ilbfw2", "ilb", "fw2", "", "blue", ex=0.7, ey=0, nx=0.5, ny=1)
d.edge("e_p1", "hub", "sp1", "peering", "blue", dashed=True, ex=1, ey=0.2, nx=0, ny=0.42)
d.edge("e_p2", "hub", "sp2", "peering", "blue", dashed=True, ex=1, ey=0.75, nx=0, ny=0.47)
d.edge("e_pl", "sp2", "paas", "Private Link", "purple", dashed=True, ex=1, ey=0.3, nx=0, ny=0.565)

# ---------------------------------------------------------------- planes
d = Diagram("planes"); D["planes"] = d
d.group("mgmt", 20, 40, 870, 560, "Control plane · management.azure.com (Azure Resource Manager)", "plain", fs=18)
d.icon("admin", 80, 140, "users", "Admin / pipeline", s=56)
d.icon("arm", 400, 140, "policy", "Azure Resource Manager", s=56, lw=220)
d.note("mgmtn", 50, 300, 810, 270,
       "• Create the vault or account, set networking, assign RBAC roles<br>• Entra ID sign-in, <b>not</b> governed by the vault or storage firewall<br>"
       "• Protect with Conditional Access, PIM and resource locks<br>• Route admin traffic through the firewall to management.azure.com and login.microsoftonline.com if you want it logged", fs=17)
d.edge("m1", "admin", "arm", "HTTPS 443", "gray")
d.group("data", 910, 40, 870, 560, "Data plane · the service endpoints", "good", fs=18)
d.icon("app", 970, 140, "app", "Application", s=56)
d.icon("kv", 1300, 120, "kv", "kv-demo.vault.azure.net<br>secrets, keys, certificates", s=56, lw=260)
d.icon("blob", 1600, 120, "blob", "stdemo.blob / dfs / file<br>.core.windows.net", s=56, lw=230)
d.note("datan", 940, 300, 810, 270,
       "• Reading a secret, uploading a blob, mounting a file share<br>• <b>This</b> is what the private endpoint, the service firewall and the Palo Alto control<br>"
       "• Authorization is separate: Key Vault RBAC, Storage data roles, SAS or shared key", fs=17)
d.edge("d1", "app", "kv", "", "green", ex=1, ey=0.3, nx=0, ny=0.5)
d.note("bottom", 20, 640, 1760, 200,
       "<b>Two locks on every door</b>: the network decides <b>where</b> a request may come from, and identity decides <b>who</b> may do what. "
       "A private endpoint without RBAC still lets any workload behind the firewall read every secret, and strong RBAC on a public endpoint still exposes the service to the internet. You want both.", fs=19)

# ---------------------------------------------------------------- Key Vault private endpoint
d = Diagram("kvpe"); D["kvpe"] = d
d.group("sp2", 30, 60, 820, 480, "Spoke 2  10.2.0.0/16", "spoke")
d.group("spe", 60, 120, 380, 220, "snet-pe  10.2.1.0/24", "subnet", fs=14)
d.icon("pe", 200, 185, "pe", "PE vault 10.2.1.6<br>sub-resource: vault", s=58, lw=220)
d.icon("zone", 520, 160, "dnsz", "privatelink.vaultcore.azure.net<br>A kv-demo → 10.2.1.6", s=56, lw=300)
d.note("dns", 60, 370, 760, 150,
       "kv-demo.vault.azure.net → CNAME kv-demo.<b>privatelink.vaultcore.azure.net</b> → 10.2.1.6<br>"
       "On-premises: forward <b>vault.azure.net</b> and <b>vaultcore.azure.net</b> to the resolver inbound endpoint", fs=17)
d.group("kvg", 950, 60, 820, 480, "Key Vault  kv-demo", "paas")
d.icon("kv", 1320, 110, "kv", "kv-demo", s=60)
d.note("kvset", 980, 230, 760, 290,
       "<b>Networking</b>: public network access <b>Disabled</b> (private endpoint only)<br>"
       "<b>Exception</b>: Allow trusted Microsoft services to bypass this firewall: still applies when public access is disabled<br>"
       "<b>Access</b>: Azure RBAC permission model (Key Vault Secrets User for apps)<br>"
       "<b>Recovery</b>: soft delete + purge protection on", fs=17)
d.edge("e_pl", "pe", "kv", "Private Link", "purple", dashed=True, ex=1, ey=0.3, nx=0, ny=0.5, pts=[(470, 202), (470, 100), (1290, 100), (1290, 140)])
d.note("who", 30, 580, 1740, 260, "<b>Who reaches the vault, and how</b>" + table([
    ["Caller", "Path", "Through the Palo Alto?"],
    ["App VM, App Service (VNet integration), on-premises", "Private endpoint 10.2.1.6", "<b style='color:#107C10'>Yes, with the UDR and network policies</b>"],
    ["Trusted services: disk encryption, SQL TDE, Azure Backup, App Gateway certificates", "Microsoft backbone, trusted bypass", "<b style='color:#C50F1F'>No</b>: governed by RBAC and the bypass setting"],
    ["Services not on the trusted list (for example Azure DevOps)", "Blocked unless they come through your network", "Yes, via a self-hosted agent in a spoke"],
], widths=[42, 30, 28], px=1700, fs=17), fs=18)

# ---------------------------------------------------------------- Storage sub-resources
d = Diagram("stpe"); D["stpe"] = d
d.group("spe", 30, 60, 560, 520, "snet-pe  10.2.1.0/24", "spoke")
subs = [("pb", "blob", "10.2.1.5"), ("pd", "dfs", "10.2.1.7"), ("pf", "file", "10.2.1.8"), ("pq", "queue", "10.2.1.9"), ("pt", "table", "10.2.1.10")]
for i, (cid, n, ip) in enumerate(subs):
    d.icon(cid, 80 + (i % 3) * 170, 130 + (i // 3) * 200, "pe", "PE %s<br>%s" % (n, ip), s=54)
d.group("stg", 1300, 60, 470, 520, "Storage account  stdemo", "paas")
d.icon("blob", 1500, 120, "blob", "stdemo", s=62)
d.note("stset", 1320, 250, 430, 310,
       "Public network access: <b>Disabled</b><br>Allow shared key access: <b>off</b><br>Anonymous blob access: <b>off</b><br>Minimum TLS 1.2<br>"
       "Firewall rules apply only to the public endpoint, not the private endpoint", fs=16)
d.note("zt", 620, 60, 650, 520, "<b>One endpoint and one DNS zone per sub-resource</b>" + table([
    ["Sub-resource", "Private DNS zone", "Used by"],
    ["blob", "privatelink.blob.core.windows.net", "Blob SDK, AzCopy"],
    ["dfs", "privatelink.dfs.core.windows.net", "Data Lake Gen2 (ABFS)"],
    ["file", "privatelink.file.core.windows.net", "SMB 445, Azure Files REST"],
    ["queue", "privatelink.queue.core.windows.net", "Queues"],
    ["table", "privatelink.table.core.windows.net", "Tables"],
    ["web", "privatelink.web.core.windows.net", "Static website"],
    ["*_secondary", "same zones", "RA-GRS read replicas"],
], widths=[18, 52, 30], px=620, fs=16), fs=17)
d.edge("e1", "spe", "stg", "Private Link", "purple", dashed=True, ex=1, ey=0.92, nx=0, ny=0.92)
d.note("gotcha", 30, 620, 1740, 220,
       "<b>The classic Data Lake gotcha</b>: you create only a blob endpoint, but the app uses the dfs endpoint. dfs still resolves to the public IP, and with public access off you get 403 errors. "
       "Inventory every endpoint your tools call. Azure Files from on-premises needs the <b>file</b> endpoint and TCP 445 open across ExpressRoute or VPN and on the firewall.", fs=18)

# ---------------------------------------------------------------- routing recap
d = Diagram("route"); D["route"] = d
d.group("sp1", 30, 60, 480, 400, "Spoke 1  10.1.0.0/16", "spoke")
d.icon("vm", 120, 150, "vm", "App VM<br>10.1.1.10", s=60)
d.icon("udr", 300, 300, "udr", "UDR 10.2.0.0/16 → 10.0.2.100", s=50, lw=260)
d.group("hub", 600, 60, 540, 400, "Hub VNet", "hub")
d.icon("ilb", 660, 230, "lb", "ILB 10.0.2.100", s=58)
d.fw("fw", 920, 220, "VM-Series<br>SNAT → 10.0.2.4", s=66)
d.group("sp2", 1230, 60, 540, 400, "Spoke 2  10.2.0.0/16", "spoke")
d.icon("pekv", 1300, 150, "pe", "PE vault 10.2.1.6", s=56)
d.icon("peblob", 1300, 300, "pe", "PE blob 10.2.1.5", s=56)
d.note("pol", 1490, 150, 260, 220, "<b>snet-pe</b><br>privateEndpoint-<br>NetworkPolicies =<br><b>Enabled</b>", sty="good", fs=16)
d.edge("byp", "vm", "pekv", "without network policies: /32 route, firewall bypassed", "red", dashed=True,
       ex=0.5, ey=0, nx=0.5, ny=0, pts=[(150, 110), (150, 40), (1328, 40)])
d.edge("r1", "vm", "ilb", "", "green", ex=1, ey=0.5, nx=0, ny=0.5, pts=[(560, 180), (560, 259)])
d.edge("r2", "ilb", "fw", "", "green")
d.edge("r3", "fw", "pekv", "", "green", ex=1, ey=0.3, nx=0, ny=0.5)
d.edge("r4", "fw", "peblob", "", "green", ex=1, ey=0.7, nx=0, ny=0.5)
d.note("steps", 30, 500, 1740, 340, "<b>Four things make it work</b>" + table([
    ["#", "Setting", "Where", "Why"],
    ["1", "privateEndpointNetworkPolicies = Enabled", "snet-pe", "Lets UDRs override the endpoint's /32 route, and NSGs apply"],
    ["2", "UDR 10.2.0.0/16 → 10.0.2.100", "every client subnet + GatewaySubnet", "At least as specific as the endpoint VNet; a default route is not enough"],
    ["3", "SNAT to the trust interface, or disableSnatOnPL = true", "VM-Series NAT policy / NIC tag", "Keeps the return path on the same firewall"],
    ["4", "NSG on snet-pe: allow 10.0.2.0/24 only", "snet-pe", "Anything that skips the firewall is dropped at the endpoint"],
], widths=[4, 34, 26, 36], px=1700, fs=17), fs=18)

# ---------------------------------------------------------------- PAN-OS policy
d = Diagram("panpol"); D["panpol"] = d
d.fw("fw", 855, 30, "VM-Series (PAN-OS)", s=80, fs=17)
d.note("obj", 20, 30, 800, 330,
       "<b>Objects</b><br>Address: pe-kv 10.2.1.6 · pe-blob 10.2.1.5 · pe-dfs 10.2.1.7 · pe-file 10.2.1.8<br>"
       "Address group: <b>ag-pe-storage</b> = blob, dfs, file<br>"
       "Custom URL category <b>cat-our-paas</b>:<br>&nbsp;kv-demo.vault.azure.net<br>&nbsp;stdemo.blob.core.windows.net, stdemo.dfs.core.windows.net<br>"
       "Firewall DNS = 10.0.3.4 so FQDN objects resolve privately", fs=16)
d.note("tls", 980, 30, 800, 330,
       "<b>TLS and inspection</b><br>• Key Vault and Blob traffic is HTTPS: match the TLS server name (SNI) against cat-our-paas without decrypting<br>"
       "• Decrypt only if clients trust your forward-proxy CA; Azure SDKs use the OS trust store<br>"
       "• Never decrypt the vault if policy treats secrets as out of scope for inspection<br>"
       "• SMB 3 to Azure Files is encrypted end to end: control it with App-ID and addresses", fs=16)
d.note("rules", 20, 390, 1760, 450, "<b>Security policy (top-down)</b>" + table([
    ["#", "Name", "Source", "Destination", "Application / service", "Action / profiles"],
    ["1", "app-to-keyvault", "TRUST · snet-app, snet-integration", "pe-kv", "ssl · tcp/443 · URL cat-our-paas", "allow · vulnerability, spyware · log"],
    ["2", "app-to-blob-dfs", "TRUST · snet-app", "ag-pe-storage", "ssl · tcp/443 · URL cat-our-paas", "allow · AV, file blocking, WildFire if decrypted"],
    ["3", "onprem-to-files", "TRUST · 172.16.0.0/16 file servers", "pe-file", "SMB application · tcp/445", "allow · log"],
    ["4", "deny-other-storage", "any", "any", "URL *.blob/dfs/file.core.windows.net, *.vault.azure.net", "<b>deny</b> · log (exfiltration guard)"],
    ["5", "deny-to-pe", "any", "PE subnets", "any", "deny · log"],
    ["NAT", "pe-snat", "TRUST", "PE subnets", "", "source NAT to ethernet1/2 (skip if disableSnatOnPL)"],
], widths=[5, 15, 21, 12, 27, 20], px=1720, fs=16), fs=18)

# ---------------------------------------------------------------- exceptions
d = Diagram("except"); D["except"] = d
d.group("stg", 640, 60, 520, 500, "Storage account · public endpoint side", "paas")
d.icon("blob", 870, 120, "blob", "stdemo", s=62)
d.note("acl", 660, 250, 480, 290,
       "Default action: <b>Deny</b><br>VNet rules (service endpoints)<br>IP rules<br><b>Resource instance rules</b>: one named resource, for example a specific AI Search service<br>"
       "<b>Trusted services exception</b>: every instance of every listed service", fs=16)
d.icon("cmk", 120, 110, "kv", "Storage → Key Vault<br>customer-managed key", s=56, lw=220)
d.icon("bkp", 120, 300, "monitor", "Azure Backup, Monitor,<br>Event Grid, Defender", s=56, lw=220)
d.icon("srch", 120, 480, "users", "AI Search, Data Factory,<br>Synapse", s=56, lw=220)
d.edge("x1", "cmk", "blob", "storage reads its key: managed identity · trusted bypass", "purple", dashed=True, ex=1, ey=0.5, nx=0, ny=0.3, both=True)
d.edge("x2", "bkp", "acl", "trusted services exception", "orange", dashed=True, ex=1, ey=0.5, nx=0, ny=0.4)
d.edge("x3", "srch", "acl", "resource instance rule (preferred)", "green", ex=1, ey=0.5, nx=0, ny=0.85)
d.fw("fw", 1400, 270, "VM-Series", s=66)
d.note("fwn", 1250, 400, 520, 160, "None of these flows touch your firewall: they never enter your VNets", sty="bad", fs=17)
d.note("bottom", 20, 600, 1760, 240,
       "<b>Govern what the firewall can't see</b>: prefer resource instance rules over the broad trusted-services exception, "
       "grant only the data roles each managed identity needs, and turn on diagnostic logs for both services. "
       "The Network Security Perimeter, generally available for Key Vault and Storage, can replace scattered IP and instance rules with one boundary and one access log.", fs=19)

# ---------------------------------------------------------------- exfiltration
d = Diagram("exfil"); D["exfil"] = d
d.group("sp1", 20, 60, 380, 480, "Spoke 1", "spoke")
d.icon("vm", 170, 150, "vm", "Compromised<br>workload", s=60)
d.group("hub", 470, 60, 420, 480, "Hub VNet", "hub")
d.fw("fw", 640, 170, "VM-Series", s=66)
d.icon("ours", 1040, 110, "blob", "stdemo<br>(ours, via PE)", s=58)
d.icon("theirs", 1040, 370, "blob", "attacker-owned<br>storage account", s=58)
d.edge("a1", "vm", "fw", "", "blue", ex=1, ey=0.3, nx=0, ny=0.5)
d.edge("a2", "fw", "ours", "allowed: cat-our-paas", "green", ex=1, ey=0.3, nx=0, ny=0.5)
d.edge("a3", "fw", "theirs", "denied: other *.blob.core.windows.net", "red", dashed=True, ex=1, ey=0.8, nx=0, ny=0.5)
d.note("ctl", 1240, 60, 540, 480,
       "<b>Layers against exfiltration</b><br>1. A private endpoint maps to <b>one</b> account, not the whole service<br>"
       "2. Palo Alto: allow only your account names, deny every other storage and vault FQDN<br>"
       "3. Service endpoint policies on any subnet still using service endpoints<br>"
       "4. Disable shared key and SAS where possible; use Entra ID data roles<br>"
       "5. Defender for Storage and Key Vault for anomalous access alerts", fs=17)
d.note("bottom", 20, 580, 1760, 260,
       "<b>Why the wildcard is dangerous</b>: an allow rule for *.blob.core.windows.net lets any workload copy data to any storage account in the world, including the attacker's. "
       "Allow exactly your account and vault names, keep the explicit deny below it, and review the URL logs for blocked storage FQDNs; they are often the first sign of a data theft attempt.", fs=19)

# ---------------------------------------------------------------- hybrid
d = Diagram("hybrid"); D["hybrid"] = d
d.group("onprem", 20, 120, 340, 520, "On-premises", "onprem")
d.icon("fs", 80, 190, "vm", "File server<br>172.16.5.20", s=56)
d.icon("opdns", 200, 430, "dnsz", "On-prem DNS<br>forwarders:<br>file.core.windows.net<br>vault.azure.net, vaultcore.azure.net<br>→ 10.0.3.4", s=52, lw=250)
d.icon("er", 400, 330, "er", "ExpressRoute", s=48)
d.group("hub", 520, 120, 680, 520, "Hub VNet", "hub")
d.icon("gw", 580, 200, "gw", "ER gateway", s=54)
d.icon("gwudr", 600, 545, "udr", "GatewaySubnet UDR<br>10.2.0.0/16 → 10.0.2.100", s=48, lw=220)
d.icon("ilb", 800, 200, "lb", "ILB", s=54)
d.fw("fw", 1010, 195, "VM-Series<br>allow 445 to pe-file", s=62)
d.icon("res", 860, 430, "dnsr", "Resolver inbound<br>10.0.3.4", s=54)
d.group("sp2", 1260, 120, 510, 520, "Spoke 2 · PEs", "spoke")
d.icon("pefile", 1320, 200, "pe", "PE file 10.2.1.8", s=54)
d.icon("pekv", 1560, 200, "pe", "PE vault 10.2.1.6", s=54)
d.edge("h0", "fs", "er", "", "gray", arrow=False, ex=1, ey=0.5, nx=0, ny=0.5, pts=[(380, 218), (380, 354)])
d.edge("h1", "er", "gw", "", "gray", arrow=False, ex=1, ey=0.5, nx=0.5, ny=1, pts=[(607, 354)])
d.edge("h2", "gw", "ilb", "", "green")
d.edge("h3", "ilb", "fw", "", "green")
d.edge("h4", "fw", "pefile", "SMB 445", "green")
d.edge("h5", "opdns", "res", "DNS", "blue", dashed=True, ex=1, ey=0.7, nx=0, ny=0.5)
d.note("bottom", 20, 680, 1760, 160,
       "Mount with the normal name: \\\\stdemo.file.core.windows.net\\share. Many ISPs block 445, but over ExpressRoute or VPN to a private endpoint it is private traffic. "
       "Use identity-based SMB authentication (Entra Kerberos or AD DS) instead of the storage account key.", fs=18)

# ---------------------------------------------------------------- troubleshooting + checklist
d = Diagram("check"); D["check"] = d
d.note("tr", 20, 20, 860, 820, "<b>Troubleshooting 403s and timeouts</b>" + table([
    ["Symptom", "Likely cause"],
    ["Key Vault 403 \"client address is not authorized\"", "Name resolved to the public IP: zone link or forwarder missing"],
    ["Key Vault 403 \"not an approved private link\"", "Endpoint pending or for a different vault"],
    ["Storage 403 AuthorizationFailure", "Wrong sub-resource (dfs vs blob) or request reached the public endpoint"],
    ["Storage 403 AuthorizationPermissionMismatch", "Network fine; missing data role (RBAC)"],
    ["Timeout, no firewall log", "UDR missing or network policies off"],
    ["Firewall log shows allow, then aged-out", "Asymmetric return: SNAT or disableSnatOnPL"],
    ["Firewall deny on URL category", "Account or vault not in cat-our-paas"],
], widths=[48, 52], px=820, fs=17), fs=18)
d.note("ck", 910, 20, 870, 820, "<b>Deployment checklist</b><br><br>"
       "☐ Private endpoint per vault and per storage sub-resource you use<br>"
       "☐ privatelink zones linked to the hub; forwarders for the public zones on-premises<br>"
       "☐ Network policies Enabled on snet-pe; NSG allows the firewall only<br>"
       "☐ UDR for the PE range on client subnets and GatewaySubnet<br>"
       "☐ SNAT or disableSnatOnPL on the VM-Series<br>"
       "☐ PAN-OS: named-account URL category, explicit deny for other storage and vault FQDNs<br>"
       "☐ Public network access Disabled on both services<br>"
       "☐ Trusted bypass only if needed; resource instance rules over broad exceptions<br>"
       "☐ Key Vault RBAC, soft delete, purge protection<br>"
       "☐ Storage: shared key off, anonymous access off, TLS 1.2<br>"
       "☐ Azure Policy to deny public access and deploy DNS zone groups<br>"
       "☐ Diagnostic logs + firewall logs to the same SIEM", fs=19)
