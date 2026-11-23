"""Concept diagrams for the Catalyst 9800 wireless on CML lesson.
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

# ------------------------------------------------------------ autonomous vs controller
@dg("why", "Autonomous APs vs a wireless controller", "Why enterprises centralise Wi-Fi", 3)
def _(d):
    d.st(0)
    d.box(40, 110, 740, 600, "<b>Autonomous APs</b>", fill="#fdf2e9", stroke=GU, size=20)
    eng = d.icon("user", 410, 210, "Engineer", 1.1)
    for i, x in enumerate([170, 410, 650]):
        a = d.icon("ap", x, 430, f"AP{i+1}")
        d.edge(eng, a, "config by hand" if i == 1 else "", color=GU, dashed=True, arrow="block")
        d.box(x - 105, 500, 210, 92, ["SSID CORP<br>key v3<br>ch 6", "SSID corp<br>key v2<br>ch 6", "SSID CORP<br>key v3<br>ch 11"][i], fill=WB, stroke=GU, size=15, valign="middle")
    d.text(60, 615, 700, 80, "Every AP is its own island: drifting configs, no shared view of RF, clients re-authenticate when they roam", 17, color=GU, bold=True)
    d.st(1)
    d.box(820, 110, 740, 600, "<b>Controller-based (Catalyst 9800)</b>", fill="#eafaf1", stroke=DA, size=20)
    w = d.icon("wlc", 1190, 230, "WLC: one config, one policy", 1.1)
    aps = [d.icon("ap", x, 470, f"AP{i+1}") for i, x in enumerate([950, 1190, 1430])]
    for a in aps: d.edge(w, a, "CAPWAP", color=CT, width=3, dashed=True)
    d.st(2)
    d.text(840, 560, 700, 140, "Lightweight APs download everything from the controller: WLANs, security, VLAN mapping, RF channels and power. Roaming, client tracking and troubleshooting live in one place.", 17, color=DA, bold=True)

# ------------------------------------------------------------ CAPWAP
@dg("capwap", "How an AP talks to the controller: CAPWAP", "Two UDP tunnels between every AP and the WLC", 3)
def _(d):
    d.st(0)
    ap = d.icon("ap", 250, 400, "Access point (vAP)", 1.4)
    sw = d.icon("l3switch", 800, 400, "SW1 (any IP network)", 1.2)
    w = d.icon("wlc", 1350, 400, "Catalyst 9800-CL", 1.4)
    d.edge(ap, sw, color=G, width=3); d.edge(sw, w, color=G, width=3)
    d.st(1)
    d.line(330, 300, 1270, 300, color=CT, width=5, arrow="block", start="block", label="Control: UDP 5246, always DTLS-encrypted (join, config, RF, stats)", size=18)
    d.st(2)
    d.line(330, 510, 1270, 510, color=DA, width=5, arrow="block", start="block", label="Data: UDP 5247, client frames tunnelled to the WLC (central switching)", size=18)
    d.box(380, 610, 840, 110, "The WLC unwraps client traffic and drops it onto a VLAN, so a CORP client lands in VLAN 20 and a GUEST client in VLAN 30, no matter which AP it joined.", fill=LB, stroke=B, size=17, valign="middle")

# ------------------------------------------------------------ AP join
@dg("join", "The AP join process", "What happens between power-on and a working radio", 6)
def _(d):
    d.st(0)
    ap = d.icon("ap", 180, 420, "AP", 1.3)
    dh = d.icon("l3switch", 620, 180, "DHCP server (SW1)", 1.0)
    w = d.icon("wlc", 1380, 420, "WLC 10.10.100.254", 1.3)
    steps = [
        ("1  DHCP: IP 10.10.100.x plus option 43 = WLC address", B),
        ("2  CAPWAP discovery request → discovery response", NV),
        ("3  DTLS handshake: AP and WLC exchange certificates", CT),
        ("4  Join request / join response", CT),
        ("5  Image check, then configuration download (tags → WLANs, RF)", DA),
    ]
    for i, (t, c) in enumerate(steps):
        d.st(i + 1)
        y = 300 + i * 80
        d.line(270, y, 1290, y, color=c, width=3, arrow="block", start="block" if i else "none", label=t, size=17)
    d.st(3)
    d.icon("cert", 1380, 300, "", 0.6)
    d.box(1080, 120, 480, 100, "Virtual WLC gotcha: it has no factory certificate, so we create the <b>manual_certs</b> trustpoint", fill="#fef9e7", stroke="#B7950B", size=15, valign="middle", top=True)

# ------------------------------------------------------------ tags and profiles
@dg("tags", "The 9800 configuration model: profiles and tags", "Build the pieces once, then attach them to APs with tags", 5)
def _(d):
    d.st(0)
    tag(d, 60, 140, 300, 70, "WLAN profile<br>CORP / GUEST (SSID, WPA2-PSK)", NV, 16)
    tag(d, 60, 260, 300, 70, "Policy profile<br>CORP-POLICY → VLAN 20", DA, 16)
    tag(d, 60, 380, 300, 70, "AP join profile<br>(CAPWAP, management)", MG, 16)
    tag(d, 60, 500, 300, 70, "RF profile<br>(default 2.4 / 5 GHz)", GU, 16)
    d.st(1)
    d.line(360, 175, 560, 235, color=NV, width=3, arrow="block"); d.line(360, 295, 560, 245, color=DA, width=3, arrow="block")
    tag(d, 560, 200, 330, 90, "<b>Policy tag</b> LAB-POLICY-TAG<br>CORP + CORP-POLICY<br>GUEST + GUEST-POLICY", DA, 16, bold=False)
    d.st(2)
    d.line(360, 415, 560, 415, color=MG, width=3, arrow="block")
    tag(d, 560, 370, 330, 90, "<b>Site tag</b> default-site-tag<br>default AP join profile, local mode", MG, 16, bold=False)
    d.line(360, 535, 560, 535, color=GU, width=3, arrow="block")
    tag(d, 560, 500, 330, 70, "<b>RF tag</b> default-rf-tag", GU, 16, bold=False)
    d.st(3)
    a1 = d.icon("ap", 1150, 300, "AP1", 1.2); a2 = d.icon("ap", 1150, 500, "AP2", 1.2)
    for y in (245, 415, 535):
        d.line(890, y, 1090, 300, color=G, width=2, arrow="block"); d.line(890, y, 1090, 500, color=G, width=2, arrow="block")
    d.st(4)
    d.box(1240, 220, 330, 360, "Every AP carries exactly three tags. Change a tag and every AP using it updates.<br><br>An AP with the <b>default-policy-tag</b> maps the SSIDs to default-policy-profile, which puts clients in the AP VLAN 100.", fill=LB, stroke=B, size=17, valign="middle")

# ------------------------------------------------------------ topology
@dg("topo", "The lab we will build in CML", "Ten nodes, five VLANs, two SSIDs", 4)
def _(d):
    d.st(0)
    inet = d.icon("cloud", 200, 200, "Internet (CML NAT)", 0.9)
    r1 = d.icon("router", 200, 420, "R1  NAT edge")
    sw = d.icon("l3switch", 620, 420, "SW1  gateways + DHCP")
    srv = d.icon("server", 620, 190, "SRV1 10.10.50.10")
    w = d.icon("wlc", 1100, 420, "WLC1  Catalyst 9800-CL")
    mg = d.icon("gcloud", 1100, 190, "Mgmt (System Bridge)", 0.8)
    d.edge(inet, r1, "e0/1", color=G, width=3); d.edge(r1, sw, "e0/0 – e0/3  VLAN 254", color=G, width=3)
    d.edge(srv, sw, "e1/0  VLAN 50", color=G, width=3)
    d.edge(sw, w, "e0/0 – Gi1  trunk 20,30,100", color=G, width=4)
    d.edge(mg, w, "Gi2  192.168.122.60 (WebUI)", color=MG, width=3, dashed=True)
    d.st(1)
    a1 = d.icon("ap", 470, 600, "AP1"); a2 = d.icon("ap", 780, 600, "AP2")
    d.edge(sw, a1, "e0/1", color=G, width=3); d.edge(sw, a2, "e0/2", color=G, width=3)
    d.text(860, 585, 360, 50, "VLAN 100 (AP management)<br>CAPWAP to 10.10.100.254", 15, color=CT, bold=True)
    d.st(2)
    c1 = d.icon("laptop", 470, 730, "CLIENT1 → CORP"); c2 = d.icon("laptop", 780, 730, "CLIENT2 → GUEST")
    d.line(470, 640, 470, 700, color=NV, width=3, dashed=True); d.line(780, 640, 780, 700, color=GU, width=3, dashed=True)
    d.st(3)
    d.box(1240, 520, 330, 230, "<b>VLANs on SW1</b><br>20 CORP 10.10.20.0/24<br>30 GUEST 10.10.30.0/24<br>50 SERVERS 10.10.50.0/24<br>100 AP-MGMT 10.10.100.0/24<br>254 transit to R1", fill=LB, stroke=B, size=16, valign="middle", align="left")

# ------------------------------------------------------------ CML wifi
@dg("sim", "How CML simulates Wi-Fi", "There is no real radio: a shared virtual medium on the CML host", 3)
def _(d):
    d.st(0)
    d.box(120, 360, 1360, 140, "", fill="#f4ecf7", stroke=MG, size=18, dashed=True)
    d.text(140, 470, 1320, 30, "Simulated wireless medium on the CML server, shared by every wireless node in the lab", 17, color=MG, bold=True)
    a1 = d.icon("ap", 400, 230, "vAP: CAPWAP AP image, radios join the medium")
    a2 = d.icon("ap", 1200, 230, "AP2")
    d.line(400, 270, 400, 400, color=MG, width=3, dashed=True); d.line(1200, 270, 1200, 400, color=MG, width=3, dashed=True)
    d.st(1)
    c1 = d.icon("laptop", 400, 640, "Wireless client node (Linux + wpa_supplicant)")
    c2 = d.icon("laptop", 1200, 640, "CLIENT2")
    d.line(400, 460, 400, 610, color=MG, width=3, dashed=True); d.line(1200, 460, 1200, 610, color=MG, width=3, dashed=True)
    d.st(2)
    d.box(560, 120, 480, 160, "Gotchas:<br>• vAP supports one wired NIC only<br>• set <b>ap country</b> or radios stay down<br>• vAP is a beta feature in CML", fill="#fef9e7", stroke="#B7950B", size=16, valign="middle", align="left")

# ------------------------------------------------------------ security
@dg("sec", "WLAN security and guest isolation", "WPA2-Personal for both SSIDs; an ACL keeps guests away from internal networks", 3)
def _(d):
    d.st(0)
    c1 = d.icon("laptop", 160, 300, "CLIENT1"); c2 = d.icon("laptop", 160, 560, "CLIENT2")
    a = d.icon("ap", 480, 430, "AP")
    d.edge(c1, a, "CORP: WPA2-PSK + AES", color=NV, width=3, dashed=True); d.edge(c2, a, "GUEST: WPA2-PSK + AES", color=GU, width=3, dashed=True)
    d.text(40, 680, 600, 60, "4-way handshake derives per-client keys from the passphrase", 16, color=G, bold=True)
    d.st(1)
    w = d.icon("wlc", 800, 430, "WLC")
    sw = d.icon("l3switch", 1100, 430, "SW1")
    d.edge(a, w, "CAPWAP", color=CT, width=3); d.edge(w, sw, "VLAN 20 / VLAN 30", color=G, width=3)
    d.st(2)
    srv = d.icon("server", 1430, 260, "SRV1 (internal)"); net = d.icon("cloud", 1430, 600, "Internet", 0.8)
    d.edge(sw, srv, "CORP allowed", color=DA, width=3, arrow="block")
    d.edge(sw, net, "GUEST allowed", color=DA, width=3, arrow="block")
    d.box(1120, 660, 440, 100, "ACL GUEST-IN on Vlan30: deny 10/8, 172.16/12, 192.168/16 → guests reach only the Internet", fill="#fdedec", stroke=CT, size=15, valign="middle", top=True)

# ------------------------------------------------------------ test plan
@dg("tests", "Test plan", "How we prove the wireless network works", 2)
def _(d):
    d.st(0)
    rows = [("APs joined", "Monitoring › AP statistics: AP1 and AP2 registered, radios up", DA),
            ("CORP client", "CLIENT1 associates, gets 10.10.20.x, pings SRV1 and 8.8.8.8", NV),
            ("GUEST client", "A client on GUEST gets 10.10.30.x, reaches 8.8.8.8, SRV1 is blocked", GU),
            ("Controller view", "Monitoring › Clients: SSID, VLAN, AP, state RUN", B),
            ("AP failure", "Stop AP1 – the client re-associates through AP2", CT)]
    for i, (a, b, c) in enumerate(rows):
        d.st(0 if i < 3 else 1)
        y = 130 + i * 120
        tag(d, 80, y, 330, 90, a, c, 19)
        d.box(430, y, 1090, 90, b, fill=WB, stroke=c, size=18, valign="middle", align="left")

# ------------------------------------------------------------ bring-up gotchas
@dg("gotcha", "Bring-up gotchas on the virtual WLC", "Five things the WebUI alone would not have fixed", 5)
def _(d):
    rows = [("Vlan99 had no IP", "Day-0 address did not apply: set it on the console, then the WebUI answers on 192.168.122.60", MG),
            ("No AP certificate", "9800-CL has no factory certificate: import the manual_certs trustpoint, use it for wireless management", CT),
            ("DTLS join failed", "Certificate revocation check (CRL) could not complete: revocation-check none on manual_certs (lab only)", CT),
            ("Radios down", "ap country US is refused while the 2.4 / 5 / 6 GHz networks are up: shut them, set the country, no shut", GU),
            ("Wizard choices", "Guest type forces web auth + RADIUS, so GUEST is built as WPA2-PSK; trunk widened to 20,30,100; Generate Certificate off", NV)]
    for i, (a, b, c) in enumerate(rows):
        d.st(i)
        y = 125 + i * 125
        tag(d, 60, y, 330, 95, a, c, 19)
        d.box(410, y, 1130, 95, b, fill=WB, stroke=c, size=18, valign="middle", align="left")

# ------------------------------------------------------------ CLIENT2 troubleshooting
@dg("debug", "Troubleshooting CLIENT2 with CML tools", "Symptom: CLIENT2 sees both SSIDs but never associates", 5)
def _(d):
    rows = [("1  Client log", "Authentication attempts to every BSSID time out, then the BSSID is ignored", NV),
            ("2  CML wireless capture", "Right-click the node > Wireless: Authentication frames go out, nothing comes back from the AP", MG),
            ("3  Controller log", "While CLIENT2 retries, AP2 keeps dropping and re-joining its CAPWAP session", CT),
            ("4  Split the problem", "Stop CLIENT2: AP2 stays up. Point CLIENT1 at GUEST: it joins AP2 at once", DA),
            ("5  Conclusion", "WLC, WLAN and AP config are fine; the fault follows that one simulated client node (beta feature)", B)]
    for i, (a, b, c) in enumerate(rows):
        d.st(i)
        y = 125 + i * 125
        tag(d, 60, y, 360, 95, a, c, 19)
        d.box(440, y, 1100, 95, b, fill=WB, stroke=c, size=18, valign="middle", align="left")

# ------------------------------------------------------------ AP failover
@dg("roam", "AP failure test", "Central switching keeps the client in VLAN 20 whichever AP it uses", 3)
def _(d):
    d.st(0)
    w = d.icon("wlc", 800, 170, "WLC1  CORP → CORP-POLICY → VLAN 20")
    a1 = d.icon("ap", 450, 420, "AP1"); a2 = d.icon("ap", 1150, 420, "AP2")
    d.edge(w, a1, "CAPWAP", color=CT, width=3, dashed=True); d.edge(w, a2, "CAPWAP", color=CT, width=3, dashed=True)
    c = d.icon("laptop", 800, 650, "CLIENT1  10.10.20.101")
    d.line(780, 625, 480, 460, color=NV, width=4, label="CORP on AP1", size=16)
    d.st(1)
    d.box(330, 300, 240, 50, "AP1 stopped in CML", fill="#fdedec", stroke=CT, size=16, valign="middle")
    d.line(830, 625, 1120, 460, color=DA, width=4, dashed=True, label="re-associate to AP2", size=16)
    d.st(2)
    d.box(1080, 560, 480, 170, "Real clients notice missing beacons and roam by themselves. The simulated client kept its old state, so we triggered a rescan and reassociate. Same SSID, same policy profile, same VLAN: same IP.", fill=LB, stroke=B, size=15, valign="middle", align="left")

# ------------------------------------------------------------ lessons
@dg("lessons", "Lessons learned", "The things that cost time in this lab", 2)
def _(d):
    d.st(0)
    items = ["Give the 9800-CL 4 vCPU and 8 GB (local mode); the default is smaller",
             "Virtual WLC: import the manual_certs trustpoint; in the lab, revocation-check none",
             "Shut the radio networks, set ap country, then bring them back",
             "Check the switch VLAN database (show vlan brief), not only the SVIs",
             "Policy tags map SSIDs to VLANs; the trunk must carry every client VLAN",
             "CML wireless capture plus controller logs isolate client-side faults fast",
             "Wireless nodes are beta: expect sim quirks (CLIENT2, no beacon-loss roaming)"]
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
        subprocess.run(f"timeout 120 xvfb-run -a drawio --no-sandbox --disable-gpu -x -f png --border 0 -o png/{fn}.png src/{fn}.drawio >/dev/null 2>&1", shell=True)
    print(len(jobs), "stages")

if __name__ == "__main__":
    a = sys.argv[1:]; last = "--last" in a; a = [x for x in a if x != "--last"]
    render(a or None, last)
