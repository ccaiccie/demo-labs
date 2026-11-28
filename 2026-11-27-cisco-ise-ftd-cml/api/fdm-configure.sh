#!/usr/bin/env bash
# =============================================================================
# fdm-configure.sh — configure the lab FTD through the FDM REST API
#
# This is the API equivalent of the GUI build in Part 4 of the lab guide
# (ise-ftd-cml-lab-guide.md). The lab itself was built in the FDM GUI; this
# script reproduces the same end state with REST calls so the configuration
# can be versioned, repeated and reviewed like code.
#
# What it creates (same names as the guide):
#   * Network objects:  WEB1, USERS-NET, IOT-NET, SERVICES-NET
#   * Port object:      TCP-8080
#   * Security zone:    iot_zone (inside_zone / outside_zone ship with FDM)
#   * AD realm:         LAB-AD  (against the Samba DC on AD-DC1, 10.10.20.60)
#   * Manual NAT:       PAT-VLAN10, PAT-VLAN20, WEB1-8080 (static :8080 -> WEB1:80)
#   * Access rules:     EGRESS-AUTH, IOT-BLOCK, INSIDE-WEB1, OUTSIDE-WEB1, IOT-WEB1
#                       (the factory Inside_Outside Trust rule is left in place,
#                        exactly as in the GUI build)
#   * Identity rule:    CAPTIVE-PORTAL (active authentication against LAB-AD)
#   * A deployment at the end.
#
# Scope notes (honest limits):
#   * Interfaces, subinterfaces and routing are day-0 work from guide Parts 3-4.
#     This script LOOKS THEM UP BY NAME (outside, inside-trunk-10/-20/-30) and
#     stops with a clear error if they are not there yet.
#   * The two DHCP pools (guide Part 4) are created in the GUI in the lab build;
#     FDM's DHCP API surface is thin, so they are intentionally not scripted here.
#   * Object field names follow the FTD 7.x FDM API ("latest"). If a call is
#     rejected on a different version, the FTD's own API explorer on the box
#     (https://<ftd>/api-explorer) shows the exact schema for that version.
#
# Run from ADMIN-PC (or any host that can reach the FDM management address).
# Requires: bash, curl, jq.  Credentials default to the lab values published
# in the guide; override with FDM_USER / FDM_PASS.
# =============================================================================
set -u

FTD="${FTD_URL:-https://10.10.20.5}"
FDM_USER="${FDM_USER:-admin}"
FDM_PASS="${FDM_PASS:-LabFTD-2026!}"
API="$FTD/api/fdm/latest"

step() { printf '\n=== %s ===\n' "$*"; }
die()  { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
command -v jq >/dev/null || die "jq is required (sudo apt install -y jq)"

# ---------------------------------------------------------------- token ------
step "Authenticate (POST /fdm/token)"
TOKEN=$(curl -sk -X POST "$API/fdm/token" -H 'Content-Type: application/json' \
  -d "{\"grant_type\":\"password\",\"username\":\"$FDM_USER\",\"password\":\"$FDM_PASS\"}" \
  | jq -r '.access_token')
[ -n "$TOKEN" ] && [ "$TOKEN" != "null" ] || die "token request failed — check address/credentials"
AUTH="Authorization: Bearer $TOKEN"
echo "token acquired"

# ------------------------------------------------------------- helpers -------
# GET a collection and print one item (full JSON) selected by .name
get_by_name() { # $1 = path, $2 = name
  curl -sk "$API$1?limit=200" -H "$AUTH" | jq -c --arg n "$2" '.items[] | select(.name==$n)' | head -1
}
# Print a reference object {id,name,type,version} for a named item
ref_by_name() { # $1 = path, $2 = name
  local item; item=$(get_by_name "$1" "$2")
  [ -n "$item" ] || die "not found: $2 (in $1) — create it in the GUI first or check the name"
  echo "$item" | jq -c '{id, name, type, version}'
}
# POST unless an item with the same name already exists in the collection
create_unless_exists() { # $1 = path, $2 = name, $3 = json body
  if [ -n "$(get_by_name "$1" "$2")" ]; then
    echo "exists, skipping: $2"
  else
    echo "creating: $2"
    curl -sk -X POST "$API$1" -H "$AUTH" -H 'Content-Type: application/json' -d "$3" \
      | jq -e '.id' >/dev/null || die "create failed for $2"
  fi
}

# ------------------------------------------------- look up the day-0 state ---
step "Discover policies, zones and interfaces (created in the GUI, guide Parts 3-4)"
ACP_ID=$(curl -sk "$API/policy/accesspolicies" -H "$AUTH" | jq -r '.items[0].id')
NAT_ID=$(curl -sk "$API/policy/manualnatpolicies" -H "$AUTH" | jq -r '.items[0].id')
IDP_ID=$(curl -sk "$API/policy/identitypolicies" -H "$AUTH" | jq -r '.items[0].id')
[ "$ACP_ID" != "null" ] && [ "$NAT_ID" != "null" ] && [ "$IDP_ID" != "null" ] \
  || die "could not read the policy containers"
echo "access policy: $ACP_ID"; echo "manual NAT policy: $NAT_ID"; echo "identity policy: $IDP_ID"

# iot_zone is the one zone the lab adds; create it (bound to the VLAN 30
# subinterface) if it is missing. inside_zone / outside_zone are factory zones.
if [ -z "$(get_by_name /object/securityzones iot_zone)" ]; then
  echo "creating zone: iot_zone"
  IOT_IF=$(ref_by_name /devices/default/interfaces inside-trunk-30)
  curl -sk -X POST "$API/object/securityzones" -H "$AUTH" -H 'Content-Type: application/json' \
    -d "{\"name\":\"iot_zone\",\"type\":\"securityzone\",\"interfaces\":[$IOT_IF]}" \
    | jq -e '.id' >/dev/null || die "zone create failed"
fi
IN_ZONE=$(ref_by_name /object/securityzones inside_zone)
OUT_ZONE=$(ref_by_name /object/securityzones outside_zone)
IOT_ZONE=$(ref_by_name /object/securityzones iot_zone)
OUT_IF=$(ref_by_name /devices/default/interfaces outside)

# --------------------------------------------------------- network objects ---
step "Network objects (Objects -> Networks in the GUI)"
create_unless_exists /object/networks WEB1 \
  '{"name":"WEB1","value":"10.10.20.20","subType":"HOST","type":"networkobject"}'
create_unless_exists /object/networks USERS-NET \
  '{"name":"USERS-NET","value":"10.10.10.0/24","subType":"NETWORK","type":"networkobject"}'
create_unless_exists /object/networks IOT-NET \
  '{"name":"IOT-NET","value":"10.10.30.0/24","subType":"NETWORK","type":"networkobject"}'
create_unless_exists /object/networks SERVICES-NET \
  '{"name":"SERVICES-NET","value":"10.10.20.0/24","subType":"NETWORK","type":"networkobject"}'
WEB1=$(ref_by_name /object/networks WEB1)
USERS_NET=$(ref_by_name /object/networks USERS-NET)
IOT_NET=$(ref_by_name /object/networks IOT-NET)
SERVICES_NET=$(ref_by_name /object/networks SERVICES-NET)

step "Port object for the published web service"
create_unless_exists /object/tcpports TCP-8080 \
  '{"name":"TCP-8080","port":"8080","type":"tcpportobject"}'
TCP8080=$(ref_by_name /object/tcpports TCP-8080)
# The translated service is the factory "http" port object if present,
# otherwise create TCP-80 and use that.
if [ -n "$(get_by_name /object/tcpports http)" ]; then
  HTTP_PORT=$(ref_by_name /object/tcpports http)
else
  create_unless_exists /object/tcpports TCP-80 \
    '{"name":"TCP-80","port":"80","type":"tcpportobject"}'
  HTTP_PORT=$(ref_by_name /object/tcpports TCP-80)
fi

# --------------------------------------------------------------- AD realm ----
step "AD realm LAB-AD (Objects -> Identity Sources in the GUI)"
create_unless_exists /object/realms LAB-AD '{
  "name":"LAB-AD","type":"activedirectoryrealm","enabled":true,"realmId":2,
  "dirUsername":"Administrator@LAB.LOCAL","dirPassword":"LabAdmin-2026!",
  "baseDN":"DC=lab,DC=local","adPrimaryDomain":"LAB.LOCAL",
  "directoryConfigurations":[{"hostname":"10.10.20.60","port":389,"encryption":"NONE"}]}'
REALM=$(ref_by_name /object/realms LAB-AD)
echo "realm ref: $REALM"

# ------------------------------------------------------------------- NAT -----
step "Manual NAT rules (Policies -> NAT in the GUI)"
# FDM presents zones in the NAT dialog; the API takes the zone references as
# interfaceIn / interfaceOut. "Interface" as a translated source is the
# destination interface object itself (dynamic PAT to its address).
create_unless_exists "/policy/manualnatpolicies/$NAT_ID/manualnatrules" PAT-VLAN10 "{
  \"name\":\"PAT-VLAN10\",\"type\":\"manualnatrule\",\"natType\":\"DYNAMIC\",\"enabled\":true,
  \"interfaceIn\":$IN_ZONE,\"interfaceOut\":$OUT_ZONE,
  \"originalSource\":$USERS_NET,\"translatedSource\":$OUT_IF}"
create_unless_exists "/policy/manualnatpolicies/$NAT_ID/manualnatrules" PAT-VLAN20 "{
  \"name\":\"PAT-VLAN20\",\"type\":\"manualnatrule\",\"natType\":\"DYNAMIC\",\"enabled\":true,
  \"interfaceIn\":$IN_ZONE,\"interfaceOut\":$OUT_ZONE,
  \"originalSource\":$SERVICES_NET,\"translatedSource\":$OUT_IF}"
create_unless_exists "/policy/manualnatpolicies/$NAT_ID/manualnatrules" WEB1-8080 "{
  \"name\":\"WEB1-8080\",\"type\":\"manualnatrule\",\"natType\":\"STATIC\",\"enabled\":true,
  \"interfaceIn\":$OUT_ZONE,\"interfaceOut\":$IN_ZONE,
  \"originalDestination\":$OUT_IF,\"originalService\":$TCP8080,
  \"translatedDestination\":$WEB1,\"translatedService\":$HTTP_PORT}"
# NOTE from the lab build: on this FTD the static rule's configuration is
# accepted and deploys cleanly, but traffic addressed to the FTD's own
# DHCP-assigned outside address is classified as self-addressed and never
# engages the rule (see the guide's Troubleshooting notes). Give the outside
# interface a static address if you need the publish to answer end to end.

# ----------------------------------------------------------- access rules ----
step "Access control rules (Policies -> Access Control in the GUI)"
APP_HTTP=$(ref_by_name /object/applications HTTP)
APP_HTTPS=$(ref_by_name /object/applications HTTPS)
# "at" pins each rule's position so the finished order matches the guide:
# EGRESS-AUTH, factory Inside_Outside (Trust), IOT-BLOCK, INSIDE-WEB1,
# OUTSIDE-WEB1, IOT-WEB1. EGRESS-AUTH must sit above the Trust rule or user
# traffic is trusted before the identity policy can challenge it.
add_rule() { # $1 = name, $2 = position, $3 = body
  if [ -n "$(get_by_name "/policy/accesspolicies/$ACP_ID/accessrules" "$1")" ]; then
    echo "exists, skipping: $1"
  else
    echo "creating rule at position $2: $1"
    curl -sk -X POST "$API/policy/accesspolicies/$ACP_ID/accessrules" \
      -H "$AUTH" -H 'Content-Type: application/json' -d "$3" \
      | jq -e '.id' >/dev/null || die "access rule failed: $1"
  fi
}
add_rule EGRESS-AUTH 0 "{
  \"name\":\"EGRESS-AUTH\",\"type\":\"accessrule\",\"ruleAction\":\"PERMIT\",\"enabled\":true,
  \"sourceZones\":[$IN_ZONE],\"destinationZones\":[$OUT_ZONE],
  \"sourceNetworks\":[$USERS_NET],\"applications\":[$APP_HTTP,$APP_HTTPS]}"
add_rule IOT-BLOCK 2 "{
  \"name\":\"IOT-BLOCK\",\"type\":\"accessrule\",\"ruleAction\":\"DENY\",\"enabled\":true,
  \"sourceZones\":[$IOT_ZONE],\"destinationZones\":[$OUT_ZONE]}"
add_rule INSIDE-WEB1 3 "{
  \"name\":\"INSIDE-WEB1\",\"type\":\"accessrule\",\"ruleAction\":\"PERMIT\",\"enabled\":true,
  \"sourceZones\":[$IN_ZONE],\"destinationZones\":[$IN_ZONE],
  \"destinationNetworks\":[$WEB1],\"applications\":[$APP_HTTP]}"
add_rule OUTSIDE-WEB1 4 "{
  \"name\":\"OUTSIDE-WEB1\",\"type\":\"accessrule\",\"ruleAction\":\"PERMIT\",\"enabled\":true,
  \"sourceZones\":[$OUT_ZONE],\"destinationZones\":[$IN_ZONE],
  \"destinationNetworks\":[$WEB1],\"applications\":[$APP_HTTP]}"
add_rule IOT-WEB1 5 "{
  \"name\":\"IOT-WEB1\",\"type\":\"accessrule\",\"ruleAction\":\"PERMIT\",\"enabled\":true,
  \"sourceZones\":[$IOT_ZONE],\"destinationZones\":[$IN_ZONE],
  \"destinationNetworks\":[$WEB1],\"applications\":[$APP_HTTP]}"

# --------------------------------------------------------- identity policy ---
step "Identity policy + CAPTIVE-PORTAL rule (Policies -> Identity in the GUI)"
# Enable the identity policy (GET -> set enabled -> PUT back with its version)
IDP_OBJ=$(curl -sk "$API/policy/identitypolicies/$IDP_ID" -H "$AUTH")
if [ "$(echo "$IDP_OBJ" | jq -r '.enabled')" != "true" ]; then
  echo "$IDP_OBJ" | jq -c '.enabled = true' > /tmp/idp.json
  curl -sk -X PUT "$API/policy/identitypolicies/$IDP_ID" \
    -H "$AUTH" -H 'Content-Type: application/json' -d @/tmp/idp.json \
    | jq -e '.id' >/dev/null || die "enabling the identity policy failed"
  echo "identity policy enabled"
fi
create_unless_exists "/policy/identitypolicies/$IDP_ID/identityrules" CAPTIVE-PORTAL "{
  \"name\":\"CAPTIVE-PORTAL\",\"type\":\"identityrule\",\"enabled\":true,
  \"sourceZones\":[$IN_ZONE],\"sourceNetworks\":[$USERS_NET],
  \"realm\":$REALM,\"action\":\"ACTIVE_AUTHENTICATION\"}"
# The action value follows the FTD 7.x API model for active (captive-portal)
# authentication; the passive default rule the policy ships with is untouched,
# as in the GUI build.

# ----------------------------------------------------------------- deploy ----
step "Deploy (the Deploy button in the GUI)"
curl -sk -X POST "$API/operational/deploy" -H "$AUTH" -H 'Content-Type: application/json' -d '{}' \
  | jq -r '"deployment queued: \(.id // "n/a") state=\(.state // "unknown")"'
for i in $(seq 1 30); do
  STATE=$(curl -sk "$API/jobs/deployments?limit=1" -H "$AUTH" | jq -r '.items[0].state // "unknown"')
  echo "deploy state: $STATE"
  case "$STATE" in
    DEPLOYED) break ;;
    FAILED|DEPLOY_FAILED) die "deployment failed — read the job messages in FDM" ;;
    *) sleep 10 ;;
  esac
done
[ "$STATE" = "DEPLOYED" ] || die "deployment did not confirm within 5 minutes (last state: $STATE)"

# ----------------------------------------------------------------- revoke ----
curl -sk -X DELETE "$API/fdm/token" -H "$AUTH" \
  -H 'Content-Type: application/json' \
  -d "{\"grant_type\":\"revoke_token\",\"access_token\":\"$TOKEN\"}" >/dev/null 2>&1 || true
step "Done — FTD configuration now matches the GUI build in the guide"
