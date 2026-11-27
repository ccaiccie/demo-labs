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


def base(d):
    """Shared topology: hub with VM-Series + ILB, two spokes that each hold an app subnet and a PE subnet."""
    d.group("onprem", 10, 190, 210, 240, "On-premises", "onprem")
    d.icon("users", 85, 250, "users", "Clients<br>172.16.0.0/16", s=50)
    d.group("hub", 250, 30, 570, 520, "Hub VNet  10.0.0.0/16", "hub")
    d.group("sgw", 270, 70, 190, 240, "GatewaySubnet", "subnet", fs=14)
    d.icon("gw", 340, 100, "gw", "ER / VPN gateway", s=46)
    d.icon("gwudr", 345, 205, "udr", "rt-gateway", s=38)
    d.group("strust", 480, 70, 320, 300, "snet-trust  10.0.2.0/24", "subnet", fs=14)
    d.fw("fw", 530, 110, "VM-Series<br>10.0.2.4", lw=120)
    d.icon("ilb", 600, 270, "lb", "ILB · HA ports<br>10.0.2.100", s=46)
    d.icon("zones", 340, 390, "dnsz", "privatelink zones<br>linked to every VNet", s=46)
    d.group("sp1", 870, 20, 910, 260, "Spoke 1  10.1.0.0/16", "spoke")
    d.group("sapp1", 890, 60, 310, 205, "snet-app  10.1.1.0/24", "subnet", fs=14)
    d.icon("vm1", 950, 105, "vm", "vm1<br>10.1.1.4", s=50)
    d.icon("udr1", 1105, 180, "udr", "rt-spoke1-app", s=40)
    d.group("spe1", 1220, 60, 540, 205, "snet-pe  10.1.2.0/24 · network policies Enabled", "subnet", fs=14)
    d.icon("pe1b", 1285, 105, "pe", "PE blob<br>10.1.2.4", s=48)
    d.icon("pe1k", 1460, 105, "pe", "PE vault<br>10.1.2.5", s=48)
    d.icon("nsg1", 1640, 110, "nsg", "NSG", s=40)
    d.group("sp2", 870, 300, 910, 250, "Spoke 2  10.2.0.0/16", "spoke")
    d.group("sapp2", 890, 340, 310, 195, "snet-app  10.2.1.0/24", "subnet", fs=14)
    d.icon("vm2", 950, 380, "vm", "vm2<br>10.2.1.4", s=50)
    d.icon("udr2", 1105, 450, "udr", "rt-spoke2-app", s=40)
    d.group("spe2", 1220, 340, 540, 195, "snet-pe  10.2.2.0/24 · network policies Enabled", "subnet", fs=14)
    d.icon("pe2b", 1285, 380, "pe", "PE blob<br>10.2.2.4", s=48)
    d.icon("nsg2", 1640, 385, "nsg", "NSG", s=40)
    d.edge("e_p1", "hub", "sp1", "peering", "gray", dashed=True, ex=1, ey=0.2, nx=0, ny=0.4)
    d.edge("e_p2", "hub", "sp2", "peering", "gray", dashed=True, ex=1, ey=0.8, nx=0, ny=0.5)
    d.edge("e_op", "users", "gw", "ER / VPN", "gray", ex=1, ey=0.5, nx=0, ny=0.5)


BASE = ["onprem", "users", "hub", "sgw", "gw", "strust", "fw", "ilb", "zones", "sp1", "sapp1", "vm1", "spe1", "pe1b", "pe1k",
        "sp2", "sapp2", "vm2", "spe2", "pe2b", "e_p1", "e_p2", "e_op"]

# ---------------------------------------------------------------- title
d = Diagram("title"); D["title"] = d
d.note("t1", 120, 110, 1560, 210,
       '<div style="font-size:52px;font-weight:bold;color:#201F1E">Private endpoints in spoke VNets:<br>forcing the traffic through a Palo Alto in the hub</div>',
       sty="none", align="center")
d.note("t2", 150, 340, 1500, 70,
       '<div style="font-size:27px;color:#605E5C">Why traffic bypasses the firewall, the routing rule that fixes it, symmetry, PAN-OS, and a Terraform test lab</div>',
       sty="none", align="center")
d.icon("ti1", 560, 470, "vm", "Spoke workload", s=74, fs=18)
d.icon("ti2", 760, 470, "udr", "Route table", s=74, fs=18)
d.fw("ti3", 960, 470, "VM-Series", s=76, fs=18)
d.icon("ti4", 1160, 470, "pe", "Private endpoint", s=74, fs=18)
d.note("t3", 150, 660, 1500, 110,
       '<div style="font-size:22px;color:#323130">Use case: every spoke keeps its own private endpoints next to its workloads. '
       'Goal: every connection to them is inspected and logged by the firewall.</div>', sty="none", align="center")

# ---------------------------------------------------------------- problem
d = Diagram("problem"); D["problem"] = d
base(d)
d.edge("e_byp", "vm1", "pe1b", "direct: firewall never sees it", "red", dashed=True, ex=1, ey=0.3, nx=0, ny=0.3)
d.note("rt", 20, 580, 1000, 270, "<b>Effective routes on vm1 (no fix yet)</b>" + table([
    ["Prefix", "Next hop", "Source", "Result"],
    ["10.1.2.4/32", "InterfaceEndpoint", "Default (private endpoint)", "<b>wins for the blob endpoint</b>"],
    ["10.1.0.0/16", "VnetLocal", "Default", "covers everything else in spoke 1"],
    ["10.2.0.0/16", "10.0.2.100", "User", "spoke 2 goes via the firewall"],
    ["0.0.0.0/0", "10.0.2.100", "User", "never beats the two above"],
], widths=[20, 22, 30, 28], px=950, fs=16), fs=17)
d.note("why", 1050, 580, 730, 270,
       "<b>Two things send it around the firewall</b><br><br>"
       "1. Inside a VNet, traffic between subnets is <b>VnetLocal</b>: no hop, no appliance.<br>"
       "2. Each private endpoint injects a <b>/32</b> route into its VNet and every peered VNet. Longest prefix wins, so a default route never catches it.",
       sty="bad", fs=17)

# ---------------------------------------------------------------- rule
d = Diagram("rule"); D["rule"] = d
d.note("rt", 20, 20, 1000, 330, "<b>Which UDR on snet-app overrides the endpoint's /32?</b>  (PE in spoke 1, VNet 10.1.0.0/16)" + table([
    ["UDR prefix", "Network policies off", "Network policies on"],
    ["0.0.0.0/0", "no", "<b>no</b>: shorter than the VNet prefix"],
    ["10.0.0.0/8", "no", "<b>no</b>: shorter than the VNet prefix"],
    ["10.1.0.0/16 (the VNet)", "no", "yes, but all intra-VNet traffic hairpins"],
    ["10.1.2.0/24 (the PE subnet)", "no", "<b>yes: recommended</b>"],
    ["10.1.2.4/32 (one endpoint)", "yes (longest match)", "yes, but one route per endpoint"],
], widths=[34, 28, 38], px=950, fs=19), fs=19)
d.note("pol", 1050, 20, 730, 620,
       "<b>The switch: privateEndpointNetworkPolicies</b><br><br>"
       "Set on the <b>subnet that hosts the endpoints</b>, not the client subnet.<br><br>"
       "• <b>RouteTableEnabled</b>: UDRs may override the /32<br>"
       "• <b>NetworkSecurityGroupEnabled</b>: NSGs apply to endpoints<br>"
       "• <b>Enabled</b>: both (use this)<br><br>"
       "Terraform:<br><code>private_endpoint_network_policies = \"Enabled\"</code><br><br>"
       "The rule: the UDR prefix must be <b>at least as long</b> as the endpoint VNet's prefix.",
       sty="good", fs=18)
d.note("tip", 20, 380, 1000, 260,
       "<b>Why the PE subnet route is the sweet spot</b><br>"
       "One route per spoke instead of one per endpoint, so you stay far below the 400-route limit. It only redirects traffic to endpoints, so app-to-app traffic inside the spoke stays local. "
       "New endpoints in that subnet are covered automatically. Keep endpoints in their own subnet so the prefix means exactly \"private endpoints\".",
       fs=18)

# ---------------------------------------------------------------- flows
d = Diagram("flows"); D["flows"] = d
base(d)
d.edge("f1", "vm1", "pe1b", "1 · same spoke", "orange", ex=1, ey=0.3, nx=0, ny=0.3, w=3)
d.edge("f2", "vm2", "pe1k", "2 · cross spoke", "purple", ex=1, ey=0.2, nx=0.5, ny=1, pts=[(1240, 390), (1240, 290), (1484, 290)], w=3)
d.edge("f3", "users", "pe2b", "3 · on-premises", "teal", ex=0.5, ey=1, nx=0.5, ny=1, pts=[(110, 565), (1309, 565)], w=3)
d.note("fl", 20, 590, 1760, 260, "<b>Three flows, three different reasons they need a route</b>" + table([
    ["Flow", "Why it bypasses or fails today", "Route that fixes it", "Where"],
    ["1 · vm1 → PE in its own spoke", "VnetLocal and the /32 route", "PE subnet 10.1.2.0/24 → 10.0.2.100", "rt-spoke1-app"],
    ["2 · vm2 → PE in spoke 1", "Spokes aren't peered: no route at all (or a /32 if they are)", "10.1.0.0/16 → 10.0.2.100", "rt-spoke2-app"],
    ["3 · on-prem → PE in spoke 2", "Gateway learns spoke prefixes and the /32s over peering", "10.2.0.0/16 → 10.0.2.100", "rt-gateway"],
], widths=[24, 34, 26, 16], px=1700, fs=16), fs=17)

# ---------------------------------------------------------------- same spoke
d = Diagram("same"); D["same"] = d
base(d)
d.edge("e_byp", "vm1", "pe1b", "bypass removed", "red", dashed=True, ex=1, ey=0.3, nx=0, ny=0.3)
d.edge("s1", "vm1", "ilb", "", "green", ex=0, ey=0.8, nx=1, ny=0.5, pts=[(920, 145), (920, 293)], w=3)
d.edge("s2", "ilb", "fw", "", "green", ex=0.5, ey=0, nx=1, ny=0.75, w=3)
d.edge("s3", "fw", "pe1b", "inspected", "green", ex=1, ey=0.2, nx=0.5, ny=0, pts=[(840, 127), (840, 12), (1309, 12)], w=3)
d.note("rt", 20, 580, 900, 270, "<b>rt-spoke1-app</b> (bgp propagation off)" + table([
    ["Prefix", "Next hop", "Purpose"],
    ["10.1.2.0/24", "10.0.2.100", "own PE subnet via firewall"],
    ["10.2.0.0/16", "10.0.2.100", "other spoke via firewall"],
    ["0.0.0.0/0 (optional)", "10.0.2.100", "internet egress via firewall"],
], widths=[32, 24, 44], px=850, fs=16), fs=17)
d.note("eff", 950, 580, 830, 270, "<b>Effective routes on vm1 after the fix</b>" + table([
    ["Prefix", "Next hop", "State"],
    ["10.1.2.4/32", "InterfaceEndpoint", "<b>Invalid</b>"],
    ["10.1.2.0/24", "VirtualAppliance 10.0.2.100", "Active"],
    ["10.1.0.0/16", "VnetLocal", "Active (app traffic stays local)"],
], widths=[26, 40, 34], px=780, fs=16), sty="good", fs=17)

# ---------------------------------------------------------------- symmetry
d = Diagram("symm"); D["symm"] = d
base(d)
d.edge("s1", "vm1", "ilb", "", "green", ex=0, ey=0.8, nx=1, ny=0.5, pts=[(920, 145), (920, 293)], w=3)
d.edge("s2", "ilb", "fw", "", "green", ex=0.5, ey=0, nx=1, ny=0.75, w=3)
d.edge("s3", "fw", "pe1b", "src 10.0.2.4 after SNAT", "green", ex=1, ey=0.2, nx=0.5, ny=0, pts=[(840, 127), (840, 12), (1309, 12)], w=3)
d.edge("ret", "pe1b", "vm1", "no SNAT: reply goes straight back", "red", dashed=True, ex=0, ey=0.8, nx=1, ny=0.8)
d.note("tb", 20, 580, 1170, 270, "<b>Keep the return path on the firewall</b>" + table([
    ["Option", "What the endpoint sees", "NSG on snet-pe must allow"],
    ["PAN-OS source NAT to ethernet1/2", "firewall IPs (10.0.2.4, 10.0.2.5)", "the firewalls' SNAT IPs only"],
    ["disableSnatOnPL = true tag on the firewall NICs", "the real client IP", "the client subnets"],
    ["Neither", "client IP, reply bypasses the firewall", "asymmetric: session drops"],
], widths=[38, 32, 30], px=1120, fs=16), fs=17)
d.note("nsgn", 1220, 580, 560, 270,
       "<b>NSG gotcha</b><br>An NSG matches the source IP that arrives at the endpoint. "
       "\"Allow only the firewall\" proves the path <b>only with SNAT</b>. Without SNAT the NSG can't tell a firewalled packet from a bypass, so the route is your control.",
       sty="bad", fs=17)

# ---------------------------------------------------------------- cross spoke
d = Diagram("cross"); D["cross"] = d
base(d)
d.edge("c1", "vm2", "ilb", "10.1.0.0/16 → ILB", "purple", ex=0, ey=0.5, nx=1, ny=0.7, pts=[(920, 405), (920, 302)], w=3)
d.edge("c2", "ilb", "fw", "", "purple", ex=0.5, ey=0, nx=1, ny=0.75, w=3)
d.edge("c3", "fw", "pe1k", "SNAT → PE vault", "purple", ex=1, ey=0.2, nx=0.5, ny=0, pts=[(840, 127), (840, 12), (1484, 12)], w=3)
d.note("cn", 20, 580, 880, 270,
       "<b>Plain hub-and-spoke: already forced</b><br>Spokes are only peered to the hub, so spoke 2 has no route to spoke 1 except your UDR to the ILB. "
       "The hub learns spoke 1's prefix and the endpoint /32s over peering, so the firewall can reach them. Add the mirror route 10.2.0.0/16 on rt-spoke1-app.",
       sty="good", fs=17)
d.note("mesh", 930, 580, 850, 270,
       "<b>Watch out: spoke-to-spoke connectivity</b><br>Direct spoke peering, or a Virtual Network Manager mesh or connected group, propagates every endpoint /32 into the other spokes. "
       "Then the same rule applies: the UDR must be at least as long as the remote spoke's VNet prefix (10.1.0.0/16 or 10.1.2.0/24), and network policies must be on.",
       sty="bad", fs=17)

# ---------------------------------------------------------------- on-prem
d = Diagram("onprem"); D["onprem"] = d
base(d)
d.edge("o1", "gw", "ilb", "", "teal", ex=1, ey=0.5, nx=0, ny=0.5, pts=[(470, 123), (470, 293)], w=3)
d.edge("o2", "ilb", "fw", "", "teal", ex=0.5, ey=0, nx=1, ny=0.75, w=3)
d.edge("o3", "fw", "pe2b", "to PE blob 10.2.2.4", "teal", ex=1, ey=0.8, nx=0, ny=0.5, pts=[(840, 158), (840, 505), (1255, 505), (1255, 404)], w=3)
d.note("gt", 20, 580, 900, 270, "<b>rt-gateway on GatewaySubnet</b> (keep gateway route propagation <b>on</b>)" + table([
    ["Prefix", "Next hop", "Note"],
    ["10.1.0.0/16", "10.0.2.100", "spoke 1, includes its PE subnet"],
    ["10.2.0.0/16", "10.0.2.100", "spoke 2"],
    ["10.0.0.0/8", "—", "too short: the endpoint /32s still win"],
    ["0.0.0.0/0", "—", "never on GatewaySubnet"],
], widths=[26, 22, 52], px=850, fs=16), fs=17)
d.note("od", 950, 580, 830, 270,
       "<b>Also needed for on-premises</b><br>• Spokes peer with <b>use remote gateways</b>, so on-prem learns 10.1/16 and 10.2/16<br>"
       "• On-prem DNS forwards blob.core.windows.net and vault.azure.net to the DNS Private Resolver inbound IP<br>"
       "• Return traffic: the spoke's own route back to 172.16.0.0/16 via the ILB, or rely on SNAT", fs=17)

# ---------------------------------------------------------------- PAN-OS
d = Diagram("panos"); D["panos"] = d
d.fw("pfw", 60, 60, "VM-Series<br>one-arm on ethernet1/2", s=80, lpos="right", lw=260)
d.note("cfg", 20, 190, 1000, 650, "<b>Minimum PAN-OS configuration</b>" + table([
    ["Item", "Setting"],
    ["Zones", "ethernet1/1 untrust, ethernet1/2 trust"],
    ["Static route", "10.0.0.0/8 → 10.0.2.1 out ethernet1/2 (all spokes and endpoints)"],
    ["Probe route + profile", "168.63.129.16/32 → 10.0.2.1; mgmt profile allows HTTPS from it"],
    ["Security rule", "trust → trust, app-subnets → pe-subnets, ssl + web-browsing, log at end"],
    ["intrazone-default", "override to <b>deny</b> and log (spoke traffic is trust → trust)"],
    ["Source NAT", "trust → trust to pe-subnets, dynamic IP and port, interface ethernet1/2"],
    ["Optional", "custom URL category with your account and vault FQDNs (TLS SNI)"],
], widths=[28, 72], px=950, fs=17), fs=18)
d.note("why", 1050, 40, 730, 800,
       "<b>Why it looks like this</b><br><br>"
       "Traffic enters through the ILB on ethernet1/2 and leaves on ethernet1/2 toward the endpoint, so the firewall sees <b>trust → trust</b>.<br><br>"
       "PAN-OS allows intrazone traffic by default. Without the override, any spoke could reach any endpoint, and nothing gets logged.<br><br>"
       "SNAT keeps the reply on the same firewall behind the load balancer, and makes the NSG on snet-pe meaningful.<br><br>"
       "With two firewalls, keep the ILB's HA ports rule. Each flow sticks to one firewall in both directions.<br><br>"
       "The full set of commands is in <b>panos/fw-config.set</b> in the lab.",
       sty="good", fs=18)

# ---------------------------------------------------------------- guardrails
d = Diagram("guard"); D["guard"] = d
d.note("g1", 20, 20, 870, 400,
       "<b>Lock it so it can't drift</b><br><br>"
       "• NSG on every snet-pe: allow 443 from the firewall SNAT IPs, deny VirtualNetwork<br>"
       "• Azure Policy: deny PE subnets without network policies, deny public network access<br>"
       "• Every client subnet gets the spoke route table, including <b>App Service and Functions VNet integration subnets</b> (with all outbound traffic routed into the VNet)<br>"
       "• Virtual Network Manager routing configurations can push the same route tables to every spoke",
       fs=18)
d.note("g2", 910, 20, 870, 400,
       "<b>DNS doesn't change the path, but it must resolve privately</b><br><br>"
       "• privatelink.blob.core.windows.net and privatelink.vaultcore.azure.net live once, centrally<br>"
       "• Link them to the hub (resolver) or to every spoke<br>"
       "• Spokes use Azure DNS or the resolver; on-premises forwards to the resolver inbound IP<br>"
       "• Point the firewall's DNS at the resolver too, so FQDN objects match private IPs",
       fs=18)
d.note("g3", 20, 450, 1760, 390, "<b>Other layouts, if you can change where endpoints live</b>" + table([
    ["Layout", "Routes you maintain", "Trade-off"],
    ["Endpoints in each spoke (this lecture)", "one PE-subnet route per spoke + one per remote spoke", "teams own their endpoints; more route tables"],
    ["Dedicated private endpoint spoke", "one route for its address space", "Microsoft's most scalable pattern; central team owns endpoints"],
    ["Virtual WAN with routing intent", "none by hand: the hub NVA or Cloud NGFW attracts private traffic", "needs a supported NVA in the virtual hub"],
], widths=[30, 36, 34], px=1700, fs=17), fs=18)

# ---------------------------------------------------------------- terraform lab
d = Diagram("lab"); D["lab"] = d
base(d)
d.note("files", 20, 580, 860, 270, "<b>terraform/</b>  (azurerm 4.x, validated with Terraform 1.17)" + table([
    ["File", "What it builds"],
    ["main.tf", "hub, VM-Series (3 NICs) + ILB, two spokes, peering, route tables, NSGs, VMs, storage, vault, PEs, DNS"],
    ["panos/fw-config.set", "PAN-OS zones, routes, rules, NAT to paste and commit"],
    ["tests/run-tests.sh", "curl from both VMs + effective routes"],
], widths=[28, 72], px=820, fs=15), fs=17)
d.note("tog", 910, 580, 870, 270, "<b>Test toggles</b>" + table([
    ["Variable", "Effect"],
    ["steer_through_firewall", "true: PE subnet routes exist. false: same-spoke bypass"],
    ["snat_mode", "firewall_snat or disable_snat_on_pl (NIC tag + NSG sources)"],
    ["lock_pe_subnets_with_nsg", "NSG on snet-pe that only allows the firewall path"],
], widths=[38, 62], px=830, fs=15), sty="good", fs=17)

# ---------------------------------------------------------------- testing
d = Diagram("test"); D["test"] = d
d.note("mx", 20, 20, 1760, 430, "<b>Expected results from tests/run-tests.sh</b>" + table([
    ["Setting", "vm1 → blob/vault (same spoke)", "vm2 → vault (cross spoke)", "Firewall sessions"],
    ["steer = true, firewall_snat, NSG on", "HTTP 4xx (reached)", "HTTP 4xx", "both flows, source NAT 10.0.2.4"],
    ["steer = false, NSG on", "<b>000 timeout</b>: NSG drops source 10.1.1.4", "HTTP 4xx", "cross-spoke only"],
    ["steer = false, NSG off", "HTTP 4xx, <b>bypass</b>", "HTTP 4xx", "cross-spoke only: the gap"],
    ["disable_snat_on_pl, steer = true", "HTTP 4xx", "HTTP 4xx", "real client IPs logged"],
], widths=[28, 28, 18, 26], px=1700, fs=17), fs=18)
d.note("tr", 20, 480, 1760, 360, "<b>When it doesn't work</b>" + table([
    ["Symptom", "Check"],
    ["Still bypasses, no firewall session", "Network policies on the PE subnet? UDR prefix at least as long as the VNet's? Route table on the right subnet?"],
    ["Session in the firewall, then timeout", "Asymmetric return: add SNAT or the disableSnatOnPL tag"],
    ["Firewall log shows deny on intrazone-default", "Rule app-to-private-endpoints missing or the address groups are wrong"],
    ["Name resolves to a public IP", "Zone link missing for that VNet, or custom DNS not forwarding to Azure DNS"],
    ["ILB backend unhealthy", "Management profile on ethernet1/2 and the 168.63.129.16 route"],
], widths=[32, 68], px=1700, fs=17), sty="bad", fs=18)
