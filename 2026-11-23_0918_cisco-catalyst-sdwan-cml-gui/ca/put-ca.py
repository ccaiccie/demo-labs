#!/usr/bin/env python3
"""Swap the root CA certificate embedded in each controller's day-0 user-data."""
import re, sys
ca = open("root-ca.crt").read().strip().splitlines()
for f in sys.argv[1:]:
    s = open(f).read()
    s, n = re.subn(r"( *)-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",
                   lambda m: "\n".join(m.group(1) + l for l in ca), s, count=1, flags=re.S)
    open(f, "w").write(s); print(f"{f}: root CA replaced ({n})")
