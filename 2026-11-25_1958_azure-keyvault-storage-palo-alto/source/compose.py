import json, os, wave, subprocess, re
from PIL import Image, ImageDraw, ImageFont
from lesson import CHAPTERS

from lesson import FULL
B = "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"
R = "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"
fT, fS, fC, fCb = ImageFont.truetype(B, 34), ImageFont.truetype(R, 22), ImageFont.truetype(R, 15), ImageFont.truetype(B, 15)
steps = json.load(open("steps.json"))
os.makedirs("frames", exist_ok=True)
PAD_BEFORE, PAD_AFTER = 0.35, 0.55


def frame(i, st):
    img = Image.new("RGB", (1920, 1080), "white")
    dr = ImageDraw.Draw(img)
    dr.rectangle([0, 0, 1920, 78], fill="#1B1A19")
    dr.rectangle([0, 74, 1920, 78], fill="#FA582D")
    ch = st["ch"]
    dr.text((30, 16), FULL[ch], font=fT, fill="white")
    sub = "Key Vault and Storage behind a Palo Alto firewall"
    w = dr.textlength(sub, font=fS)
    dr.text((1890 - w, 26), sub, font=fS, fill="#C8C6C4")
    d = Image.open("steps/%s.png" % st["name"]).convert("RGB")
    sc = min(1900 / d.width, 902 / d.height)
    d = d.resize((round(d.width * sc), round(d.height * sc)), Image.LANCZOS)
    img.paste(d, ((1920 - d.width) // 2, 82))
    # progress bar
    y0 = 992
    dr.rectangle([0, y0, 1920, 1080], fill="#F3F2F1")
    n = len(CHAPTERS)
    cw = (1920 - 40) / n
    for k, name in enumerate(CHAPTERS):
        x0 = 20 + k * cw
        col = "#FA582D" if k == ch else ("#605E5C" if k < ch else "#D2D0CE")
        tc = "white" if k <= ch else "#323130"
        dr.rounded_rectangle([x0 + 3, y0 + 22, x0 + cw - 3, y0 + 66], 8, fill=col)
        f = fCb if k == ch else fC
        tw = dr.textlength(name, font=f)
        dr.text((x0 + (cw - tw) / 2, y0 + 33), name, font=f, fill=tc)
    img.save("frames/%s.png" % st["name"])


def dur(name):
    w = wave.open("audio/%s.wav" % name)
    return w.getnframes() / w.getframerate()


def srt_time(t):
    h, r = divmod(t, 3600); m, s = divmod(r, 60)
    return "%02d:%02d:%02d,%03d" % (h, m, int(s), round((s - int(s)) * 1000) % 1000)


def chunks(text):
    sents = re.split(r"(?<=[.!?:;])\s+", re.sub(r"\s+", " ", text).strip())
    out = []
    for s in sents:
        words = s.split()
        while len(words) > 16:  # keep captions short
            cut = 14
            out.append(" ".join(words[:cut])); words = words[cut:]
        if words:
            out.append(" ".join(words))
    return out


if __name__ == "__main__":
    for i, st in enumerate(steps):
        frame(i, st)
    t = 0.0
    srt, idx, concat, chap = [], 1, [], []
    last_ch = -1
    for st in steps:
        a = dur(st["name"])
        seg = PAD_BEFORE + a + PAD_AFTER
        if st["ch"] != last_ch:
            chap.append((t, FULL[st["ch"]])); last_ch = st["ch"]
        cs = chunks(st["say"])
        total = sum(len(c) for c in cs)
        ct = t + PAD_BEFORE
        for c in cs:
            dd = a * len(c) / total
            srt.append("%d\n%s --> %s\n%s\n" % (idx, srt_time(ct), srt_time(ct + dd - 0.05), c)); idx += 1
            ct += dd
        concat.append((st["name"], seg, a))
        t += seg
    open("final.srt", "w").write("\n".join(srt))
    open("chapters.txt", "w").write("\n".join("%d:%02d %s" % (int(x // 60), int(x % 60), n) for x, n in chap))
    # audio: pad each clip, concat
    with open("alist.txt", "w") as f:
        for name, seg, a in concat:
            f.write("file 'apad/%s.wav'\n" % name)
    os.makedirs("apad", exist_ok=True)
    for name, seg, a in concat:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", "audio/%s.wav" % name, "-af",
                        "adelay=%d,apad=whole_dur=%.3f" % (PAD_BEFORE * 1000, seg), "-ar", "48000", "-ac", "1", "apad/%s.wav" % name], check=True)
    with open("vlist.txt", "w") as f:
        for name, seg, a in concat:
            f.write("file 'frames/%s.png'\nduration %.3f\n" % (name, seg))
        f.write("file 'frames/%s.png'\n" % concat[-1][0])
    print("total", t / 60, "min")
