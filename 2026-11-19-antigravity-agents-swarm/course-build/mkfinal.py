import json, html
c=json.load(open("chapters.json"))
names={"The slash swarm command: nine agents build a demo-video pipeline":"/swarm: nine agents build a demo-video pipeline",
       "Review, git ignore, and a clean commit":"Review tab, .gitignore and a clean commit"}
def fmt(s): s=int(s); h,m=divmod(s,3600); m,s=divmod(m,60); return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
ch=[(t,names.get(n,n)) for t,n in c["chapters"]]
lines=[f"{fmt(t)} {n}" for t,n in ch]
open("final/chapters.txt","w",encoding="utf-8").write("\n".join(lines)+"\n")
title="Google Antigravity + Gemini 4 Neon Full Course: Agents, Subagents, Orchestrator and /swarm"
assert len(title)<=100 and "<" not in title and ">" not in title
open("final/2026-11-19-antigravity-title.txt","w",encoding="utf-8").write(title+"\n")
desc=f"""A complete hands-on course on Google Antigravity 2.33 with Gemini 4 Neon, recorded live on Windows. We go from first launch to agents, subagents, the Orchestrator and /swarm, and then use Antigravity to build and run a narrated demo-video pipeline like the one behind this channel. Every prompt, wait, failure and fix is real.

What you will learn:
- Onboarding, the interface, projects, Automations and Customizations (plugins, skills, MCP)
- Settings: permissions, models and usage, browser, customization token budget
- Gemini 4 Neon thinking levels (Low, Medium, High, Extra) and when to use each
- Build and verify a Cisco syslog triage tool with Neon High, then fix its severity logic with Neon Low
- Review tab, .gitignore and a clean agent-made git commit
- Orchestrator (Neon) splitting a config-backup auditor across 4 parallel subagents with API contracts and file ownership (74 tests pass)
- /swarm with 9 members (verifier and stall monitor included) building a Docker, Playwright, ffmpeg, Kokoro TTS, loudness check and HTML player pipeline
- A live end-to-end run: Wsl/E_ACCESSDENIED in the sandbox, gdigrab error 5, swarm feedback on the Board, and a working narrated video
- The built-in browser and the browser subagent with URL permissions
- Workspace rules and reusable skills in .agents, and why tests still matter
- How much weekly and five-hour quota the whole session really used
- A practical recipe for making demo videos with Antigravity

Lab files (prompts, code, pipeline, rules and skills):
https://github.com/ccaiccie/demo-labs/tree/main/2026-11-19-antigravity-agents-swarm

Chapters:
{chr(10).join(lines)}

Long agent waits were trimmed and some silent stretches were sped up (at most 1.5x). Account details and a desktop notification were masked. No paid add-ons were used and AI Credit Overages stayed off.

Comprehensive courses: https://learn.techtohire.com
Free daily quiz: https://quiz.techtohire.com
Website: https://www.techtohire.com

#Antigravity #Gemini #AIAgents #NetworkEngineering #DevOps
"""
assert "<" not in desc and ">" not in desc and len(desc)<5000
open("final/2026-11-19-antigravity-desc.txt","w",encoding="utf-8").write(desc)
btn="".join(f'<li><a href="#" data-t="{t:.2f}"><span>{fmt(t)}</span> {html.escape(n)}</a></li>' for t,n in ch)
page=f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{{margin:0;background:#0e1118;color:#e6eaf2;font-family:Segoe UI,Arial,sans-serif}}main{{max-width:1280px;margin:auto;padding:20px}}
h1{{font-size:24px}}video{{width:100%;background:#000;border-radius:8px}}.bar{{margin:12px 0;display:flex;gap:8px;align-items:center}}
button{{background:#1d2433;color:#e6eaf2;border:1px solid #33405a;border-radius:6px;padding:8px 16px;font-size:15px;cursor:pointer}}button.on{{background:#4285f4;border-color:#4285f4}}
ol{{list-style:none;padding:0;columns:2}}li a{{color:#b9c7e6;text-decoration:none;display:block;padding:4px 0}}li a span{{color:#7fb0ff;display:inline-block;width:70px}}li a.cur{{color:#fff;font-weight:600}}
p.links a{{color:#7fb0ff}}</style></head><body><main>
<h1>{html.escape(title)}</h1>
<video id="v" src="2026-11-19-antigravity.mp4" controls preload="metadata"></video>
<div class="bar">Speed: <button data-r="1" class="on">1x</button><button data-r="1.5">1.5x</button><button data-r="2">2x</button></div>
<h2>Chapters</h2><ol id="ch">{btn}</ol>
<p class="links">Lab files: <a href="https://github.com/ccaiccie/demo-labs/tree/main/2026-11-19-antigravity-agents-swarm">github.com/ccaiccie/demo-labs/2026-11-19-antigravity-agents-swarm</a><br>
Courses: <a href="https://learn.techtohire.com">learn.techtohire.com</a> | Quiz: <a href="https://quiz.techtohire.com">quiz.techtohire.com</a> | <a href="https://www.techtohire.com">www.techtohire.com</a></p>
</main><script>
const v=document.getElementById('v');let rate=1;
document.querySelectorAll('button[data-r]').forEach(b=>b.onclick=()=>{{rate=+b.dataset.r;v.playbackRate=rate;document.querySelectorAll('button[data-r]').forEach(x=>x.classList.toggle('on',x===b));}});
v.addEventListener('play',()=>v.playbackRate=rate);v.addEventListener('loadedmetadata',()=>v.playbackRate=rate);
const links=[...document.querySelectorAll('#ch a')];
links.forEach(a=>a.onclick=e=>{{e.preventDefault();v.currentTime=+a.dataset.t;v.play();}});
v.addEventListener('timeupdate',()=>{{let c=null;links.forEach(a=>{{if(+a.dataset.t<=v.currentTime+0.2)c=a;}});links.forEach(a=>a.classList.toggle('cur',a===c));}});
</script></body></html>"""
open("final/2026-11-19-antigravity.html","w",encoding="utf-8").write(page)
print(len(title)); print("\n".join(lines)); print(len(desc))
