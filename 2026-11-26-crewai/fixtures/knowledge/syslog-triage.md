# Syslog triage playbook (lab)

## Scope
Review the three device logs together: `core-sw1.log`, `edge-fw1.log`, and `access-sw2.log`.
Do not invent interfaces, addresses, or MAC addresses that are not in the files.

## What to flag
1. **MAC flaps** — the same MAC address moving rapidly between two access ports on the same VLAN. That often means a loop, a duplicated NIC, or an unstable station move. Include both ports, the VLAN, and the MAC.
2. **SSH deny burst** — many authentication failures or deny messages from one source in a short window. Record the source, destination (if present), count, and whether any login later succeeded.
3. **OSPF adjacency changes** — note DOWN and FULL events and **whether the adjacency recovered**. A bounce that returns to FULL is lower severity than a neighbor that remains down.

## Severity hints
- High: active attack pattern (SSH deny burst), unresolved routing adjacency, loop-like MAC flapping that is still ongoing.
- Medium: recovered OSPF bounce, short MAC flap that has stopped, isolated auth failures.
- Low: routine config-from-console messages, link up/down with no protocol impact.

## Reporting
Write compact bullets first, then a short narrative. Use only RFC 5737 documentation addresses from the logs.
