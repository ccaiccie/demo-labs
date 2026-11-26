#!/usr/bin/env bash
# Read-only probes. Run from the disposable client, never on the firewall.
set -euo pipefail
usage() {
 cat <<'USAGE'
verify-branch.sh dns baseline|filtered
verify-branch.sh origin ./origin-ca.crt
verify-branch.sh proxy http://192.168.1.1:3128 ./inspection-ca.crt [./curl-auth.conf]
verify-branch.sh ids baseline|alert|drop

Fixed addresses refer only to the disposable branch lab described in README.
'alert' expects an allowed request; pair it with the exact alert in the GUI.
A 403 by itself is insufficient proof: match the proxy log and origin log.
Store optional curl proxy-user credentials in a private file, never Git.
USAGE
}
[[ $# -gt 0 ]] || { usage; exit 2; }
case "$1" in -h|--help) usage; exit 0;; esac
common=(--silent --show-error --connect-timeout 3 --max-time 8)
get_dns() { dig -r @192.168.1.1 +time=3 +tries=1 +noall +answer +comments "$1" A; }
http_body() {
  curl -q "${common[@]}" --noproxy '*' --fail "$1"
}
case "$1" in
 dns)
  [[ $# -eq 2 && $2 =~ ^(baseline|filtered)$ ]] || { usage; exit 2; }
  localdns=$(get_dns portal.branch.test)
  listdns=$(get_dns example.org)
  printf '%s\n%s\n' "$localdns" "$listdns"
  grep -Eq '^portal\.branch\.test\..*[[:space:]]A[[:space:]]+198\.18\.83\.10$' <<<"$localdns"
  if [[ $2 == baseline ]]; then
    grep -Eq 'status: NOERROR' <<<"$listdns"; grep -Eq '[[:space:]]A[[:space:]]' <<<"$listdns"
  else
    if grep -Eq 'status: NXDOMAIN' <<<"$listdns"; then
      ! grep -Eq '^example\.org\..*[[:space:]]A[[:space:]]' <<<"$listdns"
    else
      grep -Eq 'status: NOERROR' <<<"$listdns"
      answers=$(awk '$1=="example.org." && $4=="A" {print $5}' <<<"$listdns")
      [[ $answers == "0.0.0.0" ]]
    fi
  fi
  ;;
 origin)
  [[ $# -eq 2 && -f $2 ]] || { usage; exit 2; }
  for part in docs uploads; do
    body=$(curl -q "${common[@]}" --noproxy '*' --cacert "$2" --fail "https://portal.branch.test/$part")
    [[ $body == "${part^^}_OK" ]]
    printf '/%s 200 %s\n' "$part" "$body"
  done
  ;;
 proxy)
  [[ $# -ge 3 && $# -le 4 && $2 == http://192.168.1.1:3128 && -f $3 ]] || { usage; exit 2; }
  args=()
  if [[ $# == 4 ]]; then [[ -f $4 ]] || exit 2; args=(--config "$4"); fi
  body=$(mktemp)
  trap 'rm -f "$body"' EXIT
  for part in docs uploads; do
    if output=$(curl -q "${args[@]}" "${common[@]}" --noproxy '' --proxy "$2" --cacert "$3" -o "$body" -w '%{http_code} %{http_connect}' "https://portal.branch.test/$part"); then
      read -r http connect <<< "$output"
    else
      rc=$?
      printf 'Proxy probe /%s failed before HTTP policy validation (curl exit=%s, HTTP/CONNECT=%s).\n' "$part" "$rc" "$output" >&2
      exit 1
    fi
    printf '/%s CONNECT %s response %s\n' "$part" "$connect" "$http"
    [[ $connect == 200 ]]
    if [[ $part == docs ]]; then [[ $http == 200 && $(<"$body") == DOCS_OK ]]
    else [[ $http == 403 ]] && ! grep -q UPLOADS_OK "$body"; fi
  done
  ;;
 ids)
  [[ $# -eq 2 && $2 =~ ^(baseline|alert|drop)$ ]] || { usage; exit 2; }
  [[ $(http_body http://198.18.83.10:8080/health) == HEALTH_OK ]]
  if [[ $2 != drop ]]; then
    [[ $(http_body http://198.18.83.10:8080/ids-check) == BRANCH_LAB_IDS_MARKER_8E79 ]]
    echo 'Marker request returned its expected body.'
  else
    result=0
    code=$(curl -q "${common[@]}" --noproxy '*' -o /dev/null -w '%{http_code}' http://198.18.83.10:8080/ids-check) || result=$?
    case "$result" in 28|52|56) [[ $code == 000 ]];; *) echo "Unexpected marker result curl=$result HTTP=$code" >&2; exit 1;; esac
    printf 'Clean control passed; marker had no HTTP response (curl=%s). Match its SID and action in the local IPS log.\n' "$result"
  fi
  ;;
 *) usage; exit 2 ;;
esac
echo 'Probe matched its declared expectation.'
