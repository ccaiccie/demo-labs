stty cols 110 rows 34 2>/dev/null
export PS1='root@gns3-fmc-ftd:~/ftd-automation# '
cd /root/ftd-automation
P='root@gns3-fmc-ftd:~/ftd-automation# '
t() { printf '%s' "$P"; for ((i=0;i<${#1};i++)); do printf '%s' "${1:$i:1}"; sleep 0.03; done; echo; sleep 0.4; eval "$1"; sleep ${2:-2.5}; }
