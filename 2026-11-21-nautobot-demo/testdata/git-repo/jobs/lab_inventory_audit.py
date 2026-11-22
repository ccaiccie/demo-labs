"""Lab Inventory Audit Job for Nautobot 3.x Git Repository Data Source."""

import ipaddress

from nautobot.apps.jobs import Job
from nautobot.dcim.models import Device


RFC5737_NETWORKS = (
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
)


def is_rfc5737_ip(host_str: str) -> bool:
    """Return True if the given IPv4 address string falls within RFC 5737 TEST-NET ranges."""
    addr = ipaddress.ip_address(host_str)
    return any(addr in net for net in RFC5737_NETWORKS)


class LabInventoryAuditJob(Job):
    """Audit all Active devices for primary IPv4 assignment and RFC 5737 compliance."""

    class Meta:
        name = "Lab Inventory Audit"
        description = (
            "Checks all Active devices for a primary IPv4 address, verifies RFC 5737 "
            "TEST-NET compliance, and logs a summary table to JobResult."
        )
        has_sensitive_variables = False
        read_only = True

    def run(self):
        devices = (
            Device.objects.filter(status__name="Active")
            .select_related("location", "role", "primary_ip4")
            .order_by("name")
        )

        total = 0
        compliant = 0
        missing_ip = 0
        non_rfc5737 = 0
        rows = []

        self.logger.info("Starting Lab Inventory Audit across Active devices.")

        for device in devices:
            total += 1
            location_name = device.location.name if device.location else "unassigned"
            role_name = device.role.name if device.role else "unassigned"

            if not device.primary_ip4:
                missing_ip += 1
                status_label = "MISSING_PRIMARY_IP4"
                ip_display = "-"
                self.logger.warning(
                    "Device %s (%s) has no primary IPv4 address assigned.",
                    device.name,
                    location_name,
                    extra={"object": device},
                )
            else:
                ip_display = str(device.primary_ip4.address)
                host_ip = str(device.primary_ip4.host)
                if is_rfc5737_ip(host_ip):
                    compliant += 1
                    status_label = "PASS_RFC5737"
                    self.logger.info(
                        "Device %s (%s): primary IPv4 %s is RFC 5737 compliant.",
                        device.name,
                        location_name,
                        ip_display,
                        extra={"object": device},
                    )
                else:
                    non_rfc5737 += 1
                    status_label = "FAIL_NON_RFC5737"
                    self.logger.error(
                        "Device %s (%s): primary IPv4 %s is NOT in RFC 5737 ranges.",
                        device.name,
                        location_name,
                        ip_display,
                        extra={"object": device},
                    )

            rows.append((device.name, location_name, role_name, ip_display, status_label))

        header = f"{'Device':<28} {'Location':<16} {'Role':<15} {'Primary IPv4':<18} {'Audit Status'}"
        divider = "-" * len(header)
        table_lines = [header, divider]
        for name, loc, role, ip_val, audit_status in rows:
            table_lines.append(
                f"{name:<28} {loc:<16} {role:<15} {ip_val:<18} {audit_status}"
            )
        summary_line = (
            f"Summary: total={total}, compliant={compliant}, "
            f"missing_primary_ip4={missing_ip}, non_rfc5737={non_rfc5737}"
        )
        table_lines.append(divider)
        table_lines.append(summary_line)

        report = "\n".join(table_lines)
        self.logger.info("Lab Inventory Audit Summary:\n%s", report)
        return summary_line
