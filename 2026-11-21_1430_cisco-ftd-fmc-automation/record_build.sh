#!/bin/bash
# Records the full from-scratch build as an asciinema cast.
cd /root/ftd-automation
cat > /tmp/build_session.sh <<'S'
stty cols 110 rows 34
export PS1='root@gns3-fmc-ftd:~/ftd-automation# '
cd /root/ftd-automation
clear
printf '\033[1;36m%s\033[0m\n\n' "Cisco FTD through FMC - full build from scratch with the FMC REST API"
type_cmd() { printf 'root@gns3-fmc-ftd:~/ftd-automation# '; for ((i=0;i<${#1};i++)); do printf '%s' "${1:$i:1}"; sleep 0.04; done; echo; }
type_cmd "cat lab.yaml"; sleep 0.5; cat lab.yaml; sleep 4
type_cmd "python3 demo.py"; python3 -u demo.py
sleep 3
S
asciinema rec -q --overwrite -i 3 -c "bash /tmp/build_session.sh" logs/build.cast
