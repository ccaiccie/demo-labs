import json, sys, re, concurrent.futures
from pathlib import Path
import numpy as np, soundfile as sf
M = Path(r'C:\Users\superuser\Downloads\NewsLessons\tts-remote')
B = Path(__file__).resolve().parent; OUT = B/'tts'; OUT.mkdir(exist_ok=True)
SR=24000; GAP=0.28
K=None
def init():
    global K
    from kokoro_onnx import Kokoro
    import onnxruntime as rt
    o=rt.SessionOptions(); o.intra_op_num_threads=3; o.inter_op_num_threads=1
    K=Kokoro.from_session(rt.InferenceSession(str(M/'kokoro-v1.0.onnx'),sess_options=o,providers=['CPUExecutionProvider']),str(M/'voices-v1.0.bin'))
def sents(t):
    out=[]
    for s in re.split(r'(?<=[.!?])\s+', t.strip()):
        if not s: continue
        # split very long sentences at commas to keep kokoro stable
        while len(s)>380:
            k=s.rfind(', ',0,380); k = k if k>100 else 380
            out.append(s[:k+1]); s=s[k+1:].strip()
        out.append(s)
    return out
def synth(j):
    w=OUT/f"{j['id']}.wav"
    if w.exists(): return j['id']
    ch=[np.zeros(int(0.15*SR),np.float32)]
    for s in sents(j['spoken']):
        a,sr=K.create(s,voice='am_michael',speed=1.0,lang='en-us'); ch.append(a.astype(np.float32)); ch.append(np.zeros(int(GAP*SR),np.float32))
    tmp=OUT/f"{j['id']}.tmp.wav"; sf.write(tmp,np.concatenate(ch),SR); tmp.replace(w); return j['id']
if __name__=='__main__':
    jobs=[j for j in json.loads((B/'segments.json').read_text(encoding='utf-8')) if j['spoken'].strip()]
    with concurrent.futures.ProcessPoolExecutor(max_workers=20,initializer=init) as ex:
        for r in ex.map(synth,jobs): print(r,flush=True)
    d={j['id']: sf.info(str(OUT/(j['id']+'.wav'))).duration for j in jobs}
    json.dump(d, open(B/'tts_durations.json','w'), indent=1); print("TOTAL", sum(d.values())); (OUT/'DONE.txt').write_text('done')
