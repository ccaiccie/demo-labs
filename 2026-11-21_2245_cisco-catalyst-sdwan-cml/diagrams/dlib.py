"""Tiny builder for draw.io diagrams with Cisco 19 stencils."""
from xml.sax.saxutils import escape
S3="verticalLabelPosition=bottom;sketch=0;html=1;verticalAlign=top;aspect=fixed;align=center;pointerEvents=1;shape=mxgraph.cisco19."
RND="rect;fillColor=#FAFAFA;strokeColor=#005073;perimeter=ellipsePerimeter;prIcon="
LBL="fontSize=18;fontColor=#1d2733;fontStyle=1;labelBackgroundColor=none;"
ICON={
 "manager":(S3+RND+"vmanage;",70,70), "controller":(S3+RND+"vsmart;",70,70), "validator":(S3+RND+"vbond;",70,70),
 "router":(S3+RND+"router;",70,70), "srouter":(S3+RND+"secure_router;",70,70),
 "switch":(S3+"rect;prIcon=l2_switch;fillColor=#FAFAFA;strokeColor=#005073;",64,64),
 "firewall":(S3+"rect;prIcon=firewall;fillColor=#FAFAFA;strokeColor=#005073;",80,62),
 "pc":(S3+"workstation2;fillColor=#fafafa;strokeColor=#005073;",62,50),
 "laptop":(S3+"laptop2;fillColor=#fafafa;strokeColor=#005073;",64,45),
 "server":(S3+"server2;fillColor=#fafafa;strokeColor=#005073;",36,66),
 "user":(S3+"user2;fillColor=#fafafa;strokeColor=#005073;",56,56),
 "lock":(S3+"lock2;fillColor=#fafafa;strokeColor=#005073;perimeter=ellipsePerimeter;",56,56),
 "cert":(S3+"x509_certificate2;fillColor=#FAFAFA;strokeColor=#005073;",64,61),
 "dc":(S3+"data_center2;fillColor=#fafafa;strokeColor=#005073;",100,70),
 "branch":(S3+"branch2;fillColor=#fafafa;strokeColor=#005073;",64,64),
 "cloud":(S3+"cloud2;fillColor=#FFE9AA;strokeColor=none;",150,90),
 "bcloud":(S3+"cloud;fillColor=#186180;strokeColor=none;",150,90),
 "gcloud":(S3+"cloud;fillColor=#A6A6A6;strokeColor=none;",150,90),
 "db":(S3+"rect;prIcon=database_relational;fillColor=#FAFAFA;strokeColor=#005073;",60,60),
}
class D:
    def __init__(s,w=1600,h=790,title=None,sub=None,k=99):
        s.w,s.h=w,h; s.c=[]; s.n=2; s.k=k; s.r=(0,99)
        s.rect(0,0,w,h,"fillColor=#FFFFFF;strokeColor=none;")
        s.rect(0,0,w,8,"fillColor=#049FD9;strokeColor=none;")
        if title: s.text(40,22,w-80,46,title,30,bold=True,align="left")
        if sub: s.text(40,68,w-80,30,sub,19,color="#5b6b7b",align="left")
    def _id(s): s.n+=1; return f"c{s.n}"
    def st(s,a,b=99): s.r=(a,b); return s
    def _on(s): return s.r[0]<=s.k<=s.r[1]
    def _add(s,x,layer=0):
        if s._on(): s.c.append((layer,x))
    def cell(s,style,x,y,w,h,val="",vertex=True,layer=0):
        i=s._id(); s._add(layer=layer,x=f'<mxCell id="{i}" value="{escape(val,{chr(34):"&quot;"})}" style="{style}" vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'); return i
    def icon(s,kind,cx,cy,label="",scale=1.0,size=18,color="#1d2733"):
        st,w,h=ICON[kind]; w*=scale; h*=scale
        if kind=="cloud": st=st.replace("#FFE9AA",{"#1F618D":"#AED6F1","#D35400":"#FAD7A0","#5b6b7b":"#D5D8DC"}.get(color,"#FFE9AA"))
        return s.cell(st+f"fontSize={size};fontColor={color};fontStyle=1;labelBackgroundColor=#FFFFFF;",cx-w/2,cy-h/2,w,h,label,layer=2)
    def rect(s,x,y,w,h,style,val="",layer=0):
        return s.cell(style+"html=1;whiteSpace=wrap;",x,y,w,h,val,layer=layer)
    def box(s,x,y,w,h,val="",fill="#eef6fb",stroke="#049FD9",size=18,dashed=False,bold=False,color="#1d2733",valign="top",r=1,align="center",top=False):
        return s.rect(layer=2 if top else 0,x=x,y=y,w=w,h=h,style=f"rounded={r};arcSize=6;fillColor={fill};strokeColor={stroke};strokeWidth=2;fontSize={size};fontColor={color};verticalAlign={valign};align={align};spacingTop=6;spacingLeft=8;spacingRight=8;"+("dashed=1;dashPattern=8 6;" if dashed else "")+("fontStyle=1;" if bold else ""),val=val)
    def text(s,x,y,w,h,val,size=18,bold=False,color="#1d2733",align="center",valign="middle"):
        return s.rect(layer=2,x=x,y=y,w=w,h=h,style=f"text;strokeColor=none;fillColor=none;fontSize={size};fontColor={color};align={align};verticalAlign={valign};"+("fontStyle=1;" if bold else ""),val=val)
    def edge(s,a,b,label="",color="#5b6b7b",width=2,dashed=False,arrow="none",start="none",curved=False,ex=None,size=16,lcolor=None,pts=None,style=""):
        i=s._id(); st=(f"endArrow={arrow};startArrow={start};html=1;strokeColor={color};strokeWidth={width};fontSize={size};fontColor={lcolor or color};fontStyle=1;labelBackgroundColor=#FFFFFF;"
            +("dashed=1;dashPattern=10 6;" if dashed else "")+("curved=1;" if curved else "")+style)
        g='<mxGeometry relative="1" as="geometry">'+(('<Array as="points">'+"".join(f'<mxPoint x="{x}" y="{y}"/>' for x,y in pts)+'</Array>') if pts else "")+'</mxGeometry>'
        s._add(layer=1,x=f'<mxCell id="{i}" value="{escape(label)}" style="{st}" edge="1" parent="1" source="{a}" target="{b}">{g}</mxCell>'); return i
    def line(s,x1,y1,x2,y2,color="#5b6b7b",width=2,dashed=False,arrow="none",start="none",label="",size=16,style=""):
        i=s._id(); st=style+(f"endArrow={arrow};startArrow={start};html=1;strokeColor={color};strokeWidth={width};fontSize={size};fontColor={color};fontStyle=1;labelBackgroundColor=#FFFFFF;"+("dashed=1;dashPattern=10 6;" if dashed else ""))
        s._add(layer=1,x=f'<mxCell id="{i}" value="{escape(label)}" style="{st}" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="{x1}" y="{y1}" as="sourcePoint"/><mxPoint x="{x2}" y="{y2}" as="targetPoint"/></mxGeometry></mxCell>'); return i
    def xml(s):
        return ('<mxfile><diagram name="p">'
          f'<mxGraphModel dx="0" dy="0" grid="0" page="1" pageWidth="{s.w}" pageHeight="{s.h}" background="#FFFFFF"><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
          +"".join(x for _,x in sorted(s.c,key=lambda t:t[0]))+"</root></mxGraphModel></diagram></mxfile>")
    def save(s,name):
        open(f"src/{name}.drawio","w").write(s.xml())
