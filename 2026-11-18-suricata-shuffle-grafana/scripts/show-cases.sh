#!/usr/bin/env bash
# Show the most recent entries in the local case log
set -euo pipefail
curl -s http://127.0.0.1:8099/cases | python3 -c '
import sys, json
d = json.load(sys.stdin)
print("Cases stored: %d" % d["count"])
for c in d["cases"][-8:]:
    print("sev %s  %-48s  %s -> %s:%s" % (c.get("severity"), str(c.get("signature"))[:48], c.get("src_ip"), c.get("dest_ip"), c.get("dest_port")))
'
