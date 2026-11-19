#!/usr/bin/env bash
# Resets ONLY this lab: fresh nodes from the base image, data files as at the end of the video (no AI-added records).
# Careful: deletes secrets/ and keys/known_hosts, and recreates the three lab containers.
set -u
cd "$(dirname "$0")"
pkill -f changebot.py 2>/dev/null
nodes/down.sh
rm -rf secrets/* keys/known_hosts result
cat > data/dns-records.json <<'J'
{
  "router1": "10.88.0.11",
  "dns1": "10.88.0.12",
  "monitor1": "10.88.0.13"
}
J
cat > data/firewall.json <<'J'
{
  "router1": { "tcp": [], "udp": [] },
  "dns1": { "tcp": [53], "udp": [53] },
  "monitor1": { "tcp": [9090], "udp": [] }
}
J
nodes/up.sh
