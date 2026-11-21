source /root/ftd-automation/rec2/common.sh; clear
t 'source /root/lab-secrets.env' 1
t 'curl -sk -X POST -u "admin:$LAB_ADMIN_PW" https://192.168.100.10/api/fmc_platform/v1/auth/generatetoken -D - -o /dev/null | grep -iE "^(x-auth|domain_uuid)" | sed -E "s/(token: ).*/\1<masked>/I"' 6
