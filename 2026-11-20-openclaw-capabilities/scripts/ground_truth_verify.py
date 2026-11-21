#!/usr/bin/env python3
"""Independent ground-truth verifier for network_syslog.log."""
import collections
import json
import re
import sys
from pathlib import Path

log_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("workspace/network_syslog.log")
lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]

report = {
    "total_events": len(lines),
    "by_severity": dict(collections.Counter(ln.split()[2] for ln in lines)),
    "by_device": dict(collections.Counter(ln.split()[1] for ln in lines)),
    "ssh_auth_fail_by_src": dict(
        collections.Counter(
            re.search(r"src=(\S+)", ln).group(1)
            for ln in lines
            if "SSH_AUTH_FAIL" in ln and re.search(r"src=(\S+)", ln)
        )
    ),
}
print(json.dumps(report, indent=2))
