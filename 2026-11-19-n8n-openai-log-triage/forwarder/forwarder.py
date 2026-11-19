"""Tiny syslog-to-webhook forwarder: UDP 5514 in, HTTP POST to n8n out."""
import json, os, re, socket, urllib.request

URL = os.environ.get("N8N_WEBHOOK", "http://n8n:5678/webhook/netlog")
PRI = re.compile(r"^<\d+>")

def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("0.0.0.0", 5514))
    print(f"syslog-forwarder: UDP 5514 -> {URL}", flush=True)
    while True:
        data, addr = s.recvfrom(8192)
        line = PRI.sub("", data.decode(errors="replace").strip())
        # RFC 3164 header: "Nov 19 10:01:02 core-sw1 message..." -> pull out the hostname
        m = re.match(r"^\w{3}\s+\d+\s+[\d:]+\s+(\S+)\s+(.*)$", line)
        host, msg = (m.group(1), m.group(2)) if m else (addr[0], line)
        body = json.dumps({"host": host, "message": msg, "via": "syslog"}).encode()
        print(f"<- syslog from {addr[0]}  host={host}  {msg[:100]}", flush=True)
        try:
            req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                print("-> n8n replied:", r.read().decode()[:400], flush=True)
        except Exception as e:
            print("-> n8n error:", e, flush=True)

if __name__ == "__main__":
    main()
