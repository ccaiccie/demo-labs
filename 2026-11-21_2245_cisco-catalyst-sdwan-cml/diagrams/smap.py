"""Setup mini-map: the lab topology drawn with Cisco19 stencils.
Every element carries a tag; for a highlight set H the tagged elements in H
get a yellow halo and full colour, everything else is faded."""
import sys, os, subprocess
from dlib import D
INET="#D35400"; MPLS="#1F618D"; CTRL="#C0392B"; V10="#1E8449"; V20="#7D3C98"; GREY="#5b6b7b"
W,H=900,1240

class M(D):
    def __init__(s,hl):
        s.hl=set(hl); s.tag=None
        super().__init__(W,H)
        s.c=[x for x in s.c if 'fillColor=#049FD9' not in x[1]]  # drop top accent bar
    def g(s,*tags): s.tag=set(t for t in tags if t) or None; return s
    def _hit(s): return s.tag is not None and bool(s.tag & s.hl)
    def _add(s,x,layer=0):
        t=s.tag
        if t is not None and s.hl and not s._hit():
            x=x.replace('style="','style="opacity=18;textOpacity=25;',1)
        s.c.append((layer,x))
    def halo(s,x,y,w,h):
        if s._hit():
            st="rounded=1;arcSize=20;fillColor=#FFF3B0;strokeColor=#F1C40F;strokeWidth=4;html=1;"
            s.c.append((0,f'<mxCell id="{s._id()}" value="" style="{st}" vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'))
    def ic(s,tag,kind,cx,cy,label,scale=1.0,size=27,color="#1d2733",hw=120,hh=120,dy=10):
        s.g(tag); s.halo(cx-hw/2,cy-hh/2+dy,hw,hh); return s.icon(kind,cx,cy,label,scale,size,color)
    def chip(s,tag,x,y,w,h,val,fill,stroke,size=23):
        s.g(tag); s.halo(x-8,y-8,w+16,h+16)
        return s.box(x,y,w,h,val,fill=fill,stroke=stroke,size=size,bold=True,valign="middle",top=True)

def build(hl,name):
    m=M(hl)
    m.g("cml"); m.halo(14,218,872,1014)
    m.box(26,230,848,990,"CML lab: sdwan-demo",fill="#F7FBFE",stroke="#049FD9",size=25,dashed=True,bold=True)
    you=m.ic("you","laptop",110,90,"You (mydell1)",1.2,hw=200,hh=150,dy=18)
    ca=m.ic("ca","cert",780,86,"Root CA",1.1,hw=170,hh=150,dy=18)
    m.chip("serial",255,30,210,44,"WAN edge list","#FEF5E7","#D68910")
    m.chip("cg",255,84,210,44,"BRANCH-CG","#E9F7EF","#1E8449")
    m.chip("pol",255,138,210,44,"Policy group","#F5EEF8","#7D3C98")
    m.g("objs","serial","cg","pol"); m.text(472,84,330,44,"← held by the Manager",19,bold=True,color=GREY,align="left")
    mg=m.ic("mgr","manager",160,330,"Manager",1.15,hw=170,hh=150,dy=16)
    vb=m.ic("val","validator",450,330,"Validator",1.15,hw=170,hh=150,dy=16)
    vs=m.ic("ctl","controller",740,330,"Controller",1.15,hw=170,hh=150,dy=16)
    m.g("mgmt"); m.line(110,158,150,288,color=GREY,width=3,dashed=True,label="System Bridge",size=19)
    m.g("ca"); m.line(775,165,748,288,color="#D68910",width=3,arrow="classic",label="signs certs",size=19)
    m.g("vpn0"); m.halo(40,448,820,70)
    m.box(50,458,800,24,"",fill="#FADBD8",stroke=CTRL,size=14)
    m.text(50,486,800,24,"vrf vpn0 · 172.16.0.0/24 (controllers)",21,bold=True,color=CTRL)
    for x in (160,450,740): m.line(x,385,x,458,color=CTRL,width=3)
    m.line(450,510,450,565,color=CTRL,width=3)
    gw=m.ic("gw","router",450,605,"Gateway (vpn0 · inet · mpls)",1.15,size=25,hw=380,hh=140,dy=20)
    m.g("inet"); m.halo(100,684,280,124)
    m.icon("cloud",240,745,"",1.5,color=INET)
    m.text(165,722,150,40,"INET",30,bold=True,color=INET)
    m.text(140,761,200,26,"172.16.1.0/24",21,bold=True,color=INET)
    m.line(412,606,240,606,color=INET,width=4); m.line(240,606,240,690,color=INET,width=4)
    m.line(240,800,240,848,color=INET,width=4); m.line(70,848,830,848,color=INET,width=4)
    m.g("mpls"); m.halo(520,684,280,124)
    m.icon("cloud",660,745,"",1.5,color=MPLS)
    m.text(585,722,150,40,"MPLS",30,bold=True,color=MPLS)
    m.text(560,761,200,26,"172.16.2.0/24",21,bold=True,color=MPLS)
    m.line(488,606,660,606,color=MPLS,width=4); m.line(660,606,660,690,color=MPLS,width=4)
    m.line(660,800,660,866,color=MPLS,width=4); m.line(70,866,830,866,color=MPLS,width=4)
    sites=[("DC · site 10",40,170,[("DC-E1",110)]),("BR1 · site 20",222,300,[("BR1-E1",290),("BR1-E2",440)]),
           ("BR2 · site 30",532,164,[("BR2-E1",614)]),("BR3 · site 40",706,156,[("BR3-E1",784)])]
    for lab,x,w,eds in sites:
        m.g("sites",lab.split()[0]); m.halo(x-8,904,w+16,316)
        m.box(x,912,w,300,lab,fill="#FFFFFF",stroke="#99A3AD",size=19,bold=True)
    m.g("tun"); m.halo(50,878,800,30)
    m.line(70,893,830,893,color=V10,width=4,dashed=True)
    m.rect(130,878,146,26,"text;fillColor=#FFFFFF;strokeColor=none;fontSize=18;fontStyle=1;fontColor=#1E8449;align=center;verticalAlign=middle;","IPsec overlay",layer=2)
    for lab,x,w,eds in sites:
        for e,cx in eds:
            m.g("inet",e); m.line(cx-14,966,cx-14,848,color=INET,width=2)
            m.g("mpls",e); m.line(cx+14,966,cx+14,866,color=MPLS,width=2)
            m.g("edge",e,lab.split()[0]); m.halo(cx-64,948,128,112)
            m.icon("router",cx,995,"",0.85)
            m.text(cx-75,1030,150,28,e,22,bold=True)
    hosts=[("DC-SRV","server",110,V10),("BR1-PC","pc",290,V10),("BR1-GUEST","laptop",440,V20),
           ("BR2-PC","pc",574,V10),("BR2-GUEST","laptop",656,V20),("BR3-PC","pc",784,V10)]
    for h,k,cx,col in hosts:
        m.g("hosts",h,h.split("-")[0],"v10" if col==V10 else "v20"); m.halo(cx-40 if "BR2" in h else cx-58,1094,80 if "BR2" in h else 116,118)
        m.line(cx,1056,cx,1108,color=col,width=3)
        m.icon(k,cx,1135,"",0.8 if k!="server" else 0.7)
        m.text(cx-75,1166 if h!="BR2-GUEST" else 1188,150,24,h,19 if "BR2" not in h else 17,bold=True,color=col)
    m.g(None)
    m.save(name)

SETS={}
def key(hl): return "sm_"+("_".join(sorted(hl)) if hl else "all")

def render(hl):
    n=key(hl); png=f"png/{n}.png"
    if not os.path.exists(png):
        build(hl,n)
        subprocess.run(f"xvfb-run -a drawio -x -f png --border 0 -o {png} src/{n}.drawio",shell=True,check=True,capture_output=True)
    return png

if __name__=="__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    hl=sys.argv[1:] 
    print(render(hl))
