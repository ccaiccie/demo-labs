import json, subprocess, sys, os, concurrent.futures as cf
from pathlib import Path
import numpy as np, soundfile as sf
B=Path(r"C:\Users\superuser\antigravity-build"); C=B/"clips"; R=B/"render"; R.mkdir(exist_ok=True); NZ=B/"tts_norm"; NZ.mkdir(exist_ok=True)
DEMO=r"C:\Users\superuser\ag-lab\demo-pipeline\out\demo.mp4"
TARGET=-18.0
segs=json.loads((B/"segments.json").read_text(encoding="utf-8")); dur=json.load(open(B/"tts_durations.json"))
def active_rms(x,sr):
    w=int(0.05*sr); n=len(x)//w
    if n==0: return -99
    f=x[:n*w].reshape(n,w); r=np.sqrt((f**2).mean(1)+1e-12); db=20*np.log10(r)
    a=f[db>-40]
    return 20*np.log10(np.sqrt((a**2).mean())+1e-12) if len(a) else -99
def norm(j):
    o=NZ/f"{j['id']}.wav"
    x,sr=sf.read(B/"tts"/f"{j['id']}.wav",dtype="float32")
    if x.ndim>1: x=x.mean(1)
    g=TARGET-active_rms(x,sr); y=np.clip(x*10**(g/20),-0.99,0.99); sf.write(o,y,sr); return g
# masks: (clip, x0,y0,x1,y1, t0,t1, mode)
MASKS=[("c03-settings",355,848,592,938,0,9999,"fill"),("c14-quotas-wrapup",355,848,592,938,0,9999,"fill"),
       ("c06-verify",1525,835,1920,1032,268,9999,"blur"),("c10-swarm",0,0,960,536,74,121,"blur")]
def plan(j):
    N=dur.get(j['id'],0.0); V=j['b']-j['a']; sp=1.0
    if j['clip']=="DEMO": return V,1.0,V
    if j['clip'].startswith("CARD:"): return max(3.0,N+0.4),1.0,V
    if V>N+3: sp=min(V/(N+1.5),1.5)
    L=max(V/sp,N+0.3); return L,sp,V
ENC=["-c:v","libx264","-preset","veryfast","-crf","24","-pix_fmt","yuv420p","-r","30","-g","60","-threads","4",
     "-c:a","aac","-b:a","160k","-ar","48000","-ac","2","-video_track_timescale","15360"]
def render(i,j):
    out=R/f"{i:03d}_{j['id']}.mp4"
    L,sp,V=plan(j)
    if out.exists() and out.stat().st_size>1000: return out,L,sp
    if j['clip']=="DEMO":
        x,sr=sf.read(str(B/"demo_audio.wav")) if (B/"demo_audio.wav").exists() else (None,None)
        g=TARGET-active_rms(x.mean(1) if x.ndim>1 else x,sr)
        cmd=["ffmpeg","-v","error","-y","-i",DEMO,"-vf","scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p",
             "-af",f"volume={g:.2f}dB,aresample=48000","-t",f"{L:.3f}"]+ENC+[str(out)]
    else:
        wav=NZ/f"{j['id']}.wav"
        if j['clip'].startswith("CARD:"):
            img=B/"cards"/(j['clip'][5:]+".png")
            cmd=["ffmpeg","-v","error","-y","-loop","1","-framerate","30","-i",str(img),"-i",str(wav),"-filter_complex",
                 f"[0:v]scale=1920:1080,format=yuv420p[v];[1:a]aresample=48000,apad[a]","-map","[v]","-map","[a]","-t",f"{L:.3f}"]+ENC+[str(out)]
        else:
            a=j['a']; vf=[]; lab="[0:v]"; k=0
            for (c,x0,y0,x1,y1,t0,t1,mode) in MASKS:
                if c!=j['clip'] or t1<a or t0>j['b']: continue
                en=f"between(t,{max(0,t0-a):.2f},{t1-a:.2f})"
                if mode=="fill":
                    vf.append(f"{lab}drawbox=x={x0}:y={y0}:w={x1-x0}:h={y1-y0}:color=0x111013@1:t=fill:enable='{en}'[m{k}]")
                else:
                    vf.append(f"{lab}split[b{k}][c{k}];[c{k}]crop={x1-x0}:{y1-y0}:{x0}:{y0},boxblur=30:3[bl{k}];[b{k}][bl{k}]overlay={x0}:{y0}:enable='{en}'[m{k}]")
                lab=f"[m{k}]"; k+=1
            vf.append(f"{lab}setpts=(PTS-STARTPTS)/{sp:.4f},fps=30,pad=1920:1080:0:24:black,tpad=stop_mode=clone:stop_duration=600,format=yuv420p[v]")
            cmd=["ffmpeg","-v","error","-y","-ss",f"{a}","-t",f"{V:.3f}","-i",str(C/(j['clip']+".mkv")),"-i",str(wav),"-filter_complex",
                 ";".join(vf)+";[1:a]aresample=48000,apad[a]","-map","[v]","-map","[a]","-t",f"{L:.3f}"]+ENC+[str(out)]
    subprocess.run(cmd,check=True); return out,L,sp
if __name__=="__main__":
    only=sys.argv[1:]
    jobs=[(i,j) for i,j in enumerate(segs) if not only or j['id'] in only]
    if not (B/"demo_audio.wav").exists(): subprocess.run(["ffmpeg","-v","error","-y","-i",DEMO,"-vn","-ac","1","-ar","48000",str(B/"demo_audio.wav")],check=True)
    for i,j in jobs:
        if j['clip']!="DEMO" and not (NZ/f"{j['id']}.wav").exists(): norm(j)
    with cf.ThreadPoolExecutor(10) as ex:
        res=list(ex.map(lambda p: render(*p), jobs))
    for (i,j),(o,L,sp) in zip(jobs,res): print(j['id'],round(L,2),round(sp,3),flush=True)
