#!/usr/bin/env python3
"""Bootstrap cisco-core1 (CSR1000v generic_vm) over QEMU serial console (TCP 5000).

Idempotent: waits until vrnetlab finishes releasing the serial console,
dismisses the IOS-XE initial configuration dialog if shown, pushes
clab/configs/cisco-core1.cfg, generates a 2048-bit RSA key for SSHv2,
and saves the running config.
"""
import argparse
import os
import socket
import sys
import time


def read_all(sock: socket.socket, wait: float = 0.5) -> str:
    sock.settimeout(wait)
    chunks = []
    while True:
        try:
            data = sock.recv(4096)
            if not data:
                break
            chunks.append(data.decode("utf-8", errors="ignore"))
            sock.settimeout(0.25)
        except socket.timeout:
            break
    return "".join(chunks)


def send_cmd(sock: socket.socket, cmd: str, wait: float = 0.6) -> str:
    sock.sendall((cmd + "\r\n").encode("utf-8"))
    return read_all(sock, wait=wait)


def wait_for_console(host: str, port: int, timeout: int = 300) -> socket.socket:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            s = socket.create_connection((host, port), timeout=5)
            # Nudge console and see if IOS-XE responds (vrnetlab holds port until ready)
            s.sendall(b"\r\n")
            out = read_all(s, wait=2.0)
            if any(
                marker in out
                for marker in (
                    "Router>",
                    "Router#",
                    "cisco-core1>",
                    "cisco-core1#",
                    "Username:",
                    "Password:",
                    "initial configuration dialog",
                    "Press RETURN",
                    "autoinstall",
                )
            ):
                print(f"[bootstrap] Console ready on {host}:{port}")
                return s
            s.close()
        except OSError:
            pass
        time.sleep(5)
    raise RuntimeError(f"Timed out waiting for IOS-XE serial console on {host}:{port}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="172.30.30.13")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument(
        "--config",
        default=os.path.join(os.path.dirname(__file__), "configs", "cisco-core1.cfg"),
    )
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()

    with open(args.config, "r", encoding="utf-8") as fh:
        cfg_lines = [
            line.rstrip()
            for line in fh
            if line.strip() and not line.strip().startswith("!")
        ]

    sock = wait_for_console(args.host, args.port, timeout=args.timeout)
    try:
        out = send_cmd(sock, "", wait=1.5)
        for _ in range(10):
            if "initial configuration dialog" in out:
                print("[bootstrap] Dismissing initial configuration dialog...")
                out = send_cmd(sock, "no", wait=3.0)
            elif "terminate autoinstall" in out:
                out = send_cmd(sock, "yes", wait=3.0)
            elif "Press RETURN" in out:
                out = send_cmd(sock, "", wait=2.0)
            elif "Username:" in out:
                out = send_cmd(sock, "admin", wait=1.0)
            elif "Password:" in out:
                out = send_cmd(sock, "LabDemo123!", wait=1.0)
            elif out.rstrip().endswith(">"):
                out = send_cmd(sock, "enable", wait=1.0)
                if "Password:" in out:
                    out = send_cmd(sock, "LabDemo123!", wait=1.0)
            elif out.rstrip().endswith("#"):
                break
            else:
                out = send_cmd(sock, "", wait=2.0)

        if not out.rstrip().endswith("#"):
            print(f"[bootstrap] Warning: prompt was:\n{out[-300:]}")

        send_cmd(sock, "terminal length 0", wait=0.5)
        send_cmd(sock, "configure terminal", wait=0.8)

        print(f"[bootstrap] Applying {len(cfg_lines)} config lines...")
        for line in cfg_lines:
            if line.strip().lower() == "end":
                continue
            resp = send_cmd(sock, line, wait=0.35)
            if "% Invalid" in resp or "% Incomplete" in resp:
                print(f"[bootstrap] CLI error on '{line}': {resp.strip()}")

        print("[bootstrap] Generating RSA 2048 key for SSHv2...")
        key_out = send_cmd(sock, "crypto key generate rsa modulus 2048", wait=4.0)
        if "replace them" in key_out.lower():
            send_cmd(sock, "no", wait=1.0)
        else:
            time.sleep(3.0)
            read_all(sock, wait=1.0)

        send_cmd(sock, "end", wait=0.8)
        print("[bootstrap] Saving config (write memory)...")
        wr_out = send_cmd(sock, "write memory", wait=5.0)
        print(wr_out.strip()[-200:])

        ip_out = send_cmd(sock, "show ip interface brief", wait=1.5)
        print("[bootstrap] Interfaces:\n" + ip_out.strip())
    finally:
        sock.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
