import sys, time
sys.path.insert(0, "/root/ftd-automation")
from demo import ftd_cli
cmds = sys.argv[1:]
print("\x1b[1;36m$ ssh admin@192.168.100.11   (FTD1 CLI)\x1b[0m"); sys.stdout.flush(); time.sleep(1)
for c in cmds:
    out = ftd_cli("192.168.100.11", [c], wait=int(__import__("os").environ.get("FTDWAIT","6")))
    lines = [l for l in out.replace("\r", "").split("\n")]
    # drop the echoed command line, print typed command then output
    sys.stdout.write("> ");
    for ch in c: sys.stdout.write(ch); sys.stdout.flush(); time.sleep(0.04)
    print(); body = [l for l in lines if l.strip() != c.strip() and l.strip() != ">"]
    print("\n".join(body).strip("\n")); print(); sys.stdout.flush(); time.sleep(3)
