#!/usr/bin/env bash
# =============================================================================
# ise-configure.sh — configure the lab ISE through its REST APIs
#
# This is the API equivalent of the GUI build in Part 6 of the lab guide
# (ise-ftd-cml-lab-guide.md). The lab itself was configured in the ISE web GUI;
# this script reproduces the same end state with REST calls.
#
# ISE has two configuration APIs and this script uses both, because that is
# how Cisco split them:
#   * ERS (https://ISE:9060/ers/config/...) — network devices, internal users,
#     endpoint groups, endpoints, authorization profiles.
#   * OpenAPI (https://ISE/api/v1/...) — policy sets and their rules
#     (ERS cannot manage policy sets; on ISE 3.1+ they live in the OpenAPI).
# The lab runs ISE 3.5, so both are available.
#
# What it creates (same names as the guide):
#   * Network devices:  CORE-SW 10.10.20.2, ACC-SW 10.10.20.3 (RADIUS secret
#                       LabRadius-2026 — must match the switches' config)
#   * Internal user:    employee1 (the PC1 802.1X identity)
#   * Endpoint group:   MAB-Devices, with LINUX1's MAC 52:54:00:10:30:01
#                       statically assigned (that static assignment is what
#                       makes MAB deterministic for this endpoint)
#   * AuthZ profiles:   VLAN10-USERS (VLAN 10), VLAN30-IOT (VLAN 30)
#   * Policy set rules in the Default policy set: Wired_802.1X -> VLAN10-USERS,
#     Wired_MAB -> VLAN30-IOT, placed above the factory rules so the factory
#     Basic_Authenticated_Access rule cannot catch MAB first (it returns no
#     VLAN). Authentication rules are NOT touched: the lab used the factory
#     Default authentication rule with the Default Network Access allowed-
#     protocols list, exactly as in the GUI build.
#
# Prerequisites (one-time, in the ISE GUI):
#   Administration -> System -> Settings -> API Settings: enable
#   "ERS (Read/Write)" and "Open API (Read/Write)". The calling account must
#   be an ISE admin in the ERS Admin group. The script defaults to the lab
#   admin account from the guide (GUI password — the one set at the forced
#   first-login reset, NOT the unchanged CLI password). Override with
#   ISE_USER / ISE_PASS.
#
# Run from ADMIN-PC (or any host that can reach https://10.10.20.10).
# Requires: bash, curl, jq.
# =============================================================================
set -u

ISE="${ISE_URL:-https://10.10.20.10}"
ISE_USER="${ISE_USER:-admin}"
ISE_PASS="${ISE_PASS:-LabISE-2027!}"
ERS="$ISE:9060/ers/config"
OPENAPI="$ISE/api/v1"
CURL="curl -sk -u $ISE_USER:$ISE_PASS"
JSON='-H Content-Type:application/json -H Accept:application/json'

step() { printf '\n=== %s ===\n' "$*"; }
die()  { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
command -v jq >/dev/null || die "jq is required (sudo apt install -y jq)"

# ------------------------------------------------------------- helpers -------
ers_total() { # $1 = resource, $2 = name -> prints SearchResult.total for name.EQ
  $CURL "$ERS/$1?filter=name.EQ.$2" -H 'Accept: application/json' | jq -r '.SearchResult.total // 0'
}
ers_create() { # $1 = resource, $2 = name, $3 = json body
  if [ "$(ers_total "$1" "$2")" != "0" ]; then
    echo "exists, skipping: $2"
  else
    echo "creating: $2"
    $CURL -X POST "$ERS/$1" $JSON -d "$3" -o /dev/null -w '%{http_code}' \
      | grep -q '^201$' || die "ERS create failed for $2"
  fi
}

step "Sanity check — ERS reachable"
$CURL "$ERS/networkdevice" -H 'Accept: application/json' | jq -e '.SearchResult' >/dev/null \
  || die "ERS did not answer — is ERS (Read/Write) enabled in API Settings?"
echo "ERS OK"

# --------------------------------------------------------- network devices ---
step "Network devices (Administration -> Network Resources in the GUI)"
NAD_BODY() { # $1 = name, $2 = ip
  cat <<EOF
{"NetworkDevice":{
  "name":"$1","profileName":"Cisco","coaPort":1700,
  "NetworkDeviceIPList":[{"ipaddress":"$2","mask":32}],
  "NetworkDeviceGroupList":[
    {"name":"Location#All Locations"},
    {"name":"Device Type#All Device Types"}],
  "authenticationSettings":{
    "networkProtocol":"RADIUS",
    "radiusSharedSecret":"LabRadius-2026",
    "enableKeyWrap":false,"keyInputFormat":"ASCII"}}}
EOF
}
ers_create networkdevice CORE-SW "$(NAD_BODY CORE-SW 10.10.20.2)"
ers_create networkdevice ACC-SW  "$(NAD_BODY ACC-SW 10.10.20.3)"

# ------------------------------------------------------------ internal user --
step "Internal user employee1 (Users -> Identities in the GUI)"
EMP_GROUP_ID=$($CURL "$ERS/identitygroup?filter=name.EQ.Employee" -H 'Accept: application/json' \
  | jq -r '.SearchResult.resources[0].id')
[ -n "$EMP_GROUP_ID" ] && [ "$EMP_GROUP_ID" != "null" ] || die "Employee identity group not found"
ers_create internaluser employee1 "{
  \"InternalUser\":{
    \"name\":\"employee1\",\"password\":\"Employee-2026!\",
    \"description\":\"PC1 wired 802.1X user (lab guide Part 6)\",
    \"changePassword\":false,\"expiryDateEnabled\":false,\"enabled\":true,
    \"identityGroups\":\"$EMP_GROUP_ID\"}}"

# ------------------------------------------------- endpoint group + endpoint -
step "Endpoint group MAB-Devices + LINUX1 endpoint (Endpoints in the GUI)"
if [ "$(ers_total endpointgroup MAB-Devices)" = "0" ]; then
  echo "creating: MAB-Devices"
  LOCATION=$($CURL -X POST "$ERS/endpointgroup" $JSON -s -D - -o /dev/null \
    -d '{"EndPointGroup":{"name":"MAB-Devices","systemDefined":false,
         "description":"MAB endpoints — devices with no 802.1X supplicant"}}' \
    | grep -i '^location:' | tr -d '\r' | awk '{print $2}')
  MAB_GROUP_ID="${LOCATION##*/}"
else
  echo "exists, skipping: MAB-Devices"
  MAB_GROUP_ID=$($CURL "$ERS/endpointgroup?filter=name.EQ.MAB-Devices" \
    -H 'Accept: application/json' | jq -r '.SearchResult.resources[0].id')
fi
[ -n "$MAB_GROUP_ID" ] && [ "$MAB_GROUP_ID" != "null" ] || die "could not resolve MAB-Devices group id"
echo "MAB-Devices id: $MAB_GROUP_ID"
ers_create endpoint 52:54:00:10:30:01 "{
  \"EndPoint\":{
    \"mac\":\"52:54:00:10:30:01\",\"groupId\":\"$MAB_GROUP_ID\",
    \"staticGroupAssignment\":true,
    \"description\":\"LINUX1 — Alpine MAB device (lab guide Part 6)\"}}"

# ------------------------------------------------------ authorization profiles
step "Authorization profiles (Policy -> Policy Elements in the GUI)"
# vlan.nameID is the VLAN ID; tunnelPrivateGroupID "1:<vlan>" is the value the
# GUI shows for the VLAN tunnel attribute the switch applies to the port.
ers_create authorizationprofile VLAN10-USERS '{
  "AuthorizationProfile":{
    "name":"VLAN10-USERS","description":"Authenticated users land on VLAN 10",
    "accessType":"ACCESS_ACCEPT","authzProfileType":"SWITCH",
    "vlan":{"nameID":"10","tunnelPrivateGroupID":"1:10"}}}'
ers_create authorizationprofile VLAN30-IOT '{
  "AuthorizationProfile":{
    "name":"VLAN30-IOT","description":"MAB devices land on VLAN 30",
    "accessType":"ACCESS_ACCEPT","authzProfileType":"SWITCH",
    "vlan":{"nameID":"30","tunnelPrivateGroupID":"1:30"}}}'

# ------------------------------------------------------------- policy set ----
step "Policy set rules via the OpenAPI (Policy -> Policy Sets in the GUI)"
PS_ID=$($CURL "$OPENAPI/policy/network-access/policy-set" -H 'Accept: application/json' \
  | jq -r '.response[] | select(.name=="Default") | .id')
[ -n "$PS_ID" ] && [ "$PS_ID" != "null" ] || die "Default policy set not found via the OpenAPI"
echo "Default policy set: $PS_ID"

AUTHZ_URL="$OPENAPI/policy/network-access/policy-set/$PS_ID/authorization"
authz_create() { # $1 = rule name, $2 = rank, $3 = condition name, $4 = profile
  if $CURL "$AUTHZ_URL" -H 'Accept: application/json' \
       | jq -e --arg n "$1" '.response[] | select(.name==$n)' >/dev/null; then
    echo "exists, skipping: $1"
  else
    echo "creating rule: $1 -> $4"
    $CURL -X POST "$AUTHZ_URL" $JSON -o /dev/null -w '%{http_code}' -d "{
      \"name\":\"$1\",\"state\":\"enabled\",\"rank\":$2,
      \"condition\":{\"conditionType\":\"ConditionReference\",\"isNegate\":false,
                     \"name\":\"$3\"},
      \"profile\":[\"$4\"],\"securityGroup\":null}" \
      | grep -qE '^(200|201)$' || die "policy rule create failed: $1"
  fi
}
# The condition names are ISE's built-in library conditions — the same ones
# the GUI build picked in Conditions Studio. Both rules sit at the top of the
# set, above the factory rules (see the header note about MAB).
authz_create Wired_802.1X 0 Wired_802.1X VLAN10-USERS
authz_create Wired_MAB    1 Wired_MAB    VLAN30-IOT

# ------------------------------------------------------------------ verify ---
step "Verify — what ISE now holds"
echo "network devices:"; $CURL "$ERS/networkdevice" -H 'Accept: application/json' \
  | jq -r '.SearchResult.resources[].name' | sed 's/^/  /'
echo "internal users:"; $CURL "$ERS/internaluser" -H 'Accept: application/json' \
  | jq -r '.SearchResult.resources[].name' | sed 's/^/  /'
echo "endpoints:"; $CURL "$ERS/endpoint" -H 'Accept: application/json' \
  | jq -r '.SearchResult.resources[].name' | sed 's/^/  /'
echo "authorization rules in the Default set:"
$CURL "$AUTHZ_URL" -H 'Accept: application/json' \
  | jq -r '.response[] | "  \(.name) -> \(.profile // [] | join(","))"'
step "Done — bounce the ACC-SW ports (Gi1/0/2, Gi1/0/3) and watch Operations -> RADIUS -> Live Logs"
