"""Right-hand side panel for setup scenes: 9-step progress bar + topology mini-map."""
import os, sys, hashlib, subprocess
from PIL import Image, ImageDraw, ImageFont
HERE=os.path.dirname(os.path.abspath(__file__)); DIO=os.path.join(HERE,"..")
sys.path.insert(0,DIO)
PW,PH=450,790; BG=(13,17,23)
R="/usr/share/fonts/truetype/roboto/unhinted/RobotoTTF/Roboto-"
FB=lambda n: ImageFont.truetype(R+"Bold.ttf",n); FR=lambda n: ImageFont.truetype(R+"Regular.ttf",n)
NAMES={0:"Before the build: reset and list",1:"Create the root CA",2:"Render the topology, start the controllers",3:"Manager first-time settings",
 4:"Onboard Validator and Controller",5:"Upload the WAN edge list",6:"Build the configuration group",7:"Deploy and create the routers",
 8:"Wait for the routers to join",9:"Centralized policy"}
BLUE=(4,159,217); GREEN=(39,174,96); AMBER=(241,196,15); GREY=(70,78,90); TXT=(235,240,245); SUB=(150,160,175)
def mapimg(tags):
    import smap
    cwd=os.getcwd(); os.chdir(DIO)
    try: p=smap.render(list(tags))
    finally: os.chdir(cwd)
    return os.path.join(DIO,p)
def wrap(d,t,f,w):
    out=[]; cur=""
    for wd in t.split():
        if d.textlength((cur+" "+wd).strip(),font=f)<=w: cur=(cur+" "+wd).strip()
        else: out.append(cur); cur=wd
    return out+[cur]
def panel(tags,prog):
    key=hashlib.md5(repr((sorted(tags),prog)).encode()).hexdigest()[:12]
    out=os.path.join(HERE,"panels",key+".png")
    if os.path.exists(out): return out
    os.makedirs(os.path.dirname(out),exist_ok=True)
    im=Image.new("RGB",(PW,PH),BG); d=ImageDraw.Draw(im)
    d.line([(0,0),(0,PH)],fill=(40,48,60),width=2)
    d.text((22,10),"THE NINE BUILD STEPS",font=FB(15),fill=SUB)
    mode=prog[0]
    r=17; gap=(PW-44-2*r)/8
    for n in range(1,10):
        cx=22+r+(n-1)*gap; cy=52
        if mode=="run":
            cur=prog[1]
            if n<cur: fill,ol,tc=GREEN,GREEN,(255,255,255)
            elif n==cur: fill,ol,tc=BLUE,(255,255,255),(255,255,255)
            else: fill,ol,tc=BG,GREY,(110,118,129)
        else:
            if n in prog[1]: fill,ol,tc=AMBER,AMBER,(20,20,20)
            else: fill,ol,tc=BG,GREY,(110,118,129)
        if n<9:
            nx=cx+gap
            lc=GREEN if mode=="run" and n<prog[1] else GREY
            d.line([(cx+r,cy),(nx-r,cy)],fill=lc,width=3)
        d.ellipse([cx-r,cy-r,cx+r,cy+r],fill=fill,outline=ol,width=3)
        if mode=="run" and n<prog[1]:
            d.line([(cx-7,cy),(cx-2,cy+6),(cx+8,cy-6)],fill=(255,255,255),width=3)
        else:
            d.text((cx,cy),str(n),font=FB(17),fill=tc,anchor="mm")
    if mode=="run":
        n=prog[1]; head=f"Step {n} of 9 · running" if n else "Getting ready"
        d.text((22,84),head,font=FB(15),fill=BLUE if n else SUB)
        cap=NAMES[n]
    else:
        d.text((22,84),"Code walkthrough · used in" if prog[1] else "Code walkthrough",font=FB(15),fill=AMBER)
        cap=prog[2]
    for i,l in enumerate(wrap(d,cap,FB(21),PW-44)[:2]):
        d.text((22,106+i*27),l,font=FB(21),fill=TXT)
    # map card
    m=Image.open(mapimg(tags)).convert("RGB")
    mw=PW-24; mh=round(m.height*mw/m.width)
    if 166+mh>PH-8: mh=PH-8-166; mw=round(m.width*mh/m.height)
    m=m.resize((mw,mh),Image.LANCZOS)
    x0=(PW-mw)//2; y0=166
    card=Image.new("RGB",(mw+8,mh+8),(255,255,255))
    msk=Image.new("L",card.size,0); ImageDraw.Draw(msk).rounded_rectangle([0,0,card.width-1,card.height-1],radius=10,fill=255)
    im.paste(card,(x0-4,y0-4),msk); im.paste(m,(x0,y0))
    im.save(out); return out
if __name__=="__main__":
    print(panel(["edge","tun"],("run",8)))
    print(panel(["gw","inet"],("use",[2],"Day-zero templates: rendered in step 2")))
