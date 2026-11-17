#!/bin/sh
# Start net-snmp, then lldpd as an AgentX subagent so neighbors appear in LLDP-MIB.
# -cc also sends CDP frames: the Docker bridge does not forward LLDP frames, but it does forward CDP.
mkdir -p /var/agentx
snmpd -Lo -C -c "/etc/snmp/$SNMPD_CONF" udp:161
sleep 1
exec lldpd -d -cc -x -X /var/agentx/master -I eth0
