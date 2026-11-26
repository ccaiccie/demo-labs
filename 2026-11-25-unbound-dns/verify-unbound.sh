#!/usr/bin/env bash
# Query only the explicitly selected resolver. This script never changes settings.
set -u
export LC_ALL=C

usage() {
  cat <<'HELP'
Usage: verify-unbound.sh --resolver ADDRESS --local-host FQDN --local-ip IPv4
       --missing FQDN --public FQDN --signed FQDN --bogus FQDN [--check-cd]
Requires BIND dig (dnsutils on Debian/Ubuntu, bind-utils on Fedora).
Use an IPv4/IPv6 resolver address and names from your own isolated lab.
--signed and --bogus must have A records; the bogus name must be deliberately
mis-signed, not merely unsigned. --check-cd adds a non-scoring diagnostic query.
HELP
}

resolver= local_host= local_ip= missing= public= signed= bogus= check_cd=0
bad_args() { printf '%s\n' "$*" >&2; usage >&2; exit 2; }
while (( $# )); do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --check-cd) check_cd=1; shift; continue ;;
    --resolver|--local-host|--local-ip|--missing|--public|--signed|--bogus)
      (( $# >= 2 )) && [[ -n $2 && $2 != --* ]] || bad_args "Missing value for $1"
      case "$1" in
        --resolver) resolver=$2 ;;
        --local-host) local_host=$2 ;;
        --local-ip) local_ip=$2 ;;
        --missing) missing=$2 ;;
        --public) public=$2 ;;
        --signed) signed=$2 ;;
        --bogus) bogus=$2 ;;
      esac
      shift 2 ;;
    *) bad_args "Unknown option: $1" ;;
  esac
done

ipv4() {
  local octet
  local -a octets
  [[ $1 =~ ^(0|[1-9][0-9]{0,2})(\.(0|[1-9][0-9]{0,2})){3}$ ]] || return 1
  IFS=. read -r -a octets <<< "$1"
  for octet in "${octets[@]}"; do (( octet <= 255 )) || return 1; done
}
fqdn() { [[ $1 =~ ^([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.?$ && ${#1} -le 253 ]]; }
ipv4 "$resolver" || [[ $resolver == *:* && $resolver =~ ^[0-9a-fA-F:]+$ ]] || bad_args "Supply an explicit resolver IP address."
ipv4 "$local_ip" || bad_args "Supply the expected canonical IPv4 address for the local host."
for name in "$local_host" "$missing" "$public" "$signed" "$bogus"; do
  fqdn "$name" || bad_args "Invalid or missing fully qualified DNS name: $name"
done
[[ ${missing%.} != "${local_host%.}" && ${bogus%.} != "${signed%.}" ]] || bad_args "Use distinct local/missing and signed/bogus names."
command -v dig >/dev/null 2>&1 || bad_args "BIND dig is not installed."

failures=0 reply= status=
fail() { printf 'FAIL  %s\n' "$1"; printf '%s\n' "$reply" >&2; (( failures += 1 )); }
pass() { printf 'PASS  %s\n' "$1"; }
query() {
  # -r prevents ~/.digrc from silently changing flags. DNSSEC DO and CD are separate.
  reply=$(dig -r "@$resolver" +time=4 +tries=1 +nosearch +noall +comments +answer +nocdflag "$@" 2>&1)
  local rc=$?
  status=$(awk '/^;; ->>HEADER<<-/ { s=$0; sub(/^.*status: /,"",s); sub(/,.*/,"",s); print s; exit }' <<< "$reply")
  (( rc == 0 )) && [[ -n $status ]]
}
answer() {
  # Scan only the answer section and compare owner/value case-insensitively.
  awk -v want="$1" -v value="${2-}" -v owner="${3-}" '
    /^;; ANSWER SECTION:/ { active=1; next }
    /^;; .* SECTION:/ { active=0 }
    active && $3 == "IN" && $4 == want && (value == "" || tolower($5) == tolower(value)) && (owner == "" || tolower($1) == tolower(owner)) { found=1 }
    END { exit !found }
  ' <<< "$reply"
}
ad_bit() {
  awk '/^;; flags:/ {
    line=$0; sub(/^;; flags: /,"",line); sub(/;.*/,"",line)
    if (line ~ /(^|[[:space:]])ad([[:space:]]|$)/) found=1
  } END { exit !found }' <<< "$reply"
}
absname() { printf '%s.\n' "${1%.}"; }
local_host=$(absname "$local_host")
missing=$(absname "$missing")
public=$(absname "$public")
signed=$(absname "$signed")
bogus=$(absname "$bogus")
IFS=. read -r o1 o2 o3 o4 <<< "$local_ip"
reverse_owner="$o4.$o3.$o2.$o1.in-addr.arpa."

if query "$local_host" A && [[ $status == NOERROR ]] && answer A "$local_ip" "$local_host"; then
  pass "Local A: $local_host -> $local_ip"
else fail "Local A: expected $local_host -> $local_ip"; fi
if query -x "$local_ip" && [[ $status == NOERROR ]] && answer PTR "$local_host" "$reverse_owner"; then
  pass "Local PTR: $local_ip -> $local_host"
else fail "Local PTR: expected $local_ip -> $local_host"; fi
if query "$missing" A && [[ $status == NXDOMAIN ]]; then
  pass "Local negative answer: $missing is NXDOMAIN"
else fail "Local negative answer: expected NXDOMAIN for $missing"; fi
if query "$public" A && [[ $status == NOERROR ]] && answer A; then
  pass "Public resolution: $public returned an A record"
else fail "Public resolution: expected a successful A answer for $public"; fi
if query "$signed" A +dnssec && [[ $status == NOERROR ]] && answer A && ad_bit; then
  pass "DNSSEC positive: $signed returned an authenticated A answer (AD)"
else fail "DNSSEC positive: expected a successful A answer and AD for $signed"; fi
if query "$bogus" A +dnssec && [[ $status == SERVFAIL ]]; then
  pass "DNSSEC negative: $bogus returned SERVFAIL"
else fail "DNSSEC negative: expected SERVFAIL for $bogus"; fi
if (( check_cd )); then
  if query "$bogus" A +dnssec +cdflag && [[ $status == NOERROR ]] && answer A && ! ad_bit; then
    printf 'INFO  With checking disabled: %s returned an A answer without AD.\n' "$bogus"
  else
    printf 'INFO  With checking disabled: no unchecked A answer (status: %s). Resolver/upstream behavior may still prevent an answer.\n' "${status:-no response}"
    printf '%s\n' "$reply"
  fi
fi
printf '\n%d failed of 6 required checks.\n' "$failures"
if (( failures )); then exit 1; fi
