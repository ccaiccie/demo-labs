#!/usr/bin/env bash
# Offline comparison of two time-bounded WAN pcaps. No interfaces are opened.
set -u
export LC_ALL=C
usage() {
  printf 'Usage: %s COLD_WAN.pcap WARM_WAN.pcap\n' "${0##*/}"
  printf 'Counts outbound IPv4/IPv6 TCP/UDP destination-port-53 packets in each WAN capture.\n'
}
if [[ ${1-} == --help ]]; then usage; exit 0; fi
if (( $# != 2 )); then usage >&2; exit 2; fi
command -v tcpdump >/dev/null 2>&1 || { printf 'Install tcpdump first.\n' >&2; exit 2; }
for pcap in "$@"; do
  [[ -f $pcap && -r $pcap ]] || { printf 'Not a readable capture file: %s\n' "$pcap" >&2; exit 2; }
done
count() {
  # The filter matches outbound requests to standard port 53 on these
  # WAN-only pcaps; not replies, DNS-over-TLS, or DNS-over-HTTPS.
  # count *packets*, not unique DNS questions. -q omits expanded DNS lines.
  local packets
  packets=$(tcpdump -nn -q -r "$1" '(ip or ip6) and (tcp or udp) and dst port 53') || return 1
  awk 'NF { n++ } END { print n+0 }' <<< "$packets"
}
cold=$(count "$1") || exit 2
warm=$(count "$2") || exit 2
printf 'Cold WAN destination-port-53 packets: %d\nWarm WAN destination-port-53 packets: %d\n' "$cold" "$warm"
if (( cold > 0 && warm == 0 )); then
  printf 'Pattern is consistent with a cache hit. Confirm both matching client queries received answers on LAN.\n'
else
  printf 'Pattern is inconclusive. Check capture intervals, background traffic, cache TTL, and LAN answers.\n'
fi
