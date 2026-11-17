FROM alpine:3.22
RUN apk add --no-cache net-snmp lldpd
COPY snmpd-v2c.conf snmpd-v3.conf /etc/snmp/
COPY start.sh /usr/local/bin/start.sh
EXPOSE 161/udp
CMD ["/bin/sh", "/usr/local/bin/start.sh"]
