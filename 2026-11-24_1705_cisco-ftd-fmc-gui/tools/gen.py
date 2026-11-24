"""Concept diagrams for the FTD through FMC GUI lesson on CML.
Cisco 19 draw.io stencils, exported in build-up stages (stage k shows every
element whose stage range includes k)."""
import sys, subprocess, os
from dlib import D
B = "#049FD9"; CT = "#C0392B"; DA = "#1E8449"; GU = "#D35400"; MG = "#7D3C98"; G = "#5b6b7b"; NV = "#1F618D"
LB = "#eef6fb"; WB = "#ffffff"
DG = {}
def dg(name, title, sub, n):
    def w(f): DG[name] = (title, sub, n, f); return f
    return w
def tag(d, x, y, w, h, t, col, size=17, fill=None, bold=True):
    return d.box(x, y, w, h, t, fill=fill or WB, stroke=col, size=size, color=col if bold else "#1d2733", bold=bold, valign="middle")

# ------------------------------------------------------------ FMC vs FTD
@dg("arch", "Management Center and Threat Defense", "One manager, many firewalls: who does what", 3)
def _(d):
    d.st(0)
    adm = d.icon("user", 130, 250, "Admin (web browser)", 1.1)
    fmc = d.icon("server", 420, 250, "FMC1 (Management Center)", 1.4)
    d.edge(adm, fmc, "HTTPS", color=B, width=3, arrow="block")
    d.box(640, 140, 900, 230, "<b>Management plane: FMC</b><br>Objects, zones, interfaces, routing, access control, NAT<br>Licensing, health, upgrades<br>Stores the events the firewalls send back<br><i>The FMC never forwards a single user packet</i>", fill=LB, stroke=B, size=18, valign="middle", align="left")
    d.st(1)
    f1 = d.icon("firewall", 420, 560, "FTD1", 1.3); f2 = d.icon("firewall", 700, 560, "FTD2", 1.3)
    d.edge(fmc, f1, "sftunnel TCP 8305", color=MG, width=3, dashed=True, start="block", arrow="block", size=15)
    d.edge(fmc, f2, "", color=MG, width=3, dashed=True, start="block", arrow="block")
    d.box(860, 470, 680, 190, "<b>Data plane: FTD</b><br>Routes, NATs and inspects traffic (Lina + Snort)<br>Gets its whole configuration from the FMC<br>Sends connection and intrusion events to the FMC", fill="#f4ecf7", stroke=MG, size=18, valign="middle", align="left")
    d.st(2)
    d.box(60, 690, 1480, 70, "Policy is built once on the FMC, then <b>deployed</b> to every firewall that uses it. Change once, deploy everywhere.", fill="#eafaf1", stroke=DA, size=19, valign="middle")

# ------------------------------------------------------------ registration
@dg("reg", "How an FTD registers to the FMC", "Both sides must agree on the address and the registration key", 5)
def _(d):
    d.st(0)
    f = d.icon("firewall", 230, 400, "FTD1  192.168.122.71", 1.5)
    m = d.icon("server", 1370, 400, "FMC1  192.168.122.70", 1.5)
    steps = [
        ("1  Day 0 on the FTD: ManageLocally = No, FmcIp = 192.168.122.70, FmcRegKey", MG, 170),
        ("   (same as the CLI:  configure manager add 192.168.122.70 <key>)", G, 230),
        ("2  FMC GUI: Devices > Add Device: host, display name, the same key, policy, licenses", B, 330),
        ("3  sftunnel on TCP 8305: mutual certificate exchange, then a permanent encrypted channel", CT, 450),
        ("4  The FMC discovers the interfaces, assigns the policy and runs a first deployment", DA, 570),
    ]
    for i, (t, col, y) in enumerate(steps):
        d.st({0: 0, 1: 0, 2: 1, 3: 2, 4: 3}[i])
        d.text(380, y - 30, 840, 60, t, 18, bold=True, color=col, align="left")
        if i != 1: d.line(380, y + 20, 1250, y + 20, color=col, width=3, arrow="block" if i != 3 else "block", start="block" if i == 3 else "none", dashed=(i == 3))
    d.st(4)
    d.box(380, 650, 870, 100, "Gotcha: if the FTD was set up with <b>ManageLocally = Yes</b>, it runs Device Manager instead and will never register. That's why the day 0 config matters.", fill="#fdecea", stroke=CT, size=17, valign="middle")

# ------------------------------------------------------------ licensing
@dg("lic", "Smart Licensing in the lab: Evaluation Mode", "90 days of every feature, no Cisco account needed", 1)
def _(d):
    d.st(0)
    rows = [("Essentials", "Routing, NAT, access control, VPN basics (always required)", B),
            ("IPS", "Intrusion policies and Security Intelligence (formerly Threat)", CT),
            ("Malware Defense", "File and malware policies", GU),
            ("URL", "URL category and reputation filtering", DA)]
    for i, (n, t, col) in enumerate(rows):
        y = 130 + i * 120
        tag(d, 120, y, 300, 90, n, col, 22)
        d.box(450, y, 1030, 90, t, fill=WB, stroke=col, size=19, valign="middle", align="left")
    d.box(120, 640, 1360, 100, "Evaluation Mode is a button on <b>System > Licenses > Smart Licenses</b>. In production you register the FMC to Cisco Smart Software Manager instead.", fill=LB, stroke=B, size=18, valign="middle")

# ------------------------------------------------------------ topology
@dg("topo", "The lab topology in CML", "FMCv 10.0.1, two FTDv 10.0.0, an ISP router and four hosts", 4)
def _(d):
    d.st(0)
    d.box(110, 118, 1380, 44, "<b>MGMT</b>  192.168.122.0/24  (CML System Bridge, stays inside the server)", fill="#f4ecf7", stroke=MG, size=18, color=MG, valign="middle")
    fmc = d.icon("server", 800, 250, "FMC1  .70", 1.1)
    d.line(800, 162, 800, 215, color=MG, width=3, dashed=True)
    d.st(1)
    out = d.icon("switch", 800, 470, "OUT-SW", 0.9)
    isp = d.icon("router", 800, 610, "ISP  .1", 0.9)
    net = d.icon("cloud", 1060, 640, "Internet (CML NAT)", 0.75)
    oh = d.icon("pc", 1060, 470, "OUT-HOST  .50", 0.9)
    d.edge(isp, out, color=GU, width=3); d.edge(out, oh, color=GU, width=3)
    d.edge(isp, net, "e0/0 DHCP + NAT", color=G, width=2, size=14)
    d.text(640, 385, 330, 30, "OUTSIDE 198.51.100.0/24", 17, bold=True, color=GU)
    d.st(2)
    f1 = d.icon("firewall", 430, 470, "FTD1", 1.1)
    d.line(430, 162, 430, 432, color=MG, width=3, dashed=True, label="Mgmt0/0 .71", size=14)
    d.edge(f1, out, "Eth0/0  .11", color=GU, width=3, size=14)
    h1 = d.icon("pc", 220, 680, "HOST1  10.1.1.10", 0.9)
    w1 = d.icon("server", 520, 690, "WEB1  10.1.50.10", 0.8)
    d.edge(f1, h1, "Eth0/1 inside 10.1.1.1", color=DA, width=3, size=14)
    d.edge(f1, w1, "Eth0/2 dmz 10.1.50.1", color=NV, width=3, size=14)
    d.st(3)
    f2 = d.icon("firewall", 1330, 340, "FTD2", 1.1)
    d.line(1330, 162, 1330, 302, color=MG, width=3, dashed=True, label="Mgmt0/0 .72", size=14)
    d.edge(f2, out, "Eth0/0  .12", color=GU, width=3, size=14)
    h2 = d.icon("pc", 1350, 640, "HOST2  10.2.2.10", 0.9)
    d.edge(f2, h2, "Eth0/1 inside 10.2.2.1", color=DA, width=3, size=14)

# ------------------------------------------------------------ zones & interfaces
@dg("zones", "Interfaces and security zones", "Policies match zones, not interface names", 3)
def _(d):
    d.st(0)
    for col, (n, x) in zip((DA, GU, NV), (("INSIDE", 140), ("OUTSIDE", 640), ("DMZ", 1140))):
        d.box(x, 120, 340, 300, f"<b>Zone {n}</b>", fill=WB, stroke=col, size=22, color=col)
    d.st(1)
    m = [("FTD1 Eth0/1  inside  10.1.1.1/24", 140, DA, 190), ("FTD2 Eth0/1  inside  10.2.2.1/24", 140, DA, 270),
         ("FTD1 Eth0/0  outside  198.51.100.11/24", 640, GU, 190), ("FTD2 Eth0/0  outside  198.51.100.12/24", 640, GU, 270),
         ("FTD1 Eth0/2  dmz  10.1.50.1/24", 1140, NV, 190)]
    for t, x, col, y in m: tag(d, x + 15, y, 310, 62, t, col, 16, bold=False)
    d.st(2)
    d.box(140, 470, 1340, 230, "<b>Why zones?</b><br>A zone is a shared FMC object. Both firewalls put their inside interface in INSIDE, so one access rule <b>INSIDE → OUTSIDE</b> works on FTD1 and FTD2.<br>Each interface also gets a logical name (inside, outside, dmz) that routing and the CLI use.<br>Routed-mode interfaces need a name, a zone and an IP address before they pass traffic.", fill=LB, stroke=B, size=18, valign="middle", align="left")

# ------------------------------------------------------------ ACP
@dg("acp", "Access control policy LAB-ACP", "Rules are checked top-down. First match wins.", 3)
def _(d):
    d.st(0)
    rows = [("1", "Block-SSH-Out", "INSIDE → OUTSIDE", "SSH (TCP 22)", "Block", CT),
            ("2", "Allow-Inside-Out", "INSIDE → OUTSIDE", "any", "Allow", DA),
            ("3", "Allow-Web-DMZ", "OUTSIDE → DMZ   to WEB1", "HTTP (TCP 80)", "Allow", DA)]
    hdr = ["#", "Name", "Zones", "Ports", "Action"]; xs = [100, 170, 520, 960, 1260]; ws = [60, 340, 430, 290, 220]
    for x, w, h in zip(xs, ws, hdr): d.box(x, 120, w, 50, f"<b>{h}</b>", fill="#d6eaf8", stroke=B, size=18, valign="middle")
    for i, r in enumerate(rows):
        y = 180 + i * 80
        for j, (x, w) in enumerate(zip(xs, ws)):
            d.box(x, y, w, 66, r[j], fill=WB, stroke=r[5] if j == 4 else G, size=18, valign="middle", color=r[5] if j == 4 else "#1d2733", bold=(j == 4))
    d.box(100, 430, 1420, 60, "Default action:  <b>Block all traffic</b>  (anything no rule allows is dropped)", fill="#fdecea", stroke=CT, size=19, valign="middle")
    d.st(1)
    d.box(100, 520, 690, 200, "<b>Order matters</b><br>SSH from inside must hit rule 1 before rule 2 allows everything. Put rule 1 under rule 2 and it never matches.", fill=LB, stroke=B, size=18, valign="middle", align="left")
    d.st(2)
    d.box(830, 520, 690, 200, "<b>Rules match the real address</b><br>Rule 3 uses WEB1's inside address 10.1.50.10, not 198.51.100.110: on FTD the NAT is undone before access control looks at the packet.", fill="#eafaf1", stroke=DA, size=18, valign="middle", align="left")

# ------------------------------------------------------------ NAT
@dg("nat", "NAT policy LAB-NAT", "Outbound PAT for both sites and one published web server", 3)
def _(d):
    d.st(0)
    h = d.icon("pc", 170, 300, "HOST1 10.1.1.10", 1.0)
    f = d.icon("firewall", 720, 300, "FTD1", 1.2)
    n = d.icon("cloud", 1300, 300, "Internet", 0.9)
    d.edge(h, f, "src 10.1.1.10", color=DA, width=3, arrow="block", size=16)
    d.edge(f, n, "src 198.51.100.11 (port changed)", color=GU, width=3, arrow="block", size=16)
    d.text(140, 400, 1300, 40, "Rule 1 - dynamic, interface PAT: INSIDE → OUTSIDE, source INSIDE-NETS (10.0.0.0/8) becomes the outside interface address", 18, bold=True, color=DA)
    d.st(1)
    o = d.icon("pc", 1300, 560, "OUT-HOST 198.51.100.50", 1.0)
    w = d.icon("server", 170, 560, "WEB1 10.1.50.10", 1.0)
    f2 = d.icon("firewall", 720, 560, "FTD1", 1.2)
    d.edge(o, f2, "dst 198.51.100.110 : 80", color=GU, width=3, arrow="block", size=16)
    d.edge(f2, w, "dst 10.1.50.10 : 80", color=NV, width=3, arrow="block", size=16)
    d.text(140, 650, 1300, 40, "Rule 2 - static: DMZ → OUTSIDE, WEB1 ↔ WEB1-PUBLIC 198.51.100.110 (TCP 80 only)", 18, bold=True, color=NV)
    d.st(2)
    d.box(140, 700, 1320, 64, "One NAT policy, assigned to both firewalls. FTD2 has no DMZ zone, so only rule 1 applies there.", fill=LB, stroke=B, size=18, valign="middle")

# ------------------------------------------------------------ deploy
@dg("deploy", "Save is not Deploy", "Everything you change on the FMC is staged until you deploy it", 2)
def _(d):
    d.st(0)
    a = d.icon("user", 160, 330, "Admin", 1.1)
    m = d.icon("server", 620, 330, "FMC: saved, pending", 1.3)
    d.edge(a, m, "Save", color=B, width=3, arrow="block", size=18)
    d.box(380, 450, 480, 120, "Out-of-date devices show in the Deploy menu. The firewall is still running the old config.", fill="#fdf2e9", stroke=GU, size=17, valign="middle")
    d.st(1)
    f1 = d.icon("firewall", 1200, 230, "FTD1", 1.2); f2 = d.icon("firewall", 1200, 450, "FTD2", 1.2)
    d.edge(m, f1, "Deploy", color=DA, width=4, arrow="block", size=18); d.edge(m, f2, "Deploy", color=DA, width=4, arrow="block", size=18)
    d.box(960, 560, 560, 150, "The FMC compiles the policy into Lina (CLI) and Snort config and pushes it over sftunnel. Watch it under Deploy > Deployment History.", fill="#eafaf1", stroke=DA, size=17, valign="middle")

# ------------------------------------------------------------ tests
@dg("tests", "The test plan", "Proving every rule with real traffic", 1)
def _(d):
    d.st(0)
    items = [("HOST1 and HOST2 ping 8.8.8.8 and fetch a web page", "Allow-Inside-Out + PAT", DA),
             ("HOST1 tries SSH to OUT-HOST 198.51.100.50", "Block-SSH-Out", CT),
             ("OUT-HOST opens http://198.51.100.110", "static NAT + Allow-Web-DMZ", NV),
             ("OUT-HOST tries to reach HOST1 directly", "default action Block", CT),
             ("FMC Connection Events and the FTD CLI (show nat, show conn)", "proof on both sides", B)]
    for i, (t, r, col) in enumerate(items):
        y = 130 + i * 112
        d.box(100, y, 950, 88, f"<b>{i+1}.</b>  {t}", fill=LB if i % 2 == 0 else WB, stroke=B, size=19, valign="middle", align="left")
        tag(d, 1080, y, 420, 88, r, col, 18)

# ------------------------------------------------------------ lessons
@dg("lessons", "Lessons learned", "The things that matter when you build FTD through the FMC GUI", 2)
def _(d):
    d.st(0)
    items = ["Day 0 decides the manager: ManageLocally No plus FmcIp and the registration key",
             "Keep management on an isolated network (CML System Bridge), never a home LAN bridge",
             "The FMCv needs 32 GB and a long first boot; register the FTDs only once it's up",
             "Zones are shared objects: name them once, reuse them on every firewall",
             "Access rules are top-down, first match wins; blocks go above broad allows",
             "Access rules match real (untranslated) addresses",
             "Nothing changes on a firewall until you Deploy"]
    for i, t in enumerate(items):
        d.st(0 if i < 4 else 1)
        y = 120 + i * 92
        d.box(80, y, 1440, 76, f"<b>{i+1}.</b>  {t}", fill=LB if i % 2 == 0 else WB, stroke=B, size=19, valign="middle", align="left")

def render(names=None, last=False):
    os.makedirs("png", exist_ok=True); os.makedirs("src", exist_ok=True)
    jobs = []
    for name, (title, sub, n, f) in DG.items():
        if names and name not in names: continue
        for k in ([n-1] if last else range(n)):
            d = D(title=title, sub=sub or None, k=k); f(d)
            fn = f"{name}_{k}"; d.save(fn); jobs.append(fn)
    for fn in jobs:
        subprocess.run(f"timeout 120 nice xvfb-run -a drawio --no-sandbox --disable-gpu -x -f png --border 0 -o png/{fn}.png src/{fn}.drawio >/dev/null 2>&1", shell=True)
    print(len(jobs), "stages")

if __name__ == "__main__":
    a = sys.argv[1:]; last = "--last" in a; a = [x for x in a if x != "--last"]
    render(a or None, last)
