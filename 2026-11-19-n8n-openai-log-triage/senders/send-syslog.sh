#!/usr/bin/env bash
# Usage: ./senders/send-syslog.sh <host> "<log message>"
# Sends a real RFC 3164 syslog packet (facility local7, severity error) over UDP
# to the syslog-forwarder on 127.0.0.1:5514, as a router or switch would.
HOST="${1:?host}"; MSG="${2:?message}"
printf '<187>%s %s %s' "$(date '+%b %e %H:%M:%S')" "$HOST" "$MSG" > /dev/udp/127.0.0.1/5514
echo "syslog sent to udp/127.0.0.1:5514 as $HOST"
