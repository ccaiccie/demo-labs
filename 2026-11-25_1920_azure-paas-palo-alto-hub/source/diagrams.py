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
       '<div style="font-size:52px;font-weight:bold;color:#201F1E">Securing Azure PaaS behind a Palo Alto firewall in the hub VNet</div>',
       sty="none", align="center")
d.note("t2", 150, 340, 1500, 70,
       '<div style="font-size:28px;color:#605E5C">Every option, the routing and DNS that make it work, and how to choose</div>', sty="none", align="center")
d.icon("ti1", 470, 470, "sql", "Azure SQL", s=70, fs=18)
d.icon("ti2", 640, 470, "blob", "Storage", s=70, fs=18)
d.icon("ti3", 810, 470, "kv", "Key Vault", s=70, fs=18)
d.fw("ti4", 980, 470, "VM-Series", s=74, fs=18)
d.icon("ti5", 1150, 470, "pe", "Private Endpoint", s=70, fs=18)
d.icon("ti6", 1320, 470, "vnet", "Hub VNet", s=70, fs=18)
d.note("t3", 150, 660, 1500, 120,
       '<div style="font-size:22px;color:#323130">Public endpoints · Service endpoints · Private endpoints · VNet injection · VNet integration · '
       'Inbound publishing · Network Security Perimeter · VM-Series vs Cloud NGFW</div>', sty="none", align="center")

# ---------------------------------------------------------------- reference topology
d = Diagram("topo"); D["topo"] = d
d.cloud("inet", 610, 0, 220, 80, "Internet")
d.group("onprem", 10, 300, 230, 300, "On-premises<br>172.16.0.0/16", "onprem")
d.icon("users", 40, 390, "users", "Users", s=50)
d.icon("opdns", 140, 470, "dnsz", "On-prem DNS", s=50)
d.icon("er", 262, 425, "er", "ExpressRoute<br>or VPN", s=46)
d.group("hub", 380, 90, 640, 760, "Hub VNet  10.0.0.0/16", "hub")
d.group("smgmt", 400, 130, 190, 150, "snet-mgmt", "subnet", fs=14)
d.icon("pano", 470, 175, "vm", "Panorama /<br>mgmt", s=48)
d.group("suntr", 610, 130, 390, 150, "snet-untrust  10.0.1.0/24", "subnet", fs=14)
d.icon("plb", 650, 175, "lb", "Public LB", s=48)
d.icon("pip", 860, 175, "pip", "Public IPs", s=48)
d.fw("fw1", 660, 315, "VM-Series<br>FW1", lpos="right")
d.fw("fw2", 870, 315, "VM-Series<br>FW2", lpos="right")
d.group("strust", 610, 430, 390, 150, "snet-trust  10.0.2.0/24", "subnet", fs=14)
d.icon("ilb", 780, 470, "lb", "Internal LB (HA ports)<br>frontend 10.0.2.100", s=48, lw=200)
d.group("sgw", 400, 430, 190, 150, "GatewaySubnet", "subnet", fs=14)
d.icon("gw", 470, 470, "gw", "ER / VPN<br>gateway", s=48)
d.group("sdns", 400, 610, 600, 220, "snet-dns  10.0.3.0/24", "subnet", fs=14)
d.icon("resolver", 470, 660, "dnsr", "DNS Private Resolver<br>inbound 10.0.3.4", s=54, lw=190)
d.icon("zones", 780, 660, "dnsz", "Private DNS zones<br>privatelink.*", s=54, lw=190)
d.group("sp1", 1080, 90, 360, 360, "Spoke 1 · Workloads  10.1.0.0/16", "spoke")
d.icon("vm", 1120, 160, "vm", "App VM<br>10.1.1.10", s=54)
d.icon("app", 1320, 160, "app", "App Service<br>(VNet integration)", s=54, lw=140)
d.icon("udr1", 1215, 320, "udr", "UDR default route<br>→ 10.0.2.100", s=46, lw=170)
d.group("sp2", 1080, 490, 360, 360, "Spoke 2 · Private endpoints  10.2.0.0/16", "spoke")
d.icon("pesql", 1110, 570, "pe", "PE sql<br>10.2.1.4", s=50)
d.icon("peblob", 1235, 570, "pe", "PE blob<br>10.2.1.5", s=50)
d.icon("pekv", 1360, 570, "pe", "PE vault<br>10.2.1.6", s=50)
d.icon("udr2", 1215, 730, "udr", "UDR → 10.0.2.100", s=46, lw=170)
d.group("paas", 1500, 90, 290, 760, "Azure PaaS", "paas")
d.icon("sql", 1615, 170, "sql", "Azure SQL", s=60)
d.icon("blob", 1615, 400, "blob", "Storage account", s=60)
d.icon("kv", 1615, 630, "kv", "Key Vault", s=60)
d.edge("e_inet", "inet", "plb", "", "orange", nx=0.5, ny=0)
d.edge("e_op", "onprem", "er", "", "gray", arrow=False)
d.edge("e_er", "er", "gw", "", "gray", arrow=False)
d.edge("e_gwilb", "gw", "ilb", "", "blue")
d.edge("e_plbfw", "plb", "fw1", "", "orange")
d.edge("e_ilbfw1", "ilb", "fw1", "", "blue", ex=0.3, ey=0, nx=0.5, ny=1)
d.edge("e_ilbfw2", "ilb", "fw2", "", "blue", ex=0.7, ey=0, nx=0.5, ny=1)
d.edge("e_p1", "hub", "sp1", "peering", "blue", dashed=True, ex=1, ey=0.2, nx=0, ny=0.42)
d.edge("e_p2", "hub", "sp2", "peering", "blue", dashed=True, ex=1, ey=0.75, nx=0, ny=0.47)
d.edge("e_pl", "sp2", "paas", "Private Link", "purple", dashed=True, ex=1, ey=0.5, nx=0, ny=0.763)

# ---------------------------------------------------------------- options map
d = Diagram("options"); D["options"] = d
cards = [
    ("oA", "pip", "A · Public endpoint + service firewall", "Allow only the firewall's egress public IP on the PaaS firewall. Simple, still public."),
    ("oB", "sep", "B · Service endpoints", "Enable on the firewall's egress subnet, not the workload subnet. Source is the subnet, not a public IP."),
    ("oC", "pe", "C · Private endpoints (Private Link)", "A private IP for the resource inside your VNet. Route it through the firewall. The default choice."),
    ("oD", "sqlmi", "D · VNet injection", "Dedicated services live in your subnet: SQL MI, App Service Environment, APIM, AKS."),
    ("oE", "app", "E · Outbound: VNet integration", "App Service / Functions send their outbound traffic into a subnet and then to the firewall."),
    ("oF", "afd", "F · Inbound publishing", "Front Door with Private Link, App Gateway WAF, or firewall DNAT in front of the app."),
    ("oG", "nsp", "G · Network Security Perimeter", "A boundary around PaaS-to-PaaS and public PaaS access. Complements the firewall."),
    ("oH", "vhub", "H · Firewall form factor", "VM-Series in the hub VNet, Cloud NGFW in the hub VNet, or Cloud NGFW in a vWAN hub."),
]
for i, (cid, ic, t, body) in enumerate(cards):
    x = 30 + (i % 4) * 440
    y = 60 if i < 4 else 450
    d.note(cid, x, y, 410, 350,
           '<div style="font-size:22px;font-weight:bold;margin-top:70px">%s</div><div style="font-size:21px;margin-top:12px">%s</div>' % (t, body),
           sty="good" if cid == "oC" else "plain", align="left")
    d.icon(cid + "i", x + 20, y + 20, ic, "", s=56)

# ---------------------------------------------------------------- option A public endpoint
d = Diagram("public"); D["public"] = d
d.group("sp1", 30, 180, 300, 380, "Spoke 1", "spoke")
d.icon("vm", 145, 260, "vm", "App VM<br>10.1.1.10", s=60)
d.icon("udr", 150, 420, "udr", "UDR default route<br>→ ILB", s=50, lw=160)
d.group("hub", 400, 180, 560, 380, "Hub VNet", "hub")
d.icon("ilb", 450, 300, "lb", "Internal LB", s=56)
d.fw("fw", 640, 295, "VM-Series<br>SNAT to egress IP", s=64)
d.icon("pip", 840, 300, "pip", "Egress public IP<br>20.55.10.7", s=56, lw=150)
d.cloud("bb", 1030, 290, 270, 170, "Microsoft backbone<br>(public endpoints)")
d.group("stg", 1370, 180, 400, 380, "Storage account · public endpoint", "paas")
d.icon("blob", 1400, 230, "blob", "stgdemo.blob.core.windows.net", s=60, lpos="right")
d.note("rules", 1390, 360, 360, 180, "<b>Networking → Selected networks</b><br>IP rule: allow 20.55.10.7<br>Everything else: denied", sty="plain", fs=17)
d.icon("bad", 1090, 40, "users", "Anyone else on<br>the internet", s=50, lw=150)
d.edge("e1", "vm", "ilb", "", "blue", ex=1, ey=0.5, nx=0, ny=0.5)
d.edge("e2", "ilb", "fw", "", "blue")
d.edge("e3", "fw", "pip", "", "blue")
d.edge("e4", "pip", "bb", "", "blue")
d.edge("e5", "bb", "blob", "src 20.55.10.7 ✔", "green", ex=1, ey=0.3, nx=0, ny=0.5)
d.edge("e6", "bad", "blob", "denied ✖", "red", dashed=True, ex=1, ey=0.5, nx=0.5, ny=0)
d.note("pc", 30, 610, 1740, 230,
       "<b>Pros</b>: no DNS changes, works for every service, the firewall sees and logs every flow (App-ID, URL filtering, Threat Prevention).<br>"
       "<b>Cons</b>: the PaaS endpoint stays internet-facing; every workload behind the firewall shares one source IP, so the IP rule trusts all of them; "
       "trusted-services exceptions punch extra holes; no private path from on-premises; data can still leave to any other storage account unless the firewall filters by FQDN.",
       sty="plain", fs=18)

# ---------------------------------------------------------------- option B service endpoints
d = Diagram("svcep"); D["svcep"] = d
d.group("bad", 20, 40, 860, 620, "✖ Service endpoint on the workload subnet", "bad", fs=19)
d.group("bsub", 40, 100, 270, 220, "snet-app<br>Microsoft.Storage endpoint ON", "subnet", fs=14)
d.icon("bvm", 145, 190, "vm", "App VM", s=56)
d.fw("bfw", 450, 180, "VM-Series", s=62)
d.icon("bblob", 740, 185, "blob", "Storage", s=58)
d.edge("b1", "bvm", "bblob", "VirtualNetworkServiceEndpoint route: firewall bypassed", "red", ex=0.5, ey=1, nx=0.5, ny=1, pts=[(173, 370), (769, 370)], lx=0, ly=0)
d.edge("b2", "bvm", "bfw", "default UDR", "gray", dashed=True, ex=1, ey=0.3, nx=0, ny=0.3)
d.note("brt", 40, 420, 820, 220, table([
    ["Prefix", "Next hop", "Result"],
    ["0.0.0.0/0", "Virtual appliance 10.0.2.100", "everything else"],
    ["Storage service prefixes", "VirtualNetworkServiceEndpoint", "<b>more specific: wins</b>"],
], px=780), fs=16)
d.group("good", 920, 40, 860, 620, "✔ Service endpoint on the firewall's egress subnet", "good", fs=19)
d.icon("gvm", 960, 190, "vm", "App VM<br>(no endpoint)", s=56)
d.group("gsub", 1150, 100, 330, 220, "snet-untrust<br>Microsoft.Storage endpoint ON", "subnet", fs=14)
d.fw("gfw", 1285, 180, "VM-Series", s=62)
d.icon("gblob", 1640, 185, "blob", "Storage", s=58)
d.edge("g1", "gvm", "gfw", "UDR → ILB", "green", ex=1, ey=0.5, nx=0, ny=0.5)
d.edge("g2", "gfw", "gblob", "source = hub/snet-untrust", "green", ex=1, ey=0.5, nx=0, ny=0.5)
d.note("grt", 940, 420, 820, 220,
       "<b>Storage firewall</b>: VNet rule allows only hub / snet-untrust<br><b>VM-Series</b>: App-ID + URL filtering on *.blob.core.windows.net, SNAT to the untrust interface<br>"
       "<b>Service endpoint policy</b> on snet-untrust: only <i>your</i> storage accounts (exfiltration guard)", fs=17)
d.note("lim", 20, 690, 1760, 150,
       "<b>Limits</b>: still the public endpoint and public DNS · not reachable from on-premises · the PaaS firewall trusts the whole firewall subnet, so per-workload control "
       "lives on the Palo Alto policy · only some services support service endpoints, and fewer support endpoint policies.", fs=18)

# ---------------------------------------------------------------- option C anatomy + DNS
d = Diagram("pe"); D["pe"] = d
d.group("vnet", 30, 60, 900, 540, "Spoke VNet  10.2.0.0/16", "spoke")
d.group("sapp", 60, 120, 330, 230, "snet-app", "subnet", fs=14)
d.icon("vm", 190, 190, "vm", "Client VM", s=58)
d.group("spe", 520, 120, 380, 230, "snet-pe  10.2.1.0/24", "subnet", fs=14)
d.icon("pe", 600, 185, "pe", "Private endpoint", s=58)
d.icon("nic", 770, 190, "nic", "NIC 10.2.1.5", s=50)
d.icon("zone", 420, 430, "dnsz", "Private DNS zone<br>privatelink.blob.core.windows.net<br>A stgdemo → 10.2.1.5", s=56, lw=330)
d.group("stg", 1150, 60, 620, 540, "Storage account  stgdemo", "paas")
d.icon("blob", 1430, 140, "blob", "blob sub-resource", s=64)
d.note("pna", 1180, 300, 560, 270,
       "<b>Public network access: Disabled</b><br>Private endpoint connection: Approved<br>Target sub-resource: blob (one endpoint per sub-resource: blob, dfs, file, queue, table, web)<br>"
       "The public name still exists, but only answers privately", fs=17)
d.edge("e_vmpe", "vm", "pe", "TCP 443 → 10.2.1.5", "green", ex=1, ey=0.5, nx=0, ny=0.5)
d.edge("e_pl", "nic", "blob", "Private Link (Microsoft backbone)", "purple", dashed=True, ex=1, ey=0.5, nx=0, ny=0.5)
d.note("n1", 30, 640, 410, 200, "<b>1.</b> App resolves<br>stgdemo.blob.core.windows.net", fs=18)
d.note("n2", 470, 640, 420, 200, "<b>2.</b> Public DNS answers with a CNAME:<br>stgdemo.<b>privatelink</b>.blob.core.windows.net", fs=18)
d.note("n3", 920, 640, 420, 200, "<b>3.</b> A VNet linked to the private zone gets<br><b>A 10.2.1.5</b>", sty="good", fs=18)
d.note("n4", 1370, 640, 400, 200, "<b>4.</b> Anyone else gets the public IP, and the request is refused because public access is off", sty="bad", fs=18)

# ---------------------------------------------------------------- hybrid DNS
d = Diagram("dns"); D["dns"] = d
d.group("onprem", 20, 100, 400, 560, "On-premises", "onprem")
d.icon("client", 70, 190, "users", "Client", s=54)
d.icon("opdns", 230, 400, "dnsz", "On-prem DNS<br>conditional forwarder<br>blob.core.windows.net → 10.0.3.4", s=56, lw=300)
d.group("hub", 480, 100, 620, 560, "Hub VNet", "hub")
d.icon("res", 540, 190, "dnsr", "DNS Private Resolver<br>inbound 10.0.3.4", s=58, lw=200)
d.icon("azdns", 880, 190, "dnsz", "Azure DNS<br>168.63.129.16", s=58, lw=160)
d.icon("zones", 880, 420, "dnsz", "Private DNS zones<br>privatelink.* (linked to hub)", s=58, lw=220)
d.fw("fw", 555, 420, "VM-Series<br>DNS server = 10.0.3.4", s=60)
d.group("spk", 1160, 100, 620, 560, "Spokes", "spoke")
d.icon("svm", 1230, 190, "vm", "Spoke VM", s=58)
d.note("sopt", 1190, 350, 560, 280,
       "<b>Spoke DNS choices</b><br>1. Custom DNS = resolver inbound IP (one central path)<br>2. Azure-provided DNS + link the zones (or a forwarding ruleset) to each spoke<br>"
       "3. Custom DNS = firewall DNS proxy, which then forwards to the resolver, so every lookup is logged", fs=17)
d.edge("d1", "client", "opdns", "1", "blue", ex=0.5, ey=1, nx=0.3, ny=0)
d.edge("d2", "opdns", "res", "2 forward over ER/VPN", "blue", ex=1, ey=0.3, nx=0, ny=0.5, pts=[(470, 417), (470, 219)])
d.edge("d3", "res", "azdns", "3", "blue")
d.edge("d4", "azdns", "zones", "4  A 10.2.1.5", "green")
d.edge("d5", "fw", "res", "FQDN objects", "orange", ex=0.5, ey=0, nx=0.5, ny=1)
d.edge("d6", "svm", "res", "", "teal", ex=0.5, ey=0, nx=0.5, ny=0, pts=[(1259, 150), (569, 150)])
d.note("warn", 20, 700, 1760, 140,
       "<b>Gotchas</b>: forward the <b>public</b> zone (blob.core.windows.net, database.windows.net, vault.azure.net), not only privatelink.* · "
       "on-prem servers can't reach 168.63.129.16, so they need the resolver inbound endpoint · keep one set of privatelink zones per environment and let Azure Policy register records.", fs=18)

# ---------------------------------------------------------------- routing /32 override
d = Diagram("route"); D["route"] = d
d.group("sp1", 30, 60, 500, 420, "Spoke 1  10.1.0.0/16", "spoke")
d.icon("vm", 120, 150, "vm", "App VM<br>10.1.1.10", s=60)
d.group("hub", 620, 60, 520, 420, "Hub VNet", "hub")
d.icon("ilb", 690, 260, "lb", "ILB<br>10.0.2.100", s=58)
d.fw("fw", 930, 250, "VM-Series", s=66)
d.group("sp2", 1230, 60, 540, 420, "Spoke 2  10.2.0.0/16", "spoke")
d.icon("pe", 1300, 250, "pe", "PE 10.2.1.5", s=60)
d.note("pol", 1430, 140, 320, 300, "<b>snet-pe</b><br>privateEndpointNetworkPolicies =<br><b>RouteTableEnabled</b><br>(or Enabled, which also turns on NSGs)", sty="good", fs=16)
d.edge("byp", "vm", "pe", "peering + /32 InterfaceEndpoint route = firewall bypassed", "red", dashed=True,
       ex=1, ey=0.2, nx=0.5, ny=0, pts=[(600, 162), (600, 110), (1330, 110)])
d.edge("r1", "vm", "ilb", "UDR", "green", ex=1, ey=0.8, nx=0, ny=0.5, pts=[(260, 198), (260, 289)])
d.edge("r2", "ilb", "fw", "", "green")
d.edge("r3", "fw", "pe", "", "green")
d.note("rtb", 30, 520, 860, 320, "<b>Effective routes on snet-app: before</b>" + table([
    ["Prefix", "Next hop", "Source"],
    ["0.0.0.0/0", "Virtual appliance 10.0.2.100", "User"],
    ["10.2.0.0/16", "VNet peering", "Default"],
    ["10.2.1.5/32", "InterfaceEndpoint", "Default · <b style='color:#C50F1F'>wins (longest prefix)</b>"],
], px=820, fs=17), sty="bad", fs=18)
d.note("rta", 910, 520, 860, 320, "<b>Effective routes on snet-app: after</b>" + table([
    ["Prefix", "Next hop", "Source"],
    ["0.0.0.0/0", "Virtual appliance 10.0.2.100", "User"],
    ["10.2.0.0/16", "Virtual appliance 10.0.2.100", "User · <b style='color:#107C10'>same length as the PE VNet</b>"],
    ["10.2.1.5/32", "InterfaceEndpoint", "<s>Invalid</s>: overridden by network policy"],
], px=820, fs=17), sty="good", fs=18)

# ---------------------------------------------------------------- symmetry / SNAT
d = Diagram("symm"); D["symm"] = d
d.group("sp1", 30, 180, 320, 340, "Spoke 1", "spoke")
d.icon("vm", 155, 280, "vm", "App VM<br>10.1.1.10", s=60)
d.group("hub", 430, 60, 700, 600, "Hub VNet", "hub")
d.icon("ilb", 490, 300, "lb", "ILB 10.0.2.100<br>HA ports", s=58)
d.fw("fw1", 800, 150, "FW1  trust 10.0.2.4", s=64, lpos="top")
d.fw("fw2", 800, 430, "FW2  trust 10.0.2.5", s=64, lpos="top")
d.group("sp2", 1220, 180, 550, 340, "Spoke 2", "spoke")
d.icon("pe", 1440, 280, "pe", "PE sql 10.2.1.4", s=60)
d.edge("f1", "vm", "ilb", "", "green")
d.edge("f2", "ilb", "fw1", "", "green", ex=0.5, ey=0, nx=0, ny=0.5, pts=[(519, 182)])
d.edge("f3", "fw1", "pe", "original: 10.1.1.10 → 10.2.1.4", "green", ex=1, ey=0.5, nx=0.5, ny=0, pts=[(1469, 182)])
d.edge("ret", "pe", "vm", "return can skip the firewall → asymmetric drop", "red", dashed=True, ex=0.5, ey=1, nx=0, ny=0.8,
       pts=[(1469, 600), (90, 600), (90, 328)])
d.edge("snat", "fw1", "pe", "after SNAT: 10.0.2.4 → 10.2.1.4", "orange", ex=0.9, ey=1, nx=0, ny=0.5, pts=[(858, 309)])
d.note("o1", 30, 690, 560, 150, "<b>Option 1 · SNAT on the firewall</b><br>source becomes the trust interface, so replies always return to it. Cost: the PaaS logs see the firewall IP.", fs=16)
d.note("o2", 620, 690, 560, 150, "<b>Option 2 · disableSnatOnPL = true</b><br>tag on each firewall dataplane NIC (or VMSS instance). Keeps the real client IP. Causes a one-time reset of PE flows.", fs=16)
d.note("o3", 1210, 690, 560, 150, "<b>Either way</b><br>send both directions through the same ILB frontend so HA-ports hashing lands on the same firewall.", fs=16)

# ---------------------------------------------------------------- PE placement
d = Diagram("place"); D["place"] = d
d.group("p1", 20, 30, 570, 810, "1 · Dedicated private-endpoint spoke", "plain", fs=19)
d.group("p1h", 40, 90, 220, 170, "Hub", "hub", fs=14)
d.fw("p1fw", 120, 140, "", s=56)
d.group("p1a", 300, 90, 270, 170, "App spoke", "spoke", fs=14)
d.icon("p1vm", 405, 140, "vm", "", s=54)
d.group("p1p", 160, 300, 300, 170, "PE spoke 10.2.0.0/16", "spoke", fs=14)
d.icon("p1pe1", 220, 360, "pe", "", s=50)
d.icon("p1pe2", 340, 360, "pe", "", s=50)
d.edge("p1e1", "p1vm", "p1fw", "", "green")
d.edge("p1e2", "p1fw", "p1p", "", "green", ex=0.5, ey=1, nx=0.2, ny=0)
d.note("p1n", 40, 500, 530, 320,
       "<b>Routes</b>: app subnets: 10.2.0.0/16 → ILB<br>Network policies on snet-pe<br><br>+ one place for DNS zone groups, NSGs and firewall objects<br>+ clean zone boundary, easy to scale<br>"
       "− shared VNet needs clear ownership and RBAC", fs=16)
d.group("p2", 615, 30, 570, 810, "2 · Private endpoints in the hub", "plain", fs=19)
d.group("p2h", 635, 90, 530, 230, "Hub  10.0.0.0/16", "hub", fs=14)
d.fw("p2fw", 690, 160, "", s=56)
d.group("p2s", 880, 120, 260, 170, "snet-pe  10.0.4.0/24", "subnet", fs=14)
d.icon("p2pe", 985, 180, "pe", "", s=50)
d.group("p2a", 635, 350, 530, 120, "App spoke", "spoke", fs=14)
d.icon("p2vm", 870, 380, "vm", "", s=54)
d.edge("p2e1", "p2vm", "p2fw", "", "green", ex=0, ey=0.5, nx=0.5, ny=1, pts=[(718, 407)])
d.edge("p2e2", "p2fw", "p2pe", "", "green")
d.note("p2n", 635, 500, 530, 320,
       "<b>Routes</b>: spokes: 10.0.4.0/24 → ILB (more specific than the hub space, so it works)<br>GatewaySubnet: 10.0.4.0/24 → ILB<br><br>+ fewer VNets, hub teams own it<br>"
       "− hub grows, and anything else in the hub reaches the PEs directly", fs=16)
d.group("p3", 1210, 30, 570, 810, "3 · Private endpoint in the workload spoke", "plain", fs=19)
d.group("p3s", 1230, 90, 530, 230, "App spoke  10.1.0.0/16", "spoke", fs=14)
d.group("p3a", 1250, 130, 220, 170, "snet-app", "subnet", fs=14)
d.icon("p3vm", 1335, 185, "vm", "", s=54)
d.group("p3p", 1510, 130, 230, 170, "snet-pe 10.1.5.0/24", "subnet", fs=14)
d.icon("p3pe", 1600, 185, "pe", "", s=50)
d.group("p3h", 1230, 350, 530, 120, "Hub", "hub", fs=14)
d.fw("p3fw", 1465, 380, "", s=56)
d.edge("p3e1", "p3vm", "p3fw", "", "green", ex=0.5, ey=1, nx=0, ny=0.5, pts=[(1362, 408)])
d.edge("p3e2", "p3fw", "p3pe", "", "green", ex=1, ey=0.5, nx=0.5, ny=1, pts=[(1625, 408)])
d.note("p3n", 1230, 500, 530, 320,
       "<b>Routes</b>: snet-app: 10.1.5.0/24 → ILB (subnet-to-subnet inside one VNet)<br>Network policies on snet-pe<br><br>+ app team owns its endpoint<br>"
       "− easy to forget, DNS and policy sprawl across many spokes", fs=16)

# ---------------------------------------------------------------- hybrid routing
d = Diagram("hybrid"); D["hybrid"] = d
d.group("onprem", 20, 200, 300, 380, "On-premises", "onprem")
d.icon("users", 130, 320, "users", "Client<br>172.16.5.20", s=58)
d.icon("er", 360, 365, "er", "ExpressRoute", s=50)
d.group("hub", 470, 80, 720, 640, "Hub VNet", "hub")
d.group("sgw", 500, 260, 220, 420, "GatewaySubnet", "subnet", fs=14)
d.icon("gw", 580, 330, "gw", "ER gateway", s=58)
d.icon("gwudr", 585, 520, "udr", "UDR<br>10.2.0.0/16 → 10.0.2.100<br>propagation stays ON", s=50, lw=210)
d.icon("ilb", 820, 330, "lb", "ILB 10.0.2.100", s=58)
d.fw("fw", 1030, 320, "VM-Series", s=66)
d.group("sp2", 1260, 200, 510, 380, "Spoke 2 · Private endpoints", "spoke")
d.icon("pe", 1370, 300, "pe", "PE sql 10.2.1.4", s=60)
d.note("pol", 1290, 430, 450, 120, "Network policies on snet-pe, so the gateway doesn't learn the /32 bypass route", sty="good", fs=16)
d.edge("h0", "users", "er", "", "gray", arrow=False)
d.edge("h1", "er", "gw", "", "gray", arrow=False)
d.edge("h2", "gw", "ilb", "", "green")
d.edge("h3", "ilb", "fw", "", "green")
d.edge("h4", "fw", "pe", "", "green")
d.edge("hb", "gw", "pe", "without the GatewaySubnet UDR: straight to the PE", "red", dashed=True, ex=0.5, ey=0, nx=0.5, ny=0,
       pts=[(609, 140), (1399, 140)])
d.note("ret", 20, 750, 1760, 90,
       "<b>Return path</b>: the firewall routes 172.16.0.0/16 out of the trust interface; the PE subnet replies via SNAT or the disableSnatOnPL path. "
       "Never put a default route on GatewaySubnet, and don't disable gateway route propagation there.", fs=17)

# ---------------------------------------------------------------- PAN-OS policy
d = Diagram("panpol"); D["panpol"] = d
d.fw("fw", 855, 40, "VM-Series (PAN-OS)", s=90, fs=17)
d.note("ifc", 20, 30, 790, 370,
       "<b>Interfaces, zones, routing</b><br>ethernet1/1 · untrust 10.0.1.4 · zone UNTRUST<br>ethernet1/2 · trust 10.0.2.4 · zone TRUST<br>"
       "Static routes:<br>&nbsp;0.0.0.0/0 → 10.0.1.1 (ethernet1/1)<br>&nbsp;10.0.0.0/8, 172.16.0.0/16 → 10.0.2.1 (ethernet1/2)<br>"
       "&nbsp;168.63.129.16/32 → each interface's subnet gateway (LB probes)<br>Interface mgmt profile: HTTPS from 168.63.129.16 only", fs=16)
d.note("obj", 990, 30, 790, 370,
       "<b>Objects</b><br>Address: pe-sql 10.2.1.4 · pe-blob 10.2.1.5 · pe-kv 10.2.1.6<br>"
       "FQDN: stgdemo.blob.core.windows.net (firewall DNS = 10.0.3.4, so it resolves to the private IP)<br>"
       "Dynamic Address Groups: VNet, subnet and tag data from the Panorama Azure plugin<br>"
       "Custom URL category: *.blob.core.windows.net, *.vault.azure.net (SNI match)", fs=16)
d.note("rules", 20, 430, 1760, 410, "<b>Security policy (top-down)</b>" + table([
    ["#", "Name", "Source", "Destination", "Application", "Service", "Action / profiles"],
    ["1", "app-to-sql", "TRUST · snet-app", "pe-sql", "mssql-db", "tcp/1433 (Proxy policy)", "allow · AV, vulnerability, spyware"],
    ["2", "app-to-blob", "TRUST · snet-app", "pe-blob", "ssl", "tcp/443", "allow · URL category = your accounts"],
    ["3", "onprem-to-kv", "TRUST · 172.16.0.0/16", "pe-kv", "ssl", "tcp/443", "allow · logging"],
    ["4", "deny-to-pe", "any", "PE subnets", "any", "any", "deny · log"],
    ["—", "intrazone-default", "override", "", "", "", "<b>deny + log</b> (spoke-to-spoke is intrazone TRUST)"],
    ["NAT", "pe-snat", "TRUST", "PE subnets", "", "", "source NAT to ethernet1/2 (skip if disableSnatOnPL)"],
], widths=[5, 13, 16, 13, 11, 17, 25], px=1720, fs=17), fs=18)

# ---------------------------------------------------------------- VNet injection
d = Diagram("inject"); D["inject"] = d
d.group("hub", 20, 80, 500, 560, "Hub VNet", "hub")
d.icon("ilb", 80, 290, "lb", "ILB", s=56)
d.fw("fw", 300, 280, "VM-Series", s=66)
d.group("sp", 600, 80, 1180, 560, "Spoke · delegated / dedicated subnets", "spoke")
d.group("s1", 630, 140, 350, 230, "snet-sqlmi (delegated)", "subnet", fs=14)
d.icon("sqlmi", 770, 200, "sqlmi", "SQL Managed Instance", s=60)
d.group("s2", 1010, 140, 360, 230, "snet-ase", "subnet", fs=14)
d.icon("ase", 1160, 200, "ase", "App Service Environment v3", s=60, lw=230)
d.group("s3", 1400, 140, 350, 230, "snet-apim", "subnet", fs=14)
d.icon("apim", 1545, 200, "apim", "API Management (injected)", s=60, lw=230)
d.note("rules", 630, 400, 1120, 220,
       "• A default route to the ILB is allowed on these subnets, but keep the routes and NSG rules each service requires for its management plane<br>"
       "• SQL MI service-aided configuration adds its own routes and NSG rules, so don't fight them<br>"
       "• Allow each service's dependencies on the firewall: Entra ID, monitoring, storage, and for AKS the container registries<br>"
       "• East-west to these subnets is just like VM traffic: UDR + firewall rules", fs=16)
d.cloud("mgmt", 620, 680, 380, 150, "Azure management plane<br>(service tags)")
d.edge("m1", "s1", "mgmt", "", "gray", dashed=True, ex=0, ey=0.8, nx=0.5, ny=0, pts=[(615, 324), (615, 660), (810, 660)])
d.note("hubn", 40, 420, 460, 200, "Firewall rules for each service's documented dependencies; log and deny everything else", fs=16)
d.edge("pe1", "hub", "sp", "peering", "blue", dashed=True, ex=1, ey=0.5, nx=0, ny=0.5)
d.note("aks", 1040, 680, 740, 150, "Also in this family: AKS (egress via UDR outbound type), Databricks, Azure Container Apps environments, Application Gateway", fs=16)

# ---------------------------------------------------------------- egress from App Service
d = Diagram("egress"); D["egress"] = d
d.group("apps", 20, 100, 330, 420, "App Service (multi-tenant)", "paas")
d.icon("app", 140, 190, "app", "Web App", s=62)
d.note("flag", 40, 330, 290, 160, "outboundVnetRouting<br>.allTraffic = <b>true</b><br>(route all)", fs=16, align="center")
d.group("sp", 420, 100, 440, 420, "Spoke 1", "spoke")
d.group("sint", 445, 150, 390, 340, "snet-integration<br>delegated Microsoft.Web/serverFarms", "subnet", fs=14)
d.icon("udr", 615, 320, "udr", "UDR default route<br>→ 10.0.2.100", s=52, lw=170)
d.group("hub", 930, 100, 420, 420, "Hub VNet", "hub")
d.icon("ilb", 970, 270, "lb", "ILB", s=56)
d.fw("fw", 1170, 260, "VM-Series<br>App-ID + URL filtering", s=66)
d.cloud("inet", 1420, 80, 350, 170, "Internet / SaaS APIs")
d.group("paas", 1420, 300, 350, 220, "PaaS via private endpoints", "paas")
d.icon("sql", 1470, 360, "sql", "SQL", s=54)
d.icon("kv", 1640, 360, "kv", "Key Vault", s=54)
d.edge("x1", "app", "sint", "", "blue", ex=1, ey=0.5, nx=0, ny=0.3)
d.edge("x2", "sint", "ilb", "", "blue", ex=1, ey=0.5, nx=0, ny=0.5)
d.edge("x3", "ilb", "fw", "", "blue")
d.edge("x4", "fw", "inet", "SNAT to public IP", "orange", ex=0.5, ey=0, nx=0.2, ny=0.8)
d.edge("x5", "fw", "paas", "to PEs", "green", ex=1, ey=0.6, nx=0, ny=0.5)
d.note("notes", 20, 570, 1750, 260,
       "• Route all sends application <b>and</b> configuration traffic (image pulls, content share, backups, managed identity tokens) into the subnet<br>"
       "• Allow 443 (and 445 for a content share) from the integration subnet on the firewall<br>"
       "• VNet integration is outbound only: inbound to the app still needs a private endpoint<br>"
       "• Functions (Premium / Flex), Logic Apps Standard and Container Apps follow the same idea with their own subnet", fs=18)

# ---------------------------------------------------------------- inbound
d = Diagram("inbound"); D["inbound"] = d
d.group("r1", 20, 15, 1760, 270, "1 · Front Door Premium → Private Link origin", "plain", fs=18)
d.icon("u1", 60, 110, "users", "Internet users", s=56)
d.icon("afd", 360, 105, "afd", "Front Door Premium<br>+ WAF", s=60)
d.fw("fw1", 640, 105, "Palo Alto<br>not in path", s=60)
d.icon("app1", 930, 105, "app", "App Service<br>public access off", s=60, lw=160)
d.note("n1", 1150, 55, 610, 210, "+ global edge, WAF and DDoS absorbed at Microsoft's edge<br>+ no public origin<br>− the hub firewall never sees this traffic<br>− Microsoft-managed PE: approve it on the app", fs=16)
d.edge("a1", "u1", "afd", "", "orange")
d.edge("a2", "afd", "app1", "Private Link origin", "purple", dashed=True, ex=0.5, ey=0, nx=0.5, ny=0, pts=[(390, 80), (960, 80)])
d.group("r2", 20, 295, 1760, 270, "2 · Application Gateway WAF → VM-Series → private endpoint", "plain", fs=18)
d.icon("u2", 60, 390, "users", "Internet users", s=56)
d.icon("agw", 290, 385, "agw", "App Gateway<br>WAF v2", s=60)
d.fw("fw2", 520, 385, "VM-Series", s=60)
d.icon("pe2", 740, 385, "pe", "PE", s=58)
d.icon("app2", 930, 385, "app", "App Service", s=60)
d.note("n2", 1150, 335, 610, 210, "+ WAF sees the real client IP and adds X-Forwarded-For<br>+ firewall adds IPS / App-ID on the back leg<br>UDR on the AppGW subnet: backend prefix → ILB<br>firewall SNATs toward the PE", fs=16)
d.edge("b1", "u2", "agw", "", "orange")
d.edge("b2", "agw", "fw2", "UDR", "blue")
d.edge("b3", "fw2", "pe2", "", "green")
d.edge("b4", "pe2", "app2", "", "purple", dashed=True)
d.group("r3", 20, 575, 1760, 270, "3 · VM-Series first (public LB + DNAT) → App Gateway or private endpoint", "plain", fs=18)
d.icon("u3", 60, 670, "users", "Internet users", s=56)
d.icon("plb", 290, 665, "lb", "Public LB", s=60)
d.fw("fw3", 520, 665, "VM-Series<br>DNAT + SNAT", s=60)
d.icon("agw3", 740, 665, "agw", "AppGW (private)<br>or PE", s=60, lw=150)
d.icon("app3", 930, 665, "app", "App Service", s=60)
d.note("n3", 1150, 615, 610, 210, "+ one internet edge, Threat Prevention first<br>− DNAT + SNAT: client IP only in firewall logs<br>− L7 visibility needs inbound decryption<br>Variant: Gateway Load Balancer chained to a public frontend", fs=16)
d.edge("c1", "u3", "plb", "", "orange")
d.edge("c2", "plb", "fw3", "", "orange")
d.edge("c3", "fw3", "agw3", "", "green")
d.edge("c4", "agw3", "app3", "", "purple", dashed=True)

# ---------------------------------------------------------------- NSP
d = Diagram("nsp"); D["nsp"] = d
d.group("nsp", 480, 60, 840, 560, "Network Security Perimeter  nsp-data  (profile: default)", "good", fs=18)
d.icon("blob", 560, 160, "blob", "Storage", s=60)
d.icon("kv", 800, 160, "kv", "Key Vault", s=60)
d.icon("law", 1040, 160, "law", "Log Analytics", s=60)
d.edge("in1", "kv", "law", "diagnostics stay inside", "green")
d.note("rules", 650, 330, 640, 260,
       "<b>Inbound access rules</b>: IP prefixes or subscriptions<br><b>Outbound access rules</b>: FQDNs<br>"
       "<b>Access mode</b>: Transition (learn, log) → Enforced<br><b>Access logs</b> for every allowed and denied call", fs=17)
d.icon("pub", 90, 140, "users", "Public clients", s=56)
d.fw("fw", 90, 400, "VM-Series egress<br>20.55.10.7", s=62)
d.edge("x1", "pub", "blob", "denied", "red", dashed=True)
d.edge("x2", "fw", "blob", "inbound IP rule", "green", ex=1, ey=0.5, nx=0.3, ny=1, pts=[(578, 431)])
d.group("sp", 1400, 60, 380, 560, "Spoke VNet", "spoke")
d.icon("pe", 1560, 160, "pe", "Private endpoint", s=60)
d.edge("x3", "pe", "blob", "private traffic: not governed by NSP", "purple", dashed=True, ex=0.5, ey=1, nx=0.8, ny=1,
       pts=[(1589, 300), (608, 300)])
d.note("bottom", 20, 660, 1760, 180,
       "<b>NSP complements the firewall</b>: it governs the public side of PaaS and PaaS-to-PaaS calls, while the VM-Series governs your VNets. "
       "When public network access is set to \"secured by perimeter\", the perimeter's rules decide who gets in. Coverage differs by service (GA vs preview), so check before you rely on it.", fs=18)

# ---------------------------------------------------------------- form factors
d = Diagram("forms"); D["forms"] = d
d.group("c1", 20, 30, 570, 810, "VM-Series in the hub VNet", "hub", fs=19)
d.icon("c1plb", 90, 110, "lb", "Public LB", s=54)
d.fw("c1f1", 230, 230, "FW1", s=58)
d.fw("c1f2", 380, 230, "FW2", s=58)
d.icon("c1ilb", 300, 380, "lb", "ILB · HA ports", s=54)
d.edge("c1a", "c1plb", "c1f1", "", "orange")
d.edge("c1b", "c1ilb", "c1f1", "", "blue")
d.edge("c1c", "c1ilb", "c1f2", "", "blue")
d.note("c1n", 40, 490, 530, 330,
       "• You run the VMs: sizing, zones, upgrades, bootstrap, VMSS autoscale<br>• Full PAN-OS: GlobalProtect, decryption, every profile<br>"
       "• Panorama + Azure plugin for Dynamic Address Groups<br>• Active/active behind load balancers, or active/passive with floating IPs", fs=16)
d.group("c2", 615, 30, 570, 810, "Cloud NGFW for Azure in the hub VNet", "hub", fs=19)
d.group("c2pub", 640, 100, 520, 110, "public subnet (delegated)", "subnet", fs=14)
d.fw("c2fw", 870, 240, "Cloud NGFW (SaaS)", s=64)
d.group("c2prv", 640, 350, 520, 110, "private subnet (delegated)", "subnet", fs=14)
d.note("c2n", 635, 490, 530, 330,
       "• Azure-native ISV service: Palo Alto runs scaling and HA<br>• Spokes send traffic with a UDR to its private IP<br>"
       "• Policy from a local rulestack, Panorama, or Strata Cloud Manager<br>• Fewer knobs than full PAN-OS; check the feature matrix", fs=16)
d.group("c3", 1210, 30, 570, 810, "Cloud NGFW in a Virtual WAN hub", "hub", fs=19)
d.icon("c3hub", 1420, 120, "vhub", "vWAN hub", s=70)
d.fw("c3fw", 1430, 260, "Cloud NGFW", s=60)
d.edge("c3a", "c3hub", "c3fw", "routing intent", "blue")
d.note("c3n", 1230, 490, 530, 330,
       "• Routing intent: private and internet traffic → Cloud NGFW, no UDRs to maintain<br>• Inter-hub and branch traffic inspected too<br>"
       "• Private endpoints: enable route-table network policies on their subnets for symmetry<br>• Best when you already run vWAN", fs=16)

# ---------------------------------------------------------------- defense in depth
d = Diagram("gov"); D["gov"] = d
layers = [
    ("L1", "mi", "Identity", "Entra ID auth and managed identities; turn off shared keys and local auth (storage shared key, SQL Entra-only)"),
    ("L2", "pe", "Resource network", "Public network access disabled; private endpoints only; NSP for the public side that must stay"),
    ("L3", "nsg", "Subnet", "PE network policies on; NSG with ASGs on snet-pe allows only the firewall or SNAT sources"),
    ("L4", "lb", "Palo Alto VM-Series", "App-ID, Threat Prevention, URL/FQDN control, decryption where possible, deny-and-log by default"),
    ("L5", "policy", "Governance", "Azure Policy: deny public network access, deploy private DNS zone groups, audit missing endpoints; Defender for Cloud"),
    ("L6", "sentinel", "Observability", "Firewall logs to Strata Logging Service or Sentinel; Azure Monitor and NSP access logs; Network Watcher"),
]
for i, (cid, ic, t, body) in enumerate(layers):
    y = 20 + i * 138
    d.note(cid, 230, y, 1540, 122, '<span style="font-size:22px;font-weight:bold">%s</span><br><span style="font-size:21px">%s</span>' % (t, body),
           sty="good" if cid == "L4" else "plain")
    if cid == "L4":
        d.fw(cid + "i", 130, y + 28, "", s=64)
    else:
        d.icon(cid + "i", 130, y + 30, ic, "", s=60)

# ---------------------------------------------------------------- troubleshooting
d = Diagram("trouble"); D["trouble"] = d
steps = [
    ("T1", "dnsz", "1 · DNS", "From the client: nslookup stgdemo.blob.core.windows.net must show the privatelink CNAME and 10.2.1.5. A public IP here means a zone link or forwarder is missing."),
    ("T2", "udr", "2 · Routes", "Effective routes on the client NIC: the PE prefix → virtual appliance, and no active /32 InterfaceEndpoint route. The PE's own NIC doesn't show effective routes, so check the client side."),
    ("T3", "fw", "3 · Firewall", "Monitor → Traffic, filter on the PE subnet: right rule, NAT applied, session end reason. No log at all means the packet never reached the firewall."),
    ("T4", "pe", "4 · Endpoint", "Connection state Approved; if NSGs are on for snet-pe, they must allow the firewall's SNAT address or the real client range."),
    ("T5", "watcher", "5 · Symmetry", "Works with SNAT but not without? Check the disableSnatOnPL tag on every dataplane NIC and that both directions use the same ILB frontend."),
]
for i, (cid, ic, t, body) in enumerate(steps):
    y = 20 + i * 166
    d.note(cid, 230, y, 1540, 148, '<span style="font-size:22px;font-weight:bold">%s</span><br><span style="font-size:21px">%s</span>' % (t, body))
    if ic == "fw":
        d.fw(cid + "i", 130, y + 40, "", s=64)
    else:
        d.icon(cid + "i", 130, y + 42, ic, "", s=60)

# ---------------------------------------------------------------- decision matrix
d = Diagram("decide"); D["decide"] = d
d.note("m", 20, 20, 1760, 820, table([
    ["Option", "Through the Palo Alto?", "On-prem private path", "Exfiltration control", "Effort", "Use it when"],
    ["A · Public endpoint + IP rule", "Yes (egress)", "No", "Firewall FQDN rules only", "Low", "Quick start, service has no Private Link"],
    ["B · Service endpoint on firewall subnet", "Yes", "No", "Endpoint policies (Storage)", "Low", "Cheap Azure-only access to a few services"],
    ["<b>C · Private endpoint + UDR</b>", "<b>Yes, with network policies</b>", "<b>Yes</b>", "<b>Strong (per resource)</b>", "Medium", "<b>Default for production</b>"],
    ["D · VNet injection", "Yes (like VMs)", "Yes", "Strong", "High", "Dedicated tiers: SQL MI, ASE, APIM, AKS"],
    ["E · VNet integration, route all", "Yes (app egress)", "Yes", "Firewall egress policy", "Low", "App Service / Functions calling out"],
    ["F · Front Door PL / AppGW / DNAT", "Depends on pattern", "n/a", "WAF + firewall", "Medium", "Publishing apps to the internet"],
    ["G · Network Security Perimeter", "No (PaaS side)", "No", "Perimeter rules + logs", "Low", "PaaS-to-PaaS and public PaaS that must stay"],
], widths=[20, 16, 13, 17, 8, 26], px=1720, fs=23) +
    '<div style="font-size:25px;margin-top:30px"><b>Rule of thumb</b>: private endpoints in a dedicated spoke, network policies on, a UDR per PE prefix to the ILB, '
    'SNAT or disableSnatOnPL, the resolver for DNS, public access off, and Azure Policy to keep it that way. Add E for egress, F for publishing, G for what can\'t go private.</div>',
    fs=18)
