#!/bin/bash
# lab NODE "cmd1" "cmd2" ...  -> log in to an Alpine host console in the fmc-ftd-gui lab and run commands
node=$1; shift
args=()
for c in "$@"; do args+=("$c" "@6"); done
cd ~/cmltools && python3 con.py fmc-ftd-gui "$node" "" cisco @2 cisco @3 "${args[@]}" 2>&1 \
 | tr -d '\r' | sed -e 's/\x1b\[[0-9;]*[a-zA-Z]//g' \
 | grep -v -E 'consoles>|Connecting to console|Connected to CML|Escape character|login:|^Password:|Welcome to Alpine|Alpine Wiki|information about admin|wiki.alpinelinux|setup-alpine|editing /etc/motd|Kernel [0-9]|:~\$ cisco$|cisco: not found|^[A-Z0-9-]+:~\$ *$|^$|Login incorrect|Warning|\*\*'
echo
