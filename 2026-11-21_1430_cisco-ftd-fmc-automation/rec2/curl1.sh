source /root/ftd-automation/rec2/common.sh; source /root/lab-secrets.env
H=$(curl -sk -X POST -u "admin:$LAB_ADMIN_PW" https://192.168.100.10/api/fmc_platform/v1/auth/generatetoken -D - -o /dev/null)
TOKEN=$(echo "$H" | awk 'tolower($1)=="x-auth-access-token:"{print $2}' | tr -d '\r'); DOM=$(echo "$H" | awk 'tolower($1)=="domain_uuid:"{print $2}' | tr -d '\r')
export TOKEN DOM; clear
t 'F=https://192.168.100.10/api/fmc_config/v1/domain/$DOM' 0.5
t 'curl -sk -H "X-auth-access-token: $TOKEN" "$F/object/securityzones?expanded=true" | jq -c ".items[] | {name, interfaceMode}"' 4
t 'curl -sk -H "X-auth-access-token: $TOKEN" "$F/devices/devicerecords?expanded=true" | jq ".items[] | {name, hostName, model, sw_version}"' 7
echo "$TOKEN $DOM" > /tmp/tokdom
