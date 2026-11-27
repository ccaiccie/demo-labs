"""Tiny draw.io generator with step-based reveal + highlight."""
import html, os

W, H = 1800, 860
AZ = "img/lib/azure2/"
ICONS = {
    "vnet": "networking/Virtual_Networks.svg", "pe": "networking/Private_Endpoint.svg",
    "pl": "networking/Private_Link.svg", "pls": "networking/Private_Link_Service.svg",
    "sql": "databases/SQL_Database.svg", "sqlmi": "databases/SQL_Managed_Instance.svg",
    "blob": "storage/Storage_Accounts.svg", "kv": "security/Key_Vaults.svg",
    "app": "app_services/App_Services.svg", "ase": "app_services/App_Service_Environments.svg",
    "func": "compute/Function_Apps.svg", "apim": "app_services/API_Management_Services.svg",
    "aks": "compute/Kubernetes_Services.svg", "cosmos": "databases/Azure_Cosmos_DB.svg",
    "vm": "compute/Virtual_Machine.svg", "lb": "networking/Load_Balancers.svg",
    "pip": "networking/Public_IP_Addresses.svg", "gw": "networking/Virtual_Network_Gateways.svg",
    "er": "networking/ExpressRoute_Circuits.svg", "dnsr": "networking/DNS_Private_Resolver.svg",
    "dnsz": "networking/DNS_Zones.svg", "udr": "networking/Route_Tables.svg",
    "nsg": "networking/Network_Security_Groups.svg", "agw": "networking/Application_Gateways.svg",
    "afd": "networking/Front_Doors.svg", "waf": "networking/Web_Application_Firewall_Policies_WAF.svg",
    "nsp": "other/Network_Security_Perimeters.svg", "sep": "networking/Service_Endpoint_Policies.svg",
    "vwan": "networking/Virtual_WANs.svg", "vhub": "networking/Virtual_WAN_Hub.svg",
    "users": "identity/Users.svg", "policy": "management_governance/Policy.svg",
    "law": "management_governance/Log_Analytics_Workspaces.svg", "mi": "identity/Managed_Identities.svg",
    "defender": "security/Azure_Defender.svg", "nic": "networking/Network_Interfaces.svg",
    "subnet": "networking/Subnet.svg", "nat": "networking/NAT.svg", "monitor": "management_governance/Monitor.svg",
    "watcher": "networking/Network_Watcher.svg", "sentinel": "security/Azure_Sentinel.svg",
}
GROUP_STY = {
    "hub": "fillColor=#EAF3FB;strokeColor=#0078D4;",
    "spoke": "fillColor=#F1F8EC;strokeColor=#5C9E31;",
    "onprem": "fillColor=#F3F2F1;strokeColor=#605E5C;",
    "paas": "fillColor=#F4ECFA;strokeColor=#8661C5;",
    "subnet": "fillColor=#FFFFFF;strokeColor=#7FA7D1;dashed=1;",
    "internet": "fillColor=#FFF8EC;strokeColor=#C19C00;",
    "bad": "fillColor=#FDECEC;strokeColor=#C50F1F;",
    "good": "fillColor=#E9F6EC;strokeColor=#107C10;",
    "plain": "fillColor=#FFFFFF;strokeColor=#8A8886;",
    "none": "fillColor=none;strokeColor=none;",
}
FLOW = {"blue": "#0078D4", "green": "#107C10", "red": "#C50F1F", "orange": "#E8590C",
        "purple": "#8661C5", "gray": "#8A8886", "teal": "#038387", "black": "#323130"}
HL = "#E8590C"


def esc(s):
    return html.escape(s, quote=True)


class Diagram:
    def __init__(self, name):
        self.name = name
        self.cells = []  # (id, kind, dict)
        self.ids = set()

    def _add(self, cid, kind, **kw):
        assert cid not in self.ids, (self.name, cid)
        self.ids.add(cid)
        self.cells.append((cid, kind, kw))
        return cid

    def group(self, cid, x, y, w, h, label, sty="hub", fs=17, valign="top", align="left"):
        return self._add(cid, "group", x=x, y=y, w=w, h=h, label=label, sty=sty, fs=fs, valign=valign, align=align)

    def icon(self, cid, x, y, key, label="", s=56, fs=15, lpos="bottom", lw=None):
        return self._add(cid, "icon", x=x, y=y, s=s, key=key, label=label, fs=fs, lpos=lpos, lw=lw)

    def fw(self, cid, x, y, label="", s=60, fs=15, lpos="bottom", lw=None):
        return self._add(cid, "fw", x=x, y=y, s=s, label=label, fs=fs, lpos=lpos, lw=lw)

    def cloud(self, cid, x, y, w, h, label, fs=16):
        return self._add(cid, "cloud", x=x, y=y, w=w, h=h, label=label, fs=fs)

    def note(self, cid, x, y, w, h, text, sty="plain", fs=16, align="left", bold=False, va="top"):
        return self._add(cid, "note", x=x, y=y, w=w, h=h, text=text, sty=sty, fs=fs, align=align, bold=bold, va=va)

    def edge(self, cid, s, t, label="", color="blue", dashed=False, w=2.5, pts=None,
             ex=None, ey=None, nx=None, ny=None, both=False, fs=14, arrow=True, lx=None, ly=None):
        return self._add(cid, "edge", s=s, t=t, label=label, color=color, dashed=dashed, w=w, pts=pts or [],
                         ex=ex, ey=ey, nx=nx, ny=ny, both=both, fs=fs, arrow=arrow, lx=lx, ly=ly)

    # ------------------------------------------------------------------
    def xml(self, show, hl, title=""):
        show = set(show)
        hl = set(hl)
        dim = len(hl) > 0
        geo = {}
        for cid, kind, k in self.cells:
            if kind in ("icon", "fw"):
                geo[cid] = (k["x"], k["y"], k["x"] + k["s"], k["y"] + k["s"])
            elif kind != "edge":
                geo[cid] = (k["x"], k["y"], k["x"] + k["w"], k["y"] + k["h"])
        lit = set(hl)
        for g in [c for c in hl if c in geo and self._kind(c) == "group"]:
            gx0, gy0, gx1, gy1 = geo[g]
            for cid, (x0, y0, x1, y1) in geo.items():
                if x0 >= gx0 and y0 >= gy0 and x1 <= gx1 and y1 <= gy1:
                    lit.add(cid)
        for cid, kind, k in self.cells:
            if kind == "edge" and k["s"] in lit and k["t"] in lit and any(self._kind(c) == "group" for c in hl):
                lit.add(cid)
        out = ['<mxfile><diagram name="%s"><mxGraphModel dx="0" dy="0" grid="0" page="0"><root>'
               '<mxCell id="0"/><mxCell id="1" parent="0"/>' % esc(self.name),
               '<mxCell id="__frame" value="" style="rounded=0;fillColor=#FFFFFF;strokeColor=none;" vertex="1" parent="1">'
               '<mxGeometry x="0" y="0" width="%d" height="%d" as="geometry"/></mxCell>' % (W, H)]
        for cid, kind, k in self.cells:
            if cid not in show:
                continue
            if kind == "edge" and (k["s"] not in show or k["t"] not in show):
                continue
            is_hl = cid in hl
            op = "" if (not dim or cid in lit) else "opacity=38;textOpacity=45;"
            if kind == "group":
                st = GROUP_STY[k["sty"]]
                if is_hl:
                    st = st.replace("strokeColor=", "strokeColor=%s;x=" % HL) + "strokeWidth=4;"
                elif dim and cid not in lit and k["sty"] in ("hub", "spoke", "onprem", "paas", "internet", "plain", "good", "bad"):
                    op = "opacity=55;textOpacity=60;"  # containers stay readable
                style = ("rounded=1;arcSize=3;whiteSpace=wrap;html=1;verticalAlign=%s;align=%s;spacingLeft=10;spacingTop=4;"
                         "fontStyle=1;fontSize=%d;fontColor=#201F1E;strokeWidth=2;%s%s") % (k["valign"], k["align"], k["fs"], st, op)
                out.append(self._v(cid, k["label"], style, k["x"], k["y"], k["w"], k["h"]))
            elif kind in ("icon", "fw"):
                s = k["s"]
                if is_hl and dim:
                    pad = 10
                    out.append(self._v(cid + "__halo", "", "rounded=1;fillColor=#FFF4CE;strokeColor=%s;strokeWidth=3;" % HL,
                                       k["x"] - pad, k["y"] - pad, s + 2 * pad, s + 2 * pad))
                if kind == "icon":
                    img = "image;aspect=fixed;html=1;image=%s%s;" % (AZ, ICONS[k["key"]])
                else:
                    img = ("shape=mxgraph.networks.firewall;html=1;strokeColor=none;fillColor=#FA582D;"
                           "outlineConnect=0;")
                lp = k.get("lpos", "bottom")
                if lp == "bottom":
                    lab = "verticalLabelPosition=bottom;verticalAlign=top;labelPosition=center;align=center;"
                elif lp == "right":
                    lab = "verticalLabelPosition=middle;verticalAlign=middle;labelPosition=right;align=left;spacingLeft=4;"
                elif lp == "left":
                    lab = "verticalLabelPosition=middle;verticalAlign=middle;labelPosition=left;align=right;spacingRight=4;"
                else:
                    lab = "verticalLabelPosition=top;verticalAlign=bottom;labelPosition=center;align=center;"
                style = img + lab + "whiteSpace=wrap;fontSize=%d;fontColor=#201F1E;labelBackgroundColor=none;%s" % (k["fs"], op)
                if lp in ("bottom", "top"):
                    style += "labelWidth=%d;" % (k.get("lw") or max(190, s + 40))
                out.append(self._v(cid, k["label"], style, k["x"], k["y"], s, s))
            elif kind == "cloud":
                style = ("ellipse;shape=cloud;whiteSpace=wrap;html=1;fillColor=#FFF8EC;strokeColor=#C19C00;strokeWidth=2;"
                         "fontSize=%d;fontStyle=1;%s") % (k["fs"], op)
                if is_hl and dim:
                    style = style.replace("strokeColor=#C19C00", "strokeColor=%s" % HL).replace("strokeWidth=2", "strokeWidth=4")
                out.append(self._v(cid, k["label"], style, k["x"], k["y"], k["w"], k["h"]))
            elif kind == "note":
                st = GROUP_STY[k["sty"]]
                if is_hl and dim:
                    st = st.replace("strokeColor=", "strokeColor=%s;x=" % HL)
                    st += "strokeWidth=3;"
                style = ("rounded=1;arcSize=4;whiteSpace=wrap;html=1;align=%s;verticalAlign=%s;spacing=12;"
                         "fontSize=%d;fontColor=#201F1E;%s%s%s") % (k["align"], k.get("va", "top"), round(k["fs"] * 1.12), st, "fontStyle=1;" if k["bold"] else "", op)
                out.append(self._v(cid, k["text"], style, k["x"], k["y"], k["w"], k["h"]))
            elif kind == "edge":
                col = FLOW[k["color"]]
                wdt = k["w"] + (1.5 if (is_hl and dim) else 0)
                style = ("edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;strokeColor=%s;strokeWidth=%s;fontSize=%d;"
                         "fontColor=%s;labelBackgroundColor=#FFFFFF;fontStyle=1;endArrow=%s;endFill=1;startArrow=%s;startFill=1;%s%s") % (
                    col, wdt, k["fs"], col, "block" if k["arrow"] else "none", "block" if k["both"] else "none",
                    "dashed=1;dashPattern=8 5;" if k["dashed"] else "", op)
                for a, b in (("ex", "exitX"), ("ey", "exitY"), ("nx", "entryX"), ("ny", "entryY")):
                    if k[a] is not None:
                        style += "%s=%s;" % (b, k[a])
                pts = "".join('<mxPoint x="%d" y="%d"/>' % p for p in k["pts"])
                geo = '<mxGeometry relative="1" as="geometry">%s%s</mxGeometry>' % (
                    ('<Array as="points">%s</Array>' % pts) if pts else "",
                    ('<mxPoint x="%d" y="%d" as="offset"/>' % (k["lx"], k["ly"])) if k["lx"] is not None else "")
                out.append('<mxCell id="%s" value="%s" style="%s" edge="1" parent="1" source="%s" target="%s">%s</mxCell>' % (
                    cid, esc(k["label"]), style, k["s"], k["t"], geo))
        out.append("</root></mxGraphModel></diagram></mxfile>")
        return "\n".join(out)

    def _kind(self, cid):
        for c, kind, k in self.cells:
            if c == cid:
                return kind

    @staticmethod
    def _v(cid, label, style, x, y, w, h):
        return ('<mxCell id="%s" value="%s" style="%s" vertex="1" parent="1"><mxGeometry x="%d" y="%d" width="%d" height="%d" as="geometry"/></mxCell>'
                % (cid, esc(label), style, x, y, w, h))
