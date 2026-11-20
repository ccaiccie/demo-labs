import subprocess, re, json
from pathlib import Path
from PIL import Image
import winocr
B=Path(r"C:\Users\superuser\antigravity-build"); d=B/"fscan"; d.mkdir(exist_ok=True)
if not list(d.glob("*.png")):
    subprocess.run(["ffmpeg","-v","error","-i",str(B/"final/2026-11-19-antigravity.mp4"),"-vf","fps=1/3","-q:v","2",str(d/"f%05d.png")],check=True)
EM=re.compile(r"[\w.+-]+@[\w-]+\.[a-z]{2,}",re.I); KW=re.compile(r"ccaiccie@|gmail\.com|yahoo\.com|IP address:|2600:|sk-[A-Za-z0-9]{8}|api[_ ]?key\s*[:=]|Notification Center|Downloads",re.I)
hits=[]
for i,p in enumerate(sorted(d.glob("f*.png"))):
    t=i*3+1.5; im=Image.open(p).convert("RGB"); im=im.resize((im.width*2,im.height*2))
    for ln in winocr.recognize_pil_sync(im,"en-US")["lines"]:
        s=ln["text"]
        if EM.search(s) or KW.search(s): hits.append([t,re.sub(r"[\w.+-]+@","***@",s)])
json.dump(hits,open(B/"fscan_hits.json","w"),indent=0); print("frames",i+1,"hits",len(hits))
for h in hits: print(h)
