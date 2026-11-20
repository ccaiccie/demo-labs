FROM alpine:3.20

RUN apk add --no-cache net-snmp net-snmp-tools

EXPOSE 161/udp

ENTRYPOINT ["snmpd", "-f", "-Lo", "-C", "-c", "/etc/snmp/snmpd.conf"]
