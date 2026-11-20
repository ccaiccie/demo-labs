import sys, subprocess, json, re, os, glob
from pathlib import Path
from PIL import Image
import winocr
B=Path(r"C:\Users\superuser\antigravity-build"); C=B/"clips"; S=B/"scan"; S.mkdir(exist_ok=True)
EM=re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"); KW=re.compile(r"gmail|yahoo|outlook\.com|notification|IP address:|2600:|password|api[_ ]?key|sk-|token", re.I)
out={}
for mk in sorted(C.glob("*.mkv")):
    name=mk.stem; d=S/name; d.mkdir(exist_ok=True)
    if not list(d.glob("*.png")):
        subprocess.run(["ffmpeg","-v","error","-i",str(mk),"-vf","fps=1/4","-q:v","2",str(d/"f%05d.png")],check=True)
    res=[]
    for i,p in enumerate(sorted(d.glob("f*.png"))):
        t=i*4+2
        im=Image.open(p).convert("RGB"); im=im.resize((im.width*2,im.height*2))
        r=winocr.recognize_pil_sync(im,"en-US")
        txt=[ln["text"] for ln in r["lines"]]
        for ln in r["lines"]:
            s=ln["text"]
            if EM.search(s) or KW.search(s):
                ws=ln["words"]; x=min(w["bounding_rect"]["x"] for w in ws)/2; y=min(w["bounding_rect"]["y"] for w in ws)/2
                res.append([t,s,int(x),int(y)])
    out[name]=res; print(name,len(res),flush=True)
    json.dump(out,open(S/"hits.json","w"),indent=0)
print("DONE")
