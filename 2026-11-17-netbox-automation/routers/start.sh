#!/bin/sh
# Lab router start-up for the official FRRouting image.
# 1. Remove the IPv4 address Docker put on the data interfaces, so every
#    interface address comes from NetBox through Ansible (like a new router).
# 2. Turn on ospfd and use the single integrated frr.conf.
# 3. Hand over to the image's normal start command (watchfrr + daemons).
set -e
for dev in $(ls /sys/class/net); do
  [ "$dev" = lo ] && continue
  ip -4 addr flush dev "$dev"
done
sed -i 's/^ospfd=no/ospfd=yes/' /etc/frr/daemons
echo 'service integrated-vtysh-config' > /etc/frr/vtysh.conf
[ -f /etc/frr/frr.conf ] || printf 'hostname %s\n' "$(hostname)" > /etc/frr/frr.conf
chown frr:frr /etc/frr/frr.conf /etc/frr/vtysh.conf
exec /sbin/tini -- /usr/lib/frr/docker-start
