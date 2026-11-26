# Ticket memory

- Source: `edge-fw1.log`
- Severity: high
- Summary: The log contains multiple SSH login denials from the source IP 198.51.100.66, indicating an SSH denial burst attack.
- Artifact: `flow-incident.md`
- Follow up: review the source address, confirm whether the deny burst stopped, and note any later successful admin login from a trusted address.
