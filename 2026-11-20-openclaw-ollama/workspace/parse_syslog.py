import sys
import json
from collections import defaultdict

def parse_syslog(log_file):
    device_events = defaultdict(int)
    severity_counts = defaultdict(int)
    ssh_auth_fail = defaultdict(int)
    ssh_auth_fail_per_device = defaultdict(int)

    with open(log_file, 'r') as file:
        for line in file:
            parts = line.strip().split(' ', 3)
            timestamp, device, severity, message = parts

            device_events[device] += 1
            severity_counts[severity] += 1

            if 'SSH_AUTH_FAIL' in message:
                ssh_auth_fail[device] += 1
                ssh_auth_fail_per_device[device] += 1

    return {
        "total_events_per_device": dict(device_events),
        "events_per_severity": dict(severity_counts),
        "total_ssh_auth_fail": dict(ssh_auth_fail),
        "ssh_auth_fail_per_device": dict(ssh_auth_fail_per_device)
    }

if __name__ == '__main__':
    log_file = 'network_syslog.log'
    result = parse_syslog(log_file)
    with open('summary.json', 'w') as json_file:
        json.dump(result, json_file, indent=4)
    print("Results written to summary.json")
    print(json.dumps(result, indent=4))
