# OSPF lab notes (documentation prefixes only)

## Topology
- `core-sw1` and peer `core-sw2` run a single OSPF process (process 1) on `GigabitEthernet0/1`.
- `core-sw2` router ID / neighbor ID: `192.0.2.19`.
- `core-sw1` management access originates from `192.0.2.50`.
- All addresses are RFC 5737 documentation prefixes (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`).

## Expected behavior
- A brief link-down on `GigabitEthernet0/1` will take the OSPF adjacency from FULL to DOWN (dead timer expired).
- When the line protocol returns, the adjacency should return to FULL (`Loading Done`).
- A recovered adjacency is **not** a standing outage. Record it as a transient bounce and confirm whether FULL was restored.
- Treat a neighbor that stays DOWN as a high-severity routing incident.
