source /root/ftd-automation/rec2/common.sh; read TOKEN DOM < /tmp/tokdom; export TOKEN DOM F=https://192.168.100.10/api/fmc_config/v1/domain/$DOM; clear
t 'ACP=$(curl -sk -H "X-auth-access-token: $TOKEN" "$F/policy/accesspolicies" | jq -r ".items[] | select(.name==\"Demo-ACP\") | .id")' 0.5
t 'curl -sk -H "X-auth-access-token: $TOKEN" "$F/policy/accesspolicies/$ACP/accessrules?expanded=true" | jq ".items[0] | {name, action, sourceZones: .sourceZones.objects, destinationZones: .destinationZones.objects}"' 8
