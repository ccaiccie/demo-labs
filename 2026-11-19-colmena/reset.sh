#!/usr/bin/env bash
# Resets ONLY this lab to its starting state: fresh nodes from the base image, starting data files.
# Careful: removes hive.nix changes, secrets/ and the local git history of this folder copy.
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
  "dns1": { "tcp": [], "udp": [] },
  "monitor1": { "tcp": [9090], "udp": [] }
}
J
nodes/up.sh
