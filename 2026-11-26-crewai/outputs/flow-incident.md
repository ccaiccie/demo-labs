# Title
SSH Denial of Service Incident

## What happened
Multiple SSH login denials were observed from the source IP 198.51.100.66, suggesting an SSH denial burst attack.

## Why it is high severity
The repeated SSH login denials from a single IP address indicate a potential SSH denial of service attack, which can compromise system security and stability.

## Immediate checks
- Review the firewall logs for any other entries from 198.51.100.66.
- Conduct a full system scan to identify if any services are compromised.
- Temporarily block the IP address 198.51.100.66 to prevent further unauthorized access.
- Monitor system performance and logs for any unusual activity.