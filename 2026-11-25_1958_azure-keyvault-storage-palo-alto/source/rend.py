import os, sys, subprocess, shutil
from diagrams import D
def render_states(states, outdir):
    """states: list of (name, diagram_key, show, hl)"""
    src = outdir + "_src"; shutil.rmtree(src, ignore_errors=True); os.makedirs(src); os.makedirs(outdir, exist_ok=True)
    for name, key, show, hl in states:
        open(f"{src}/{name}.drawio", "w").write(D[key].xml(show, hl))
    subprocess.run(["xvfb-run", "-a", "drawio", "-x", "-f", "png", "-s", "1", "-b", "0", "-o", outdir + "/", src, "--no-sandbox"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1800)
if __name__ == "__main__":
    keys = sys.argv[1:] or list(D)
    render_states([(k, k, [c[0] for c in D[k].cells], []) for k in keys], "full")
