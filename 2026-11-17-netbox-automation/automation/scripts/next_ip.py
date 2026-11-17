"""Allocate the next free IP in a NetBox prefix and assign it to a device interface.

Usage: python scripts/next_ip.py <prefix> <device> <interface> [description]
"""
import os, sys
import pynetbox

prefix, device, ifname = sys.argv[1:4]
desc = sys.argv[4] if len(sys.argv) > 4 else ""
nb = pynetbox.api(os.environ["NETBOX_API"], token=os.environ["NETBOX_TOKEN"])

pfx = nb.ipam.prefixes.get(prefix=prefix)
iface = nb.dcim.interfaces.get(device=device, name=ifname)
print(f"Prefix {pfx.prefix} (id {pfx.id}), interface {device} {iface.name} (id {iface.id})")

ip = pfx.available_ips.create({
    "description": desc,
    "assigned_object_type": "dcim.interface",
    "assigned_object_id": iface.id,
})
print(f"Allocated {ip.address} -> {device} {iface.name}")
