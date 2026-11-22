"""Concept diagrams for the Catalyst SD-WAN on CML lesson.
Each diagram is drawn with draw.io's Cisco 19 stencils and exported in
build-up stages: stage k shows every element whose range includes k."""
import sys, subprocess, os
from dlib import D
INET = "#D35400"; MPLS = "#1F618D"; CTRL = "#C0392B"; V10 = "#1E8449"; V20 = "#7D3C98"; G = "#5b6b7b"
LB = "#eef6fb"; WB = "#ffffff"
DG = {}
def dg(name, title, sub, n):
    def w(f): DG[name] = (title, sub, n, f); return f
    return w
def tag(d, x, y, w, h, t, col, size=17, fill=None, bold=True):
    return d.box(x, y, w, h, t, fill=fill or WB, stroke=col, size=size, color=col if bold else "#1d2733", bold=bold, valign="middle")

# ---------------------------------------------------------------- 101
@dg("why1", "The problem: a traditional WAN", "Every router configured by hand, and most links sit idle", 3)
def _(d):
    d.st(0)
    eng = d.icon("user", 150, 400, "Network engineer", 1.5)
    d.text(60, 470, 190, 60, "one box at a time,<br>over the CLI", 17, color=G)
    rs = []
    for i, (y, n) in enumerate([(200, "Branch 1"), (400, "Branch 2"), (600, "Branch 3")]):
        r = d.icon("router", 560, y, n); rs.append(r)
        d.edge(eng, r, "ssh + paste" if i == 1 else "", color=G, dashed=True, arrow="block")
        d.box(615, y - 75, 230, 56, f"running-config v{[3,7,5][i]}<br><i>what's really on it?</i>", fill="#fdf2e9", stroke=INET, size=15, valign="middle", top=True)
    d.st(1)
    m = d.icon("cloud", 1080, 220, "MPLS (private)", 1.0, color=MPLS)
    n = d.icon("cloud", 1080, 420, "Broadband Internet (often idle)", 1.0, color=INET)
    l = d.icon("cloud", 1080, 620, "LTE (backup, idle)", 1.0, color=G)
    hq = d.icon("dc", 1440, 420, "Data centre")
    for r in rs:
        d.edge(r, m, color=MPLS, width=3); d.edge(r, n, color=INET, dashed=True); d.edge(r, l, color=G, dashed=True)
    d.edge(m, hq, color=MPLS, width=3); d.edge(n, hq, color=INET, dashed=True); d.edge(l, hq, color=G, dashed=True)
    d.st(2)
    d.box(700, 705, 870, 65, "Goal: use every link at once, and pick the best one per application, right now", fill="#eafaf1", stroke=V10, size=19, bold=True, color=V10, valign="middle")

# ---------------------------------------------------------------- 102
@dg("why2", "How SD-WAN answers it", "Four ideas we will see working in this lab", 5)
def _(d):
    d.st(1)
    d.box(520, 115, 560, 175, "Central control: one place for configuration and policy", fill=LB, stroke="#049FD9", size=18, bold=True)
    c = [d.icon("manager", 640, 215, "Manager", 0.9), d.icon("controller", 800, 215, "Controller", 0.9), d.icon("validator", 960, 215, "Validator", 0.9)]
    xs = [200, 600, 1000, 1400]; nm = ["DC", "Branch 1", "Branch 2", "Branch 3"]
    e = [d.icon("srouter", x, 560, n) for x, n in zip(xs, nm)]
    for r in e: d.edge(c[1], r, color=CTRL, dashed=True)
    d.line(240, 680, 560, 680, color=V10, width=5, arrow="block", start="block")
    d.text(160, 700, 480, 40, "user traffic flows directly between sites", 17, bold=True, color=V10)
    d.st(2)
    for a, b in zip(xs, xs[1:]):
        d.line(a + 40, 545, b - 40, 545, color=INET, width=3); d.line(a + 40, 580, b - 40, 580, color=MPLS, width=3)
        d.icon("lock", (a + b) / 2, 512, "", 0.45)
    d.text(900, 700, 660, 40, "IPsec over every transport, measured constantly", 18, bold=True, color=MPLS)
    d.st(3)
    for x in xs: d.icon("cert", x + 70, 470, "", 0.55)
    d.text(30, 330, 400, 60, "Every device proves its identity with a certificate", 17, bold=True, color=CTRL, align="left")
    d.st(4)
    d.box(1120, 115, 450, 175, "<b>Zero-touch provisioning</b><br>ship the router → plug it in → it finds the controllers, downloads its config and joins", fill="#eafaf1", stroke=V10, size=17, color="#1d2733", valign="middle")

# ---------------------------------------------------------------- 103
@dg("comp", "The four building blocks", "New names (and the old Viptela names you will still see everywhere)", 5)
def _(d):
    cols = [("manager", "SD-WAN Manager", "formerly vManage", "<b>Management plane</b><br><br>web GUI, REST API,<br>configuration, upgrades,<br>monitoring", "#049FD9"),
            ("controller", "SD-WAN Controller", "formerly vSmart", "<b>Control plane brain</b><br><br>learns routes from every edge,<br>applies policy, tells each<br>router what it may reach", CTRL),
            ("validator", "SD-WAN Validator", "formerly vBond", "<b>Orchestrator</b><br><br>first contact for a new router,<br>authenticates it, says where<br>Controllers and Manager are", "#B9770E"),
            ("srouter", "WAN Edge", "formerly cEdge (vs. vEdge)", "<b>Data plane</b><br><br>Catalyst 8000V, IOS XE in<br>SD-WAN (controller) mode,<br>carries user traffic", V10)]
    for i, (ic, n, old, txt, col) in enumerate(cols):
        d.st(i + 1)
        x = 40 + i * 390
        d.box(x, 120, 360, 600, "", fill=WB, stroke=col)
        d.icon(ic, x + 180, 260, "", 2.0)
        d.text(x, 360, 360, 40, n, 24, bold=True, color=col)
        d.text(x, 400, 360, 30, old, 18, color=G)
        d.text(x + 10, 450, 340, 200, txt, 19)

@dg("comp2", "In this lab vs. in production", "One of each controller here; redundancy in real networks", 4)
def _(d):
    d.st(0)
    d.box(40, 115, 740, 300, "<b>This lab</b>", fill=LB, stroke="#049FD9", size=20)
    for i, (ic, n) in enumerate([("manager", "1 × Manager"), ("controller", "1 × Controller"), ("validator", "1 × Validator")]):
        d.icon(ic, 170 + i * 240, 260, n, 1.3)
    d.st(1)
    d.box(820, 115, 740, 300, "<b>Production</b>", fill="#fdf2e9", stroke=INET, size=20)
    for i, (ic, n) in enumerate([("manager", "Manager cluster (3+)"), ("controller", "2+ Controllers"), ("validator", "2+ Validators")]):
        d.icon(ic, 930 + i * 250, 250, "", 1.1); d.icon(ic, 960 + i * 250, 275, "", 1.1)
        d.text(860 + i * 250, 330, 230, 30, n, 18, bold=True)
    d.st(2)
    d.box(40, 440, 1520, 220, "<b>5 WAN edges at 4 sites</b>", fill=WB, stroke=V10, size=20)
    for x, n, k in [(250, "DC (site 10)", 1), (650, "Branch 1 (site 20)", 2), (1050, "Branch 2 (site 30)", 1), (1400, "Branch 3 (site 40)", 1)]:
        d.icon("branch" if k == 1 and x > 300 else ("dc" if x == 250 else "branch"), x, 540, "", 0.8)
        for j in range(k): d.icon("srouter", x + 80 + j * 65, 540, "", 0.75)
        d.text(x - 120, 600, 300, 30, n + (" – 2 routers" if k == 2 else ""), 17, bold=True)
    d.st(3)
    d.box(40, 680, 1520, 80, "In code, files and the API: <b>vmanage</b> = Manager · <b>vsmart</b> = Controller · <b>vbond</b> = Validator", fill="#f4f6f7", stroke=G, size=20, valign="middle")

# ---------------------------------------------------------------- 105
@dg("planes", "Four planes, one job each", "", 5)
def _(d):
    rows = [("validator", "Orchestration plane", "Validator", "First contact: who are you? are you allowed in? here is where everything else is.", "#B9770E"),
            ("manager", "Management plane", "Manager", "Holds configuration groups and policies, pushes config to devices, collects statistics.", "#049FD9"),
            ("controller", "Control plane", "Controller", "Runs OMP with every edge: distributes routes, TLOCs and encryption keys; enforces control policy.", CTRL),
            ("srouter", "Data plane", "WAN edges", "Carry the actual user traffic, in IPsec tunnels, directly between sites.", V10)]
    for i, (ic, p, who, txt, col) in enumerate(rows):
        d.st(i + 1)
        y = 110 + i * 166
        d.box(40, y, 1520, 150, "", fill=WB, stroke=col)
        d.rect(40, y, 18, 150, f"fillColor={col};strokeColor=none;")
        d.icon(ic, 160, y + 62, who, 1.1)
        d.text(270, y + 18, 400, 40, p, 26, bold=True, color=col, align="left")
        d.text(270, y + 60, 1260, 80, txt, 21, align="left", valign="top")
    d.st(4)
    for x in (1180, 1330, 1480):
        d.icon("srouter", x, 700, "", 0.6)
    d.line(1205, 700, 1305, 700, color=V10, width=4); d.line(1355, 700, 1455, 700, color=V10, width=4)

@dg("conn", "How the pieces talk to each other", "Control connections are DTLS; data tunnels are IPsec; keys come from the Controller", 5)
def _(d):
    d.st(0)
    v = d.icon("validator", 300, 210, "Validator", 1.2); m = d.icon("manager", 800, 210, "Manager", 1.2); c = d.icon("controller", 1300, 210, "Controller", 1.2)
    a = d.icon("srouter", 500, 600, "Edge A", 1.2); b = d.icon("srouter", 1100, 600, "Edge B", 1.2)
    for e in (a, b):
        for t in (v, m, c): d.edge(e, t, "", color=CTRL, dashed=True, width=2)
    d.box(30, 400, 380, 110, "control connections:<br>DTLS (TLS over UDP) from port 12346, or TLS over TCP", fill="#fdedec", stroke=CTRL, size=17, bold=True, color=CTRL, valign="middle")
    d.st(1)
    for x, y in ((560, 600), (1160, 600), (360, 210), (860, 210), (1360, 210)):
        d.icon("cert", x, y - 40, "", 0.5)
    d.box(30, 530, 380, 60, "certificates checked in both directions", fill=WB, stroke=CTRL, size=16, bold=True, color=CTRL, valign="middle")
    d.st(2)
    d.edge(a, b, "", color=V10, width=7)
    d.icon("lock", 800, 600, "", 0.7)
    d.text(560, 640, 480, 50, "IPsec, encapsulated in UDP – crosses NAT", 18, bold=True, color=V10)
    d.st(3)
    d.box(650, 700, 300, 50, "no IKE between routers", fill="#f4f6f7", stroke=G, size=18, bold=True, color=G, valign="middle", top=True)
    d.st(4)
    d.edge(c, a, "keys", color="#B9770E", width=5, arrow="block", size=17)
    d.edge(c, b, "keys", color="#B9770E", width=5, arrow="block", size=17)
    d.box(1200, 400, 370, 110, "IPsec keys distributed by the Controller over the already-secure control connections", fill="#fef9e7", stroke="#B9770E", size=17, valign="middle")

# ---------------------------------------------------------------- 107
@dg("vpns", "VPNs: separate routing tables (VRFs) in one router", "", 5)
def _(d):
    d.st(0)
    d.box(180, 115, 1240, 655, "", fill="#fbfcfc", stroke=G, dashed=True)
    d.icon("srouter", 800, 160, "", 0.8)
    d.text(830, 135, 560, 50, "one WAN edge, isolated routing tables", 18, bold=True, color=G, align="left")
    d.st(1)
    d.box(210, 210, 580, 250, "<b>VPN 0 – transport</b><br>WAN interfaces and the underlay<br>Gi1 → INET (biz-internet)<br>Gi2 → MPLS (mpls)<br>every control connection and tunnel starts here", fill="#fdf2e9", stroke=INET, size=19)
    d.icon("cloud", 90, 300, "Internet", 0.75, color=INET); d.icon("cloud", 90, 420, "MPLS", 0.75, color=MPLS)
    d.st(2)
    d.box(810, 210, 580, 250, "<b>VPN 512 – out-of-band management</b><br>in this lab only the Manager uses it:<br>web GUI and API on 192.168.122.50", fill="#f4f6f7", stroke=G, size=19)
    d.st(3)
    d.box(210, 490, 580, 255, "<b>VPN 10 – service VPN (CORP)</b><br>where the users live<br>Gi3 → corporate LAN", fill="#eafaf1", stroke=V10, size=19)
    d.box(810, 490, 580, 255, "<b>VPN 20 – service VPN (GUEST)</b><br>Gi4 → guest LAN<br>any number except 0 and 512", fill="#f5eef8", stroke=V20, size=19)
    d.icon("pc", 1500, 560, "employees", 0.9); d.icon("laptop", 1500, 680, "guests", 0.9)
    d.st(4)
    d.box(250, 640, 500, 90, "IOS XE config:<br><font face='monospace'>vrf definition 10</font>", fill="#1d2733", stroke="#1d2733", size=18, color="#ffffff", valign="middle")

@dg("vpns2", "Two service VPNs, two different topologies", "", 4)
def _(d):
    def sites(x0):
        p = {"DC": (x0 + 180, 250), "BR3": (x0 + 540, 250), "BR1": (x0 + 180, 560), "BR2": (x0 + 540, 560)}
        return {k: d.icon("srouter", x, y, k, 0.9) for k, (x, y) in p.items()}
    d.st(1)
    d.box(30, 110, 750, 660, "<b>VPN 10 – CORP</b>: full mesh, critical traffic steered by AAR", fill=WB, stroke=V10, size=19, color=V10)
    s = sites(50)
    for a, b in [("DC", "BR1"), ("DC", "BR2"), ("DC", "BR3"), ("BR1", "BR2"), ("BR2", "BR3"), ("BR1", "BR3")]:
        d.edge(s[a], s[b], color=V10, width=3)
    d.text(60, 700, 690, 40, "every site reaches every other site directly", 18, bold=True, color=V10)
    d.st(2)
    d.box(820, 110, 750, 660, "<b>VPN 20 – GUEST</b>: branches only reach the DC guest segment", fill=WB, stroke=V20, size=19, color=V20)
    t = sites(840)
    for b in ("BR1", "BR2", "BR3"): d.edge(t["DC"], t[b], color=V20, width=3)
    for a, b in [("BR1", "BR2"), ("BR2", "BR3"), ("BR1", "BR3")]:
        d.edge(t[a], t[b], "✕", color=CTRL, dashed=True, size=24)
    d.text(840, 150, 710, 40, "no guest-to-guest, no access to VPN 10", 18, bold=True, color=CTRL)
    d.st(3)
    for b, (x, y) in (("BR1", (1020, 690)), ("BR2", (1380, 690)), ("BR3", (1500, 380))):
        cl = d.icon("cloud", x, y, "", 0.55, color=INET)
        d.edge(t[b], cl, "", color=INET, arrow="block", width=3)
    d.text(1100, 670, 200, 60, "DIA: local Internet breakout", 17, bold=True, color=INET)

# ---------------------------------------------------------------- 109
@dg("tloc", "TLOC – the transport locator", "One end of a tunnel", 4)
def _(d):
    d.st(1)
    for i, (h, v, col) in enumerate([("System IP", "10.255.0.10<br><small>identifier, not an interface address</small>", "#049FD9"), ("Colour", "mpls", MPLS), ("Encapsulation", "IPsec", G)]):
        x = 60 + i * 330
        d.box(x, 130, 280, 130, f"<b>{h}</b><br>{v}", fill=WB, stroke=col, size=19, valign="middle")
        if i < 2: d.text(x + 280, 170, 50, 50, "+", 40, bold=True)
    d.text(1050, 170, 50, 50, "=", 40, bold=True)
    d.box(1110, 130, 440, 130, "<b>TLOC</b><br>(10.255.0.10, mpls, ipsec)", fill="#eaf2f8", stroke=MPLS, size=22, valign="middle", color=MPLS)
    d.st(2)
    r = d.icon("srouter", 200, 520, "DC-E1<br>system IP 10.255.0.10", 1.4)
    i1 = d.icon("cloud", 880, 380, "INET", 1.0, color=INET); m1 = d.icon("cloud", 880, 660, "MPLS", 1.0, color=MPLS)
    d.edge(r, i1, "Gi1 → TLOC (10.255.0.10, biz-internet, ipsec)", color=INET, width=4, size=17)
    d.edge(r, m1, "Gi2 → TLOC (10.255.0.10, mpls, ipsec)", color=MPLS, width=4, size=17)
    d.st(3)
    d.box(1050, 360, 500, 130, "<b>Public colours</b> – may sit behind NAT<br>biz-internet, public-internet, lte, 3g, …", fill="#fdf2e9", stroke=INET, size=18)
    d.box(1050, 540, 500, 130, "<b>Private colours</b> – reachable on their native address<br>mpls, private1 … private6, metro-ethernet, …", fill="#eaf2f8", stroke=MPLS, size=18)

@dg("restrict", "Which tunnels get built? The restrict option", "", 4)
def _(d):
    d.st(0)
    a = d.icon("srouter", 180, 440, "BR1-E1", 1.3); b = d.icon("srouter", 1420, 440, "DC-E1", 1.3)
    ai = tag(d, 330, 260, 230, 56, "biz-internet", INET); am = tag(d, 330, 560, 230, 56, "mpls", MPLS)
    bi = tag(d, 1040, 260, 230, 56, "biz-internet", INET); bm = tag(d, 1040, 560, 230, 56, "mpls", MPLS)
    for x, y in ((ai, a), (am, a), (bi, b), (bm, b)): d.edge(x, y, color=G)
    d.edge(ai, bi, "Internet ⟷ Internet", color=INET, width=4, size=17); d.edge(am, bm, "MPLS ⟷ MPLS", color=MPLS, width=4, size=17)
    d.st(0, 2)
    d.edge(ai, bm, "", color=G, width=2, dashed=True); d.edge(am, bi, "", color=G, width=2, dashed=True)
    d.text(600, 400, 400, 40, "default: 4 tunnels per pair", 19, bold=True, color=G)
    d.st(1, 2)
    d.text(760, 440, 80, 60, "✕", 52, bold=True, color=CTRL)
    d.text(560, 500, 480, 40, "INET and MPLS providers can't reach each other", 17, bold=True, color=CTRL)
    d.st(2)
    d.box(560, 120, 480, 80, "<font face='monospace'>color mpls restrict</font><br>only build tunnels to the same colour", fill="#fdedec", stroke=CTRL, size=17, valign="middle")
    d.st(3)
    d.box(560, 660, 480, 90, "<b>Result: 2 tunnels per pair of routers</b><br>one over the Internet, one over MPLS", fill="#eafaf1", stroke=V10, size=18, valign="middle")

# ---------------------------------------------------------------- 111
@dg("omp", "OMP – the Overlay Management Protocol", "Like BGP, runs inside the DTLS connection to the Controller", 5)
def _(d):
    d.st(0)
    c = d.icon("controller", 800, 230, "Controller<br>(route reflector)", 1.4)
    names = ["DC-E1", "BR1-E1", "BR1-E2", "BR2-E1", "BR3-E1"]
    e = [d.icon("srouter", 340 + i * 230, 640, n) for i, n in enumerate(names)]
    for r in e: d.edge(r, c, "", color=CTRL, dashed=True, width=2)
    d.text(560, 430, 160, 30, "OMP sessions", 17, bold=True, color=CTRL)
    d.st(1)
    d.line(380, 700, 530, 700, color=CTRL, width=2, dashed=True); d.text(420, 700, 80, 50, "✕", 34, bold=True, color=CTRL)
    d.text(240, 735, 460, 30, "edges never run OMP with each other", 16, bold=True, color=CTRL)
    d.st(2)
    d.box(30, 115, 450, 120, "<b>OMP routes</b> – LAN prefixes<br>e.g. 10.20.10.0/24, VPN 10, branch 1", fill="#eafaf1", stroke=V10, size=17)
    d.st(3)
    d.box(30, 250, 450, 120, "<b>TLOC routes</b> – tunnel endpoints<br>address, colour, encryption keys", fill="#eaf2f8", stroke=MPLS, size=17)
    d.box(30, 385, 450, 90, "<b>Service routes</b> – e.g. firewalls<br>(not used here)", fill="#f4f6f7", stroke=G, size=17)
    d.st(4)
    d.box(1100, 115, 470, 230, "<b>An OMP route points at TLOCs</b><br><font face='monospace'>10.20.10.0/24 vpn 10<br>&nbsp;via 10.255.0.21 mpls<br>&nbsp;via 10.255.0.21 biz-internet</font><br>→ which tunnel reaches the prefix", fill=WB, stroke="#049FD9", size=17)

@dg("ctrlpol", "Control policy on the Controller", "Filter or modify what the Controller reflects", 4)
def _(d):
    d.st(0)
    c = d.icon("controller", 800, 210, "Controller", 1.4)
    d.box(910, 160, 300, 90, "control policy<br>filter / modify routes", fill="#fdedec", stroke=CTRL, size=17, bold=True, color=CTRL, valign="middle")
    d.st(1)
    d.box(30, 330, 740, 440, "<b>No control policy</b> → everything reflected → <b>full mesh</b>", fill=WB, stroke=V10, size=18, color=V10)
    pos = [(150, 470), (400, 420), (650, 470), (400, 680)]
    s = [d.icon("srouter", x, y, n, 0.8) for (x, y), n in zip(pos, ["DC", "BR1", "BR2", "BR3"])]
    for i in range(4):
        for j in range(i + 1, 4): d.edge(s[i], s[j], color=V10, width=2)
    d.text(470, 730, 290, 30, "what we want for VPN 10", 16, bold=True, color=V10)
    d.st(2)
    d.box(830, 330, 740, 440, "<b>VPN 20</b>: hide branch guest networks from other branches", fill=WB, stroke=V20, size=18, color=V20)
    b2 = d.icon("srouter", 1450, 680, "BR2", 0.8); b1 = d.icon("srouter", 950, 680, "BR1", 0.8)
    cc = d.icon("controller", 1200, 470, "Controller", 0.9)
    d.edge(b2, cc, "10.30.20.0/24", color=V20, arrow="block", width=3)
    d.edge(cc, b1, "✕ not advertised", color=CTRL, arrow="block", dashed=True, width=3)
    d.st(3)
    d.box(300, 125, 450, 125, "By default every edge advertises its connected and static LAN routes into OMP", fill="#f4f6f7", stroke=G, size=17, valign="middle")

# ---------------------------------------------------------------- 113
@dg("bfd", "BFD: liveness and quality on every tunnel", "", 5)
def _(d):
    d.st(0)
    a = d.icon("srouter", 180, 260, "BR1-E1", 1.3); b = d.icon("srouter", 1420, 260, "DC-E1", 1.3)
    d.edge(a, b, "", color=MPLS, width=10)
    for x in range(330, 1300, 160):
        d.rect(x, 246, 46, 28, "rounded=1;fillColor=#F4D03F;strokeColor=#7D6608;fontSize=12;fontStyle=1;", "hello", layer=2)
    d.text(560, 180, 480, 40, "BFD hello down every tunnel, every 1 s", 19, bold=True, color=MPLS)
    d.st(1)
    d.box(500, 320, 600, 70, "several hellos lost in a row → tunnel down → traffic moves in seconds", fill="#fdedec", stroke=CTRL, size=17, valign="middle", top=True)
    d.st(2)
    for i, (n, u) in enumerate([("Loss", "%"), ("Latency", "ms"), ("Jitter", "ms")]):
        d.box(240 + i * 400, 420, 320, 90, f"<b>{n}</b> ({u})<br>measured continuously", fill=LB, stroke="#049FD9", size=18, valign="middle")
    d.st(3)
    for i in range(6):
        d.box(180 + i * 210, 560, 200, 70, f"bucket {i+1}", fill="#fef9e7", stroke="#B9770E", size=17, valign="middle")
    d.text(180, 630, 200, 30, "← poll interval →", 16, bold=True, color="#B9770E")
    d.text(600, 630, 600, 30, "default poll interval: 10 minutes (too slow for a demo)", 16, color=G)
    d.st(4)
    d.box(380, 680, 840, 80, "<b>This lab:</b> poll interval 30 s × multiplier 2 → quality changes noticed in ≈ 1 minute", fill="#eafaf1", stroke=V10, size=19, valign="middle")

@dg("aar", "Application-aware routing (AAR)", "BFD measurements + SLA class → path choice for every packet", 5)
def _(d):
    d.st(0)
    d.box(30, 130, 360, 260, "", fill=WB, stroke="#B9770E")
    d.icon("server", 210, 200, "", 0.9)
    d.text(30, 250, 360, 40, "BFD measurements", 20, bold=True, color="#B9770E")
    d.text(30, 290, 360, 80, "loss · latency · jitter<br>per tunnel", 18)
    d.st(1)
    d.box(30, 420, 360, 220, "<b>SLA class CRITICAL-SLA</b><br><br>latency ≤ 150 ms<br>loss ≤ 2 %<br>jitter ≤ 50 ms", fill="#fdf2e9", stroke=INET, size=20)
    d.st(2)
    p = d.box(470, 140, 330, 90, "ICMP to CORP-NETS<br>(CORP-AAR, VPN 10)", fill="#eafaf1", stroke=V10, size=18, bold=True, valign="middle")
    q1 = d.rect(470, 280, 330, 160, "rhombus;fillColor=#eef6fb;strokeColor=#049FD9;strokeWidth=2;fontSize=17;fontStyle=1;", "which tunnels<br>meet CRITICAL-SLA?")
    d.edge(p, q1, color=G, arrow="block")
    d.st(3)
    q2 = d.rect(950, 280, 300, 160, "rhombus;fillColor=#eef6fb;strokeColor=#049FD9;strokeWidth=2;fontSize=17;fontStyle=1;", "is an mpls<br>tunnel among them?")
    d.edge(q1, q2, "some", color=G, arrow="block")
    u1 = tag(d, 1330, 320, 240, 80, "use mpls<br>(preferred colour)", MPLS)
    d.edge(q2, u1, "yes", color=G, arrow="block")
    d.st(4)
    u2 = tag(d, 950, 520, 300, 80, "use biz-internet<br>(still meets SLA)", INET)
    d.edge(q2, u2, "no", color=G, arrow="block")
    u3 = tag(d, 470, 560, 330, 90, "fallback to best path<br>(best of the rest, never drop)", CTRL)
    d.edge(q1, u3, "none", color=G, arrow="block")

# ---------------------------------------------------------------- 115
@dg("onboard", "Zero-touch: how a new router joins", "", 9)
def _(d):
    xs = {"e": 150, "v": 520, "m": 860, "c": 1170, "o": 1460}
    d.st(0)
    for k, ic, n in [("e", "srouter", "New edge"), ("v", "validator", "Validator"), ("m", "manager", "Manager"), ("c", "controller", "Controller"), ("o", "srouter", "Other edges")]:
        d.icon(ic, xs[k], 140, n, 0.9)
        d.line(xs[k], 210, xs[k], 775, color="#aab7b8", dashed=True)
    def step(n, y, a, b, t, col, side=False):
        d.st(n)
        d.rect(30, y - 20, 40, 40, f"ellipse;fillColor={col};strokeColor=none;fontColor=#ffffff;fontSize=20;fontStyle=1;", str(n))
        if side:
            d.line(xs[a], y, xs[b], y, color=col, width=3, arrow="block")
            d.text(max(xs[a], xs[b]) + 20, y - 20, 900, 40, t, 17, bold=True, color=col, align="left")
        else:
            d.line(xs[a], y, xs[b], y, color=col, width=3, arrow="block", label=t, size=17, style="verticalAlign=bottom;labelBackgroundColor=none;")
    d.st(1)
    d.rect(30, 220, 40, 40, "ellipse;fillColor=#5b6b7b;strokeColor=none;fontColor=#ffffff;fontSize=20;fontStyle=1;", "1")
    d.box(180, 215, 300, 100, "bootstrap file: chassis + OTP, Validator name, org name, root CA", fill="#f4f6f7", stroke=G, size=15, valign="middle")
    step(2, 345, "e", "v", "VPN 0 up · resolve validator.sdwan.local · open DTLS", CTRL, side=True)
    d.st(3)
    d.rect(30, 400, 40, 40, "ellipse;fillColor=#B9770E;strokeColor=none;fontColor=#ffffff;fontSize=20;fontStyle=1;", "3")
    d.box(560, 390, 300, 70, "check org name, chassis on allowed list, certificates", fill="#fef9e7", stroke="#B9770E", size=15, valign="middle")
    step(4, 490, "v", "e", "here are the Manager and Controllers · your public IP is … (NAT discovery)", "#B9770E", side=True)
    step(5, 560, "e", "m", "full configuration from the configuration group", "#049FD9")
    step(6, 630, "e", "c", "OMP up: send own TLOCs + routes, receive everyone else's", CTRL)
    step(7, 700, "e", "o", "IPsec tunnels + BFD to every allowed router", V10)
    d.st(8)
    d.box(1080, 730, 490, 50, "= zero-touch provisioning (≈ 10 min in the lab)", fill="#eafaf1", stroke=V10, size=18, bold=True, color=V10, valign="middle")

@dg("trust", "Trust and identity in this lab", "", 7)
def _(d):
    d.st(1)
    ca = d.icon("cert", 230, 200, "Lab root CA (pki.py)", 1.4)
    d.st(2)
    cs = [d.icon(ic, 100 + i * 130, 460, n, 0.9) for i, (ic, n) in enumerate([("manager", "Manager"), ("controller", "Controller"), ("validator", "Validator")])]
    for c in cs: d.edge(ca, c, "", color="#B9770E", arrow="block", width=2)
    d.text(30, 290, 120, 40, "signs", 17, bold=True, color="#B9770E")
    d.text(30, 560, 420, 40, "everyone trusts this root", 17, bold=True)
    d.st(3)
    d.box(30, 620, 420, 70, "Manager setting: Enterprise Root Certificate", fill="#fef9e7", stroke="#B9770E", size=17, valign="middle")
    d.st(4)
    m = d.icon("manager", 780, 200, "Manager acts as CA for the edges", 1.4)
    es = [d.icon("srouter", 640 + i * 140, 460, f"edge {i+1}", 0.8) for i in range(3)]
    for e in es: d.edge(m, e, "", color="#049FD9", arrow="block", width=2)
    d.text(560, 560, 440, 60, "signs each router's certificate after its first successful contact", 17, bold=True, color="#049FD9")
    d.st(5)
    d.box(1080, 120, 490, 280, "<b>Before first contact</b><br><br>• WAN edge list: signed serial file with the chassis numbers allowed to join (on the Validator)<br>• one-time password in the bootstrap must match what the Manager expects", fill=WB, stroke=CTRL, size=17)
    d.icon("validator", 1320, 470, "Validator holds the list", 0.9)
    d.st(6)
    d.box(560, 680, 1010, 80, "Organization name must be identical everywhere: certificates · Manager settings · serial file", fill="#fdedec", stroke=CTRL, size=19, bold=True, color=CTRL, valign="middle")

# ---------------------------------------------------------------- 118
@dg("cg", "Configuration groups (release 20.18)", "", 9)
def _(d):
    d.st(1)
    d.box(1180, 110, 390, 90, "older releases: device templates + feature templates", fill="#f4f6f7", stroke=G, size=16, color=G, valign="middle")
    d.st(2)
    root = d.box(560, 120, 480, 80, "<b>Configuration group BRANCH-CG</b>", fill="#eaf2f8", stroke="#049FD9", size=21, valign="middle")
    pr = [("System profile<br>LAB-SYSTEM", "basic · AAA users<br>BFD timers · OMP<br>global · logging", "#049FD9"),
          ("Transport profile<br>LAB-TRANSPORT", "VPN 0<br>Gi1 → INET, Gi2 → MPLS<br>tunnels and colours", INET),
          ("Service profile<br>LAB-SERVICE", "LAB-VPN10-CORP (Gi3, VRRP)<br>LAB-VPN20-GUEST (Gi4, VRRP)", V10),
          ("CLI profile<br>LAB-CLI", "the odd command not modelled elsewhere", G)]
    for i, (n, parc, col) in enumerate(pr):
        d.st(3 + i)
        x = 40 + i * 390
        p = d.box(x, 270, 360, 90, f"<b>{n}</b>", fill=WB, stroke=col, size=18, valign="middle")
        d.edge(root, p, color=G)
        d.st(7)
        d.box(x, 400, 360, 150, "parcels:<br>" + parc, fill="#fbfcfc", stroke=col, size=16, dashed=True)
    d.st(7)
    d.text(40, 555, 900, 30, "each feature inside a profile = a parcel (API name)", 16, bold=True, color=G, align="left")
    d.st(8)
    for i, (n, t, col) in enumerate([("Global", "same value on every device", "#049FD9"), ("Variable", "filled in per device", V10), ("Default", "Cisco default value", G)]):
        d.box(140 + i * 450, 600, 420, 110, f"<b>{n}</b><br>{t}", fill=WB, stroke=col, size=19, valign="middle")
    d.text(40, 715, 1500, 40, "every value in a parcel is one of these three", 17, color=G)

@dg("cg2", "One design, five routers – and where policy goes", "", 3)
def _(d):
    d.st(0)
    g = d.box(40, 120, 420, 80, "<b>BRANCH-CG</b> + per-device variables", fill="#eaf2f8", stroke="#049FD9", size=19, valign="middle")
    rows = [("DC-E1", "10.255.0.10", "10"), ("BR1-E1", "10.255.0.21", "20"), ("BR1-E2", "10.255.0.22", "20"), ("BR2-E1", "10.255.0.30", "30"), ("BR3-E1", "10.255.0.40", "40")]
    for i, (h, ip, site) in enumerate(rows):
        y = 240 + i * 105
        r = d.icon("srouter", 90, y + 40, "", 0.8)
        d.box(150, y, 330, 85, f"host <b>{h}</b> · system IP {ip}<br>site {site} · Gi addresses · VRRP prio", fill=WB, stroke=G, size=15, valign="middle")
    d.st(1, 2)
    d.box(560, 120, 1010, 640, "", fill="#fbfcfc", stroke=G, dashed=True)
    d.st(2)
    pg = d.box(600, 160, 440, 120, "<b>Policy group</b><br>bundles policy profiles", fill="#eafaf1", stroke=V10, size=19, valign="middle")
    tg = d.box(1100, 160, 440, 120, "<b>Topology group</b><br>bundles topology profiles", fill="#fdedec", stroke=CTRL, size=19, valign="middle")
    es = [d.icon("srouter", 640 + i * 90, 470, "", 0.7) for i in range(5)]
    for e in es: d.edge(pg, e, color=V10, arrow="block")
    d.text(600, 530, 440, 60, "attached to the edges", 18, bold=True, color=V10)
    c = d.icon("controller", 1320, 470, "", 1.2)
    d.edge(tg, c, color=CTRL, arrow="block", width=3)
    d.text(1100, 540, 440, 120, "attached to the Controller – who builds tunnels to whom, who learns which routes", 18, bold=True, color=CTRL)

@dg("pg", "The policy we will end up with", "", 6)
def _(d):
    d.st(1)
    d.box(40, 120, 900, 470, "<b>Policy group LAB-PG</b>", fill="#fbfcfc", stroke=V10, size=21, color=V10)
    d.box(70, 180, 840, 380, "Application priority profile LAB-APP-PRIORITY", fill="#eafaf1", stroke=V10, size=18)
    d.st(2)
    d.box(100, 240, 380, 290, "<b>CORP-AAR</b> → VPN 10<br><br>ICMP to CORP-NETS<br>SLA class CRITICAL-SLA<br>prefer mpls<br>fallback to best path", fill=WB, stroke=MPLS, size=18)
    d.st(3)
    d.box(500, 240, 380, 290, "<b>GUEST-DIA</b> → VPN 20<br><br>RFC1918 → overlay<br>everything else →<br>nat use VPN 0<br>(local Internet link)", fill=WB, stroke=INET, size=18)
    d.st(4)
    d.box(1000, 120, 570, 470, "<b>Topology group LAB-TOPOLOGY-GROUP</b>", fill="#fbfcfc", stroke=CTRL, size=20, color=CTRL)
    d.box(1030, 190, 510, 220, "<b>GUEST-ISOLATION</b> (custom control)<br><br>branches learn guest routes only from the DC, never from each other", fill=WB, stroke=CTRL, size=18)
    d.icon("controller", 1285, 490, "", 1.0)
    d.st(5)
    for i in range(5): d.icon("srouter", 200 + i * 130, 680, "", 0.8)
    d.text(40, 730, 900, 40, "data policy runs on the edges", 22, bold=True, color=V10)
    d.text(1000, 640, 570, 40, "control policy runs on the Controller", 22, bold=True, color=CTRL)

@dg("goals", "What step nine has to achieve", "Without policy: full mesh in every VPN, all tunnels used equally", 4)
def _(d):
    rows = [("1", "VPN 10: critical traffic prefers MPLS while it meets the SLA, else moves to the Internet", MPLS, "data policy → policy group LAB-PG"),
            ("2", "VPN 20: guests go straight to the Internet from their own branch – no backhaul to the DC", INET, "data policy → policy group LAB-PG"),
            ("3", "VPN 20: guests at one branch never reach guests at another branch", CTRL, "control policy → topology group")]
    for i, (n, t, col, where) in enumerate(rows):
        d.st(i + 1)
        y = 140 + i * 210
        d.rect(40, y + 40, 80, 80, f"ellipse;fillColor={col};strokeColor=none;fontColor=#ffffff;fontSize=34;fontStyle=1;", n)
        d.box(150, y, 900, 160, t, fill=WB, stroke=col, size=21, valign="middle")
        d.box(1100, y + 30, 460, 100, where, fill="#f4f6f7", stroke=col, size=19, bold=True, color=col, valign="middle")

# ---------------------------------------------------------------- 206
@dg("underlay", "The underlay: one Gateway router, three VRFs", "IOL router plays DC network, Internet provider and MPLS provider", 9)
def _(d):
    d.st(0)
    gw = d.icon("router", 800, 420, "Gateway", 1.6)
    d.st(1)
    for i, (ic, n) in enumerate([("manager", "Manager .1"), ("controller", "Controller .101"), ("validator", "Validator .201")]):
        cc = d.icon(ic, 200 + i * 140, 175, n, 0.8)
    sw0 = d.icon("switch", 340, 330, "", 0.9)
    d.text(130, 360, 420, 30, "VPN0 segment 172.16.0.0/24", 17, bold=True, color="#049FD9")
    for i in range(3): d.line(200 + i * 140, 210, 340, 300, color=G)
    d.edge(sw0, gw, "e0/0 · vrf vpn0 · .254", color="#049FD9", width=3, size=16)
    d.st(2)
    swi = d.icon("switch", 420, 640, "", 0.9)
    d.text(220, 680, 420, 50, "INET 172.16.1.0/24<br>colour biz-internet → 5 edges Gi1", 16, bold=True, color=INET)
    d.edge(gw, swi, "e0/1 · vrf inet", color=INET, width=3, size=16)
    d.st(3)
    swm = d.icon("switch", 1180, 640, "", 0.9)
    d.text(980, 680, 420, 50, "MPLS 172.16.2.0/24<br>colour mpls → 5 edges Gi2", 16, bold=True, color=MPLS)
    d.edge(gw, swm, "e0/2 · vrf mpls", color=MPLS, width=3, size=16)
    d.st(4)
    cl = d.icon("cloud", 1220, 200, "", 0.9, color=G)
    d.text(1290, 150, 290, 60, "Internet<br>(CML NAT connector)", 17, bold=True, color=G, align="left")
    d.edge(gw, cl, "e0/3 · uplink · DHCP", color=G, width=3, size=16)
    d.st(5)
    d.box(1300, 330, 280, 250, "<b>BGP route-target leaking</b><br><br>vpn0 ⟷ inet ✓<br>vpn0 ⟷ mpls ✓<br><font color='#C0392B'><b>inet ⟷ mpls ✕</b></font><br><br>→ restrict on colours", fill=WB, stroke=G, size=17, top=True)
    d.st(6)
    d.box(30, 440, 420, 120, "<b>DNS on the Gateway</b><br>validator.sdwan.local → 172.16.0.201<br>(host entry in every VRF)", fill="#fef9e7", stroke="#B9770E", size=16, valign="middle")
    d.st(7)
    d.box(600, 150, 330, 60, "NAT for vpn0 and inet", fill="#f4f6f7", stroke=G, size=16, bold=True, valign="middle", top=True)
    d.st(8)
    d.box(1300, 600, 280, 90, "mpls VRF has <b>no</b> Internet → DIA must use INET", fill="#fdedec", stroke=CTRL, size=15, valign="middle")

@dg("steps", "build.py – nine steps", "Read the code, then watch the real run", 10)
def _(d):
    st = [("cert", "1 · Certificate authority", "pki.py creates our root CA"),
          ("server", "2 · Topology in CML", "render + start the controllers"),
          ("manager", "3 · Manager settings", "org, Validator, CA modes"),
          ("validator", "4 · Onboard controllers", "add Validator + Controller,<br>sign their CSRs"),
          ("cert", "5 · WAN edge list", "upload the signed serial file"),
          ("db", "6 · Configuration group", "BRANCH-CG and its profiles"),
          ("srouter", "7 · Each router", "chassis, variables, deploy, bootstrap, create in CML"),
          ("router", "8 · Wait for join", "control, OMP, BFD up"),
          ("controller", "9 · Centralized policy", "LAB-PG + topology group")]
    prev = None
    for i, (ic, t, s) in enumerate(st):
        d.st(i + 1)
        if i < 5: x, y = 40 + i * 310, 150
        else: x, y = 195 + (i - 5) * 310, 470
        b = d.box(x, y, 280, 250, "", fill=WB, stroke="#049FD9")
        d.icon(ic, x + 140, y + 70, "", 1.0)
        d.text(x, y + 120, 280, 40, t, 19, bold=True, color="#005073")
        d.text(x + 10, y + 160, 260, 80, s, 16)
        if prev: d.edge(prev, b, color="#049FD9", arrow="block", width=2, pts=[(1420, 435), (335, 435)] if i == 5 else None)
        prev = b

# ---------------------------------------------------------------- 605
@dg("dia", "GUEST-DIA – direct Internet access for guests", "Data policy on the edge, VPN 20, sequences in order", 4)
def _(d):
    d.st(0)
    g = d.icon("laptop", 170, 430, "BR1-GUEST<br>10.20.20.x", 1.4)
    r = d.icon("srouter", 560, 430, "BR1-E1<br>VRF 20", 1.4)
    d.edge(g, r, "Gi4", color=V20, width=3, arrow="block")
    d.st(1)
    dc = d.icon("srouter", 1300, 210, "DC-E1 → DC guest segment", 1.1)
    d.edge(r, dc, "seq 10: RFC1918 destination → no action → overlay", color=V20, width=4, arrow="block", size=17)
    d.st(2)
    cl = d.icon("cloud", 1300, 630, "Internet", 1.1, color=INET)
    d.edge(r, cl, "seq 20: everything else → nat use VPN 0", color=INET, width=4, arrow="block", size=17)
    d.box(700, 690, 400, 70, "out of the local Gi1 (INET), source NAT to Gi1's address", fill="#fdf2e9", stroke=INET, size=16, valign="middle")
    d.st(3)
    d.box(30, 600, 560, 110, "without seq 10, guest traffic to the DC guest segment would also be sent to the Internet – and fail", fill="#fdedec", stroke=CTRL, size=17, valign="middle")

@dg("iso", "GUEST-ISOLATION – the control policy", "Applied outbound on the Controller, towards the branch sites", 5)
def _(d):
    d.st(0)
    c = d.icon("controller", 800, 200, "Controller", 1.4)
    pos = [("DC (site 10)", 220), ("BR1 (site 20)", 620), ("BR2 (site 30)", 1000), ("BR3 (site 40)", 1380)]
    s = [d.icon("srouter", x, 640, n, 1.0) for n, x in pos]
    d.st(1)
    d.box(1010, 110, 560, 190, "<b>outbound → branch sites</b><br>seq 10: VPN 20, origin site 10 → accept<br>seq 20: VPN 20 → reject<br>default action: accept", fill="#fdedec", stroke=CTRL, size=17)
    d.st(2)
    d.edge(s[0], c, "DC guest 10.10.20.0/24", color=V20, arrow="block", width=3, size=16)
    d.edge(c, s[1], "accept", color=V10, arrow="block", width=3, size=16)
    d.edge(c, s[3], "accept", color=V10, arrow="block", width=3, size=16)
    d.st(3)
    d.edge(s[2], c, "BR2 guest 10.30.20.0/24", color=V20, arrow="block", width=3, dashed=True, size=16)
    d.box(200, 200, 400, 90, "BR2's guest route hits seq 20 → <b>reject</b><br>never sent to BR1 or BR3", fill="#fdedec", stroke=CTRL, size=17, valign="middle", top=True)
    d.st(4)
    d.box(300, 720, 1000, 60, "VPN 10 routes and all TLOC routes untouched → VPN 10 full mesh, branch tunnels still built", fill="#eafaf1", stroke=V10, size=18, bold=True, color=V10, valign="middle")

@dg("hs", "Lesson: built-in hub-and-spoke vs. custom control", "", 4)
def _(d):
    def panel(x0, title, col):
        d.box(x0, 110, 760, 660, title, fill=WB, stroke=col, size=19, color=col)
        h = d.icon("srouter", x0 + 380, 230, "DC (hub)", 1.0)
        sp = [d.icon("srouter", x0 + 130 + i * 250, 560, f"BR{i+1}", 1.0) for i in range(3)]
        return h, sp
    d.st(0)
    h, sp = panel(30, "<b>Built-in hub and spoke (VPN 20)</b>", CTRL)
    for x in sp: d.edge(h, x, color=G, width=2)
    d.st(1)
    d.box(70, 330, 680, 90, "Controller rejects everything at the spokes not from the hub – <b>including TLOC routes</b>", fill="#fdedec", stroke=CTRL, size=17, valign="middle", top=True)
    d.st(2)
    for a, b in ((0, 1), (1, 2)): d.edge(sp[a], sp[b], "✕", color=CTRL, dashed=True, width=3, size=22)
    d.text(70, 690, 680, 50, "branch-to-branch tunnels gone – VPN 10 lost its full mesh too", 18, bold=True, color=CTRL)
    d.st(3)
    h2, sp2 = panel(810, "<b>Custom control policy, default accept</b>", V10)
    for x in sp2: d.edge(h2, x, color=V10, width=3)
    for a, b in ((0, 1), (1, 2)): d.edge(sp2[a], sp2[b], color=V10, width=3)
    d.text(850, 690, 680, 50, "only VPN 20 branch routes rejected; TLOCs and VPN 10 untouched", 18, bold=True, color=V10)

# ---------------------------------------------------------------- 722
@dg("walk", "Packet walk: BR1-PC pings DC-SRV", "", 11)
def _(d):
    d.st(0)
    pc = d.icon("pc", 110, 470, "BR1-PC<br>10.20.10.100", 1.2)
    e1 = d.icon("srouter", 420, 470, "BR1-E1<br>VRRP master", 1.3)
    gw = d.icon("router", 800, 470, "Gateway<br>vrf mpls", 1.1)
    dc = d.icon("srouter", 1180, 470, "DC-E1", 1.3)
    sv = d.icon("server", 1480, 470, "DC-SRV<br>10.10.10.100", 1.2)
    d.st(1)
    d.edge(pc, e1, "gw 10.20.10.1 (VRRP VIP)", color=V10, width=4, arrow="block", size=15)
    d.st(2)
    d.text(300, 560, 250, 30, "in on Gi3 · VRF 10", 16, bold=True, color=V10)
    d.st(3)
    d.box(180, 110, 520, 130, "<b>lookup 10.10.10.0/24</b> → OMP route<br>TLOCs on DC-E1: mpls · biz-internet", fill=LB, stroke="#049FD9", size=17, valign="middle")
    d.st(4)
    d.box(180, 250, 520, 110, "<b>CORP-AAR seq 10</b>: ICMP to CORP-NETS<br>meets CRITICAL-SLA, prefer mpls → <b>mpls</b>", fill="#eaf2f8", stroke=MPLS, size=17, valign="middle")
    d.st(5)
    d.edge(e1, gw, "Gi2 · IPsec", color=MPLS, width=5, arrow="block", size=15)
    d.box(250, 640, 700, 120, "<b>outer</b> 172.16.2.21 → 172.16.2.10 · UDP/IPsec (ESP)<br>" "<b>inner</b> 10.20.10.100 → 10.10.10.100 · ICMP · VPN 10 label", fill="#1d2733", stroke="#1d2733", size=16, color="#ffffff", valign="middle", top=True)
    d.icon("lock", 610, 430, "", 0.5)
    d.st(6)
    d.edge(gw, dc, "", color=MPLS, width=5, arrow="block")
    d.edge(dc, sv, "decrypt · VPN 10 · Gi3", color=V10, width=4, arrow="block", size=15)
    d.st(7)
    d.line(1180, 605, 420, 605, color=G, width=2, dashed=True, arrow="block", label="reply: DC-E1's own copy of the policy chooses", size=15)
    d.st(8)
    d.rect(880, 110, 690, 200, "rounded=1;fillColor=#f4f6f7;strokeColor=#aab7b8;dashed=1;", "")
    for i, ic in enumerate(("manager", "controller", "validator")): d.icon(ic, 960 + i * 130, 180, "", 0.8)
    d.text(1310, 130, 250, 120, "controllers:<br>not in the data path", 18, bold=True, color=G)
    d.st(10)
    d.box(1000, 640, 570, 120, "controllers gone? tunnels keep working for hours (OMP graceful restart)", fill="#eafaf1", stroke=V10, size=17, valign="middle")

@dg("fail", "The MPLS failover test", "", 3)
def _(d):
    d.st(0)
    b = d.icon("srouter", 200, 430, "BR1-E1", 1.3)
    i = d.icon("cloud", 800, 230, "INET", 1.1, color=INET); m = d.icon("cloud", 800, 620, "MPLS", 1.1, color=MPLS)
    dc = d.icon("srouter", 1400, 430, "DC-E1", 1.3)
    d.edge(b, i, color=INET, width=3); d.edge(b, m, color=MPLS, width=3)
    d.edge(i, dc, color=INET, width=3)
    d.edge(m, dc, "+300 ms each way ≈ 600 ms RTT", color=CTRL, width=6, size=18)
    d.st(1)
    d.box(30, 620, 560, 110, "only tunnels to the DC over MPLS break CRITICAL-SLA (150 ms)", fill="#fdedec", stroke=CTRL, size=18, valign="middle")
    d.st(2)
    d.box(30, 120, 560, 110, "everything over the Internet stays fast → CORP-AAR moves ICMP to biz-internet", fill="#fdf2e9", stroke=INET, size=18, valign="middle")

@dg("vrrp", "Router failure test at branch one (VRRP)", "", 8)
def _(d):
    d.st(0)
    pc = d.icon("pc", 150, 440, "BR1-PC<br>gw 10.20.10.1", 1.2)
    sw = d.icon("switch", 360, 440, "LAN VPN 10", 0.9)
    e1 = d.icon("srouter", 650, 250, "BR1-E1", 1.3); e2 = d.icon("srouter", 650, 630, "BR1-E2", 1.3)
    d.edge(pc, sw, color=V10, width=3)
    d.edge(sw, e1, color=V10, width=3); d.edge(sw, e2, color=V10, width=3)
    ov = d.icon("cloud", 1000, 440, "overlay", 1.1, color=G)
    d.edge(e1, ov, color=G, width=2); d.edge(e2, ov, color=G, width=2)
    dc = d.icon("srouter", 1000, 700, "DC-E1 → DC-SRV", 1.0)
    d.edge(ov, dc, color=G, width=2)
    d.text(380, 330, 160, 60, "VIP<br>10.20.10.1", 17, bold=True, color=V10)
    d.st(1, 3)
    tag(d, 730, 170, 220, 50, "priority 110 · MASTER", V10)
    tag(d, 730, 550, 220, 50, "priority 100 · backup", G)
    d.st(4, 6)
    d.text(600, 180, 100, 120, "✕", 90, bold=True, color=CTRL)
    tag(d, 730, 170, 220, 50, "powered off", CTRL)
    d.st(5, 6)
    tag(d, 730, 550, 220, 50, "MASTER now", V10)
    d.st(7)
    tag(d, 730, 170, 260, 50, "back · MASTER (preempt)", V10)
    tag(d, 730, 550, 220, 50, "backup again", G)
    d.st(2)
    d.box(1180, 120, 390, 420, "<b>Test in five steps</b>", fill=WB, stroke="#049FD9", size=19)
    for j, t in enumerate(["1 ping PC → DC server", "2 power off BR1-E1", "3 BR1-E2 takes over, ping", "4 what Manager + OMP say", "5 power on, E1 takes back"]):
        d.st(3 + j, 3 + j)
        d.text(1200, 170 + j * 70, 360, 60, "▶ " + t, 19, align="left", bold=True, color="#049FD9")
        d.st(4 + j)
        d.text(1200, 170 + j * 70, 360, 60, t, 18, align="left")

def render(names=None, last=False):
    os.makedirs("png", exist_ok=True)
    jobs = []
    for name, (title, sub, n, f) in DG.items():
        if names and name not in names: continue
        for k in ([n-1] if last else range(n)):
            d = D(title=title, sub=sub or None, k=k); f(d)
            fn = f"{name}_{k}"; d.save(fn); jobs.append(fn)
    for fn in jobs:
        subprocess.run(f"xvfb-run -a drawio -x -f png --border 0 -o png/{fn}.png src/{fn}.drawio >/dev/null 2>&1", shell=True)
    print(len(jobs), "stages")

if __name__ == "__main__":
    a=sys.argv[1:]; last="--last" in a; a=[x for x in a if x!="--last"]
    render(a or None, last)
