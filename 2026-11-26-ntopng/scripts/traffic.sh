#!/bin/sh
# Lab-only traffic generator. Profiles: office (web + DNS + occasional TLS), engineering (heavier: bulk + iperf3).
P="${1:-office}"
WEB=web.lab.test; IPERF=iperf.lab.test
EXT="example.com www.wikipedia.org github.com www.cloudflare.com www.debian.org"
i=0
while true; do
  i=$((i+1))
  curl -s -o /dev/null "http://$WEB/" 
  dig +short web.lab.test >/dev/null
  ping -c 2 -W 1 10.77.40.10 >/dev/null 2>&1
  if [ $((i % 3)) -eq 0 ]; then
    h=$(echo $EXT | tr ' ' '\n' | awk -v s=$i 'NR==(s%5)+1')
    dig +short "$h" >/dev/null
    curl -s -o /dev/null -m 10 "https://$h/"
  fi
  if [ "$P" = engineering ]; then
    curl -s -o /dev/null "http://$WEB/backup.bin"
    [ $((i % 4)) -eq 0 ] && iperf3 -c $IPERF -t 6 -b 30M >/dev/null 2>&1
  else
    [ $((i % 5)) -eq 0 ] && curl -s -o /dev/null "http://$WEB/backup.bin"
  fi
  sleep $((3 + i % 4))
done
