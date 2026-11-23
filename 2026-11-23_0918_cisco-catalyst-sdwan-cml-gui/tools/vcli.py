#!/usr/bin/env python3
"""vcli.py TARGET "cmd1" "cmd2" ...

Run read-only show commands on an SD-WAN controller or edge by SSH-ing to the
SD-WAN Manager and hopping from there ("request execute vpn 0 ssh ...").
TARGET is a VPN 0 address (e.g. 172.16.0.101) or "mgr" for the Manager itself.

Environment:
  MGR_PASSWORD  admin password (required)
  MGR_HOST      Manager address, default 192.168.122.50
  JUMP_HOST     optional SSH jump host that can reach the Manager
Note: the hop uses the same password; if a device has a different admin
password, use the Manager API (dataservice/device/config?deviceId=...) instead.
"""
import os, sys, time
import pexpect

pw = os.environ["MGR_PASSWORD"]
mgr = os.environ.get("MGR_HOST", "192.168.122.50")
jump = os.environ.get("JUMP_HOST", "")
tgt, cmds = sys.argv[1], sys.argv[2:]

ssh = "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
ssh += (f"-J {jump} " if jump else "") + f"admin@{mgr}"
c = pexpect.spawn(ssh, encoding="utf-8", timeout=60)
c.expect("assword:"); c.sendline(pw); c.expect(r"#\s*$")
c.sendline("paginate false"); c.expect(r"#\s*$")
if tgt != "mgr":
    c.sendline(f"request execute vpn 0 ssh -o StrictHostKeyChecking=no admin@{tgt}")
    c.expect(["assword: ", pexpect.TIMEOUT]); time.sleep(2); c.sendline(pw); c.expect(r"#\s*$")
    c.sendline("paginate false"); c.expect(r"#\s*$")
for cmd in cmds:
    c.sendline(cmd); c.expect(r"\n[\w\-]+#\s*$", timeout=90)
    print(">>>", cmd); print(c.before)
c.sendline("exit"); c.close()
