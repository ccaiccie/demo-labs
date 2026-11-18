#!/usr/bin/env python3
"""Tail Suricata eve.json and forward alert events to Shuffle webhook + local case log.
Lab-only helper for 2026-11-18-suricata-shuffle-grafana.
"""
import json, os, sys, time, urllib.request, urllib.error
from pathlib import Path

EVE = Path(os.environ.get("EVE_PATH", "/var/log/suricata/eve.json"))
WEBHOOK = os.environ.get("SHUFFLE_WEBHOOK", "").strip()
CASELOG = os.environ.get("CASELOG_URL", "http://127.0.0.1:8099/case").strip()
POLL = float(os.environ.get("POLL_SECONDS", "1.0"))

def post(url, payload):
    if not url:
        return False, "no-url"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return True, f"{resp.status}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, str(e)

def main():
    print(f"[forwarder] watching {EVE}", flush=True)
    print(f"[forwarder] shuffle webhook set={bool(WEBHOOK)} caselog={CASELOG}", flush=True)
    pos = 0
    if EVE.exists():
        # start at end so we only forward new alerts after start
        pos = EVE.stat().st_size
    while True:
        try:
            if not EVE.exists():
                time.sleep(POLL)
                continue
            size = EVE.stat().st_size
            if size < pos:
                pos = 0  # rotated
            if size == pos:
                time.sleep(POLL)
                continue
            with EVE.open("r", encoding="utf-8", errors="replace") as f:
                f.seek(pos)
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ev = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if ev.get("event_type") != "alert":
                        continue
                    alert = ev.get("alert") or {}
                    payload = {
                        "source": "suricata",
                        "timestamp": ev.get("timestamp"),
                        "src_ip": ev.get("src_ip"),
                        "src_port": ev.get("src_port"),
                        "dest_ip": ev.get("dest_ip"),
                        "dest_port": ev.get("dest_port"),
                        "proto": ev.get("proto"),
                        "signature": alert.get("signature"),
                        "signature_id": alert.get("signature_id"),
                        "category": alert.get("category"),
                        "severity": alert.get("severity"),
                        "action": alert.get("action"),
                        "raw_alert": alert,
                    }
                    ok1, m1 = post(CASELOG, payload)
                    ok2, m2 = (True, "skipped") if not WEBHOOK else post(WEBHOOK, payload)
                    print(
                        f"[alert] sid={payload['signature_id']} sev={payload['severity']} "
                        f"sig={payload['signature']!r} src={payload['src_ip']} "
                        f"caselog={m1} shuffle={m2}",
                        flush=True,
                    )
                pos = f.tell()
        except KeyboardInterrupt:
            print("[forwarder] stop", flush=True)
            return 0
        except Exception as e:
            print(f"[forwarder] error: {e}", flush=True)
            time.sleep(2)

if __name__ == "__main__":
    sys.exit(main() or 0)
