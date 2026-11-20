import json, subprocess
from pathlib import Path
import numpy as np, soundfile as sf
B=Path(r"C:\Users\superuser\antigravity-build")
segs=json.loads((B/"segments.json").read_text(encoding="utf-8"))
files=sorted((B/"render").glob("*.mp4"))
t=0; ch=[]; starts={}
for j,f in zip(segs,files):
    assert j['id'] in f.name
    d=float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",str(f)]).decode())
    starts[j['id']]=t
    if j.get('chapter'): ch.append((t,j['chapter']))
    t+=d
def fmt(s): s=int(s); h,m=divmod(s,3600); m,s=divmod(m,60); return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
json.dump({"chapters":[[a,b] for a,b in ch],"starts":starts,"total":t},open(B/"chapters.json","w"),indent=1)
for a,b in ch: print(fmt(a),b)
print("TOTAL",t)
subprocess.run(["ffmpeg","-v","error","-y","-i",str(B/"final/2026-11-19-antigravity.mp4"),"-vn","-ac","1","-ar","48000",str(B/"final_audio.wav")],check=True)
x,sr=sf.read(str(B/"final_audio.wav"),dtype="float32")
w=int(0.05*sr); res=[]
for m in range(int(np.ceil(len(x)/sr/60))):
    seg=x[m*60*sr:(m+1)*60*sr]; n=len(seg)//w
    if n==0: continue
    f=seg[:n*w].reshape(n,w); db=20*np.log10(np.sqrt((f**2).mean(1))+1e-12); a=f[db>-40]
    act=len(a)*0.05
    if act<5: res.append((m,act,None)); continue
    res.append((m,act,20*np.log10(np.sqrt((a**2).mean()))))
v=[r[2] for r in res if r[2] is not None]
for r in res: print("min",r[0],round(r[1],1),None if r[2] is None else round(r[2],2))
print("RMS min %.2f max %.2f spread %.2f over %d minutes"%(min(v),max(v),max(v)-min(v),len(v)))
