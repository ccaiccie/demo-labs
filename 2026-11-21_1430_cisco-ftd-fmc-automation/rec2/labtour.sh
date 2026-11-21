source /root/ftd-automation/rec2/common.sh; clear
export PRJ=de7d9431-b330-40a8-b382-13aeb18ed3b8
t 'curl -s http://127.0.0.1:3080/v2/projects/$PRJ/nodes | jq -r ".[] | [.name, .node_type, .status] | @tsv" | column -t' 4
t 'ip -br addr show br-mgmt; ip -br addr show br-outside' 4
t 'docker ps --format "table {{.Image}}\t{{.Status}}\t{{.Names}}" | cut -c1-100' 5
