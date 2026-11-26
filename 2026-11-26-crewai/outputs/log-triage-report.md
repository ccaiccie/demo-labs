### Triage Report

#### Summary
Network issues have been identified and are currently being addressed. The primary issues involve OSPF recovery on core-sw1, SSH denial bursts on edge-fw1, and MAC flaps on access-sw2.

#### Findings
1. **OSPF Recovery on core-sw1**: OSPF has recovered on core-sw1 (neighbor 192.0.2.19). This indicates that the network connectivity issue related to OSPF has been resolved.
2. **SSH Denial Burst on edge-fw1**: There was a burst of SSH denial attempts from the IP address 198.51.100.66. This could indicate a potential security threat or a misconfigured firewall rule.
3. **MAC Flaps on access-sw2**: There were MAC flaps detected on access-sw2 for the MAC address 00:11:22:33:44:61. This MAC address was observed flapping between ports Gi1/0/12 and Gi1/0/24 on VLAN 20. This could indicate a hardware issue or a misconfiguration.

#### Severity
- **OSPF Recovery**: Medium - The OSPF recovery is a positive development and indicates that the network connectivity issue has been resolved.
- **SSH Denial Burst**: High - The SSH denial bursts could be indicative of a security threat and should be investigated immediately.
- **MAC Flaps**: High - The MAC flaps could indicate a hardware issue or misconfiguration, which could affect network stability and security.

#### Recommended Next Checks
1. **OSPF Recovery on core-sw1**: Verify that all OSPF neighbors are correctly configured and that the network connectivity is stable.
2. **SSH Denial Burst on edge-fw1**: Investigate the SSH denial attempts. Check firewall logs for any suspicious activity and ensure that the SSH port is not open to unauthorized sources. Review the SSH configuration and firewall rules to ensure they are secure.
3. **MAC Flaps on access-sw2**: Investigate the MAC flaps. Check the switch configuration to ensure that the ports are correctly configured and that the VLAN assignments are correct. If necessary, replace faulty hardware. Verify that the switch is not experiencing any hardware issues.

Ensure that all findings are logged and reviewed, and take appropriate action to mitigate any potential security risks.
