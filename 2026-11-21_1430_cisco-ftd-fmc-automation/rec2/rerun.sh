source /root/ftd-automation/rec2/common.sh; clear
printf '\033[1;36m%s\033[0m\n\n' "Second run against the finished setup - nothing should be duplicated"
t 'python3 -u demo.py' 3
