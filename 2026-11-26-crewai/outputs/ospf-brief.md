# OSPF Lab Brief

## Topology
- Devices: `core-sw1`, `core-sw2`
- Interfaces: `GigabitEthernet0/1`
- Neighbor IDs: `192.0.2.19` (from `core-sw2`)

## What Good Looks Like
- A stable OSPF adjacency between `core-sw1` and `core-sw2` should be in the FULL state, with the neighbor ID `192.0.2.19`.
- Upon a brief link-down on `GigabitEthernet0/1`, the OSPF adjacency should transition to DOWN, then back to FULL (`Loading Done`) upon line protocol recovery.
- A recovered adjacency is considered a transient bounce and should be recorded as such.
- A neighbor that remains DOWN should be treated as a high-severity routing incident.

## How to Judge an OSPF Bounce
- **Transient Bounce**: A brief link-down on `GigabitEthernet0/1` will cause the OSPF adjacency to transition from FULL to DOWN. Upon line protocol recovery, the adjacency should revert to FULL (`Loading Done`). Such a transition is considered a transient bounce and should be recorded as such.
- **High-Severity Incident**: A neighbor that remains DOWN after a link-down on `GigabitEthernet0/1` should be treated as a high-severity routing incident.
