#!/usr/bin/env bash
# Compact summary of Suricata alerts in eve.json (count per signature)
set -euo pipefail
docker exec ids-suricata cat /var/log/suricata/eve.json 2>/dev/null | python3 -c '
import sys, json, collections
alerts = []
for line in sys.stdin:
    try: e = json.loads(line)
    except Exception: continue
    if e.get("event_type") == "alert": alerts.append(e)
c = collections.Counter((a["alert"]["signature_id"], a["alert"]["signature"]) for a in alerts)
print(f"Total alerts: {len(alerts)}")
print("%8s  %5s  %s" % ("SID", "COUNT", "SIGNATURE"))
for (sid, sig), n in c.most_common():
    print(f"{sid:>8}  {n:>5}  {sig[:60]}")
'
