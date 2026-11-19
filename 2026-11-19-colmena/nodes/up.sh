#!/usr/bin/env bash
# Starts the three lab nodes as NixOS containers running systemd on an internal Docker network.
# No --privileged: systemd gets SYS_ADMIN (to remount its own cgroup namespace read-write)
# and NET_ADMIN (for nftables inside the container's network namespace).
set -euo pipefail
cd "$(dirname "$0")"
IMAGE=colmena-lab/nixos-base:26.05
BIN=$(cat base-system.txt)/sw/bin          # tools from the image's own NixOS closure
BOOT='mount -o remount,rw /sys/fs/cgroup && if [ -e /nix/var/nix/profiles/system/init ]; then exec /nix/var/nix/profiles/system/init; else exec /init; fi'
docker network inspect colmena-lab >/dev/null 2>&1 || \
  docker network create --subnet 10.88.0.0/24 --gateway 10.88.0.1 colmena-lab >/dev/null
node() {  # name ip [extra docker args]
  local name=$1 ip=$2; shift 2
  docker run -d -t --name "$name" --hostname "$name" --network colmena-lab --ip "$ip" \
    --cap-add SYS_ADMIN --cap-add NET_ADMIN --security-opt apparmor=unconfined \
    --cgroupns private --tmpfs /run --tmpfs /tmp --stop-signal SIGRTMIN+3 \
    --restart unless-stopped "$@" --entrypoint "$BIN/sh" "$IMAGE" -c "PATH=$BIN; $BOOT" >/dev/null
  echo "started $name $ip"
}
node router1 10.88.0.11
node dns1 10.88.0.12
node monitor1 10.88.0.13 -p 127.0.0.1:9095:9090
