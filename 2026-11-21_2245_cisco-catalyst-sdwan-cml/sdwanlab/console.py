"""Run commands on any lab node through the CML console server.

CML has a built-in terminal server: SSH to the CML host with your CML
login and you get a "consoles>" prompt. From there

    open /<lab title>/<node label>/0

attaches you to that node's serial console, exactly like plugging a
console cable into a real router. This works even when the node has no
management IP, which is why we use it to test from the hosts.
"""
from __future__ import annotations

import re
import time

import paramiko


class Console:
    PROMPT = re.compile(rb"([>#$]|consoles>)\s*$")

    def __init__(self, host: str, user: str, password: str):
        self.host, self.user, self.password = host, user, password

    def _read_until(self, ch, patterns, timeout=30) -> str:
        buf, end = b"", time.time() + timeout
        while time.time() < end:
            if ch.recv_ready():
                buf += ch.recv(65535)
                text = buf.decode(errors="ignore")
                for p in patterns:
                    if re.search(p, text[-300:]):
                        return text
            else:
                time.sleep(0.2)
        return buf.decode(errors="ignore")

    def run(self, lab: str, node: str, commands: list[str], login: tuple[str, str] | None = None,
            timeout: int = 60, prompt: str = r"[#$>]\s*$", enable: bool = False) -> str:
        cli = paramiko.SSHClient()
        cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        cli.connect(self.host, username=self.user, password=self.password,
                    look_for_keys=False, allow_agent=False, timeout=20)
        ch = cli.invoke_shell(width=250, height=1000)
        try:
            self._read_until(ch, [r"consoles>\s*$"], 20)
            ch.send(f"open /{lab}/{node}/0\r")
            time.sleep(1)
            ch.send("\r")
            out = self._read_until(ch, [r"[Ll]ogin:\s*$", r"[Uu]sername:\s*$", r"[Pp]assword:\s*$", prompt], 20)
            if login and re.search(r"([Ll]ogin|[Uu]sername):\s*$", out[-200:]):
                ch.send(login[0] + "\r")
                self._read_until(ch, [r"[Pp]assword:\s*$"], 10)
                ch.send(login[1] + "\r")
                self._read_until(ch, [prompt], 20)
            # IOS-XE edges drop us at "Router>" (user EXEC) when the console
            # line has no login. 'enable' lifts us to "Router#" so show
            # commands like 'show sdwan ...' are allowed.
            if enable:
                ch.send("\r")
                tail = self._read_until(ch, [r"[#>]\s*$"], 10)[-80:]
                if re.search(r"[^s]>\s*$", tail):           # '>' but not 'consoles>'
                    ch.send("enable\r")
                    t = self._read_until(ch, [r"#\s*$", r"[Pp]assword:\s*$"], 10)
                    if re.search(r"[Pp]assword:\s*$", t[-50:]) and login:
                        ch.send(login[1] + "\r")
                        self._read_until(ch, [r"#\s*$"], 10)
            result = []
            for cmd in commands:
                ch.send(cmd + "\r")
                result.append(self._read_until(ch, [prompt], timeout))
            return "".join(result)
        finally:
            ch.close()
            cli.close()
