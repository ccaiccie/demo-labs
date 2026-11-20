#!/usr/bin/env python3
"""Audit Cisco IOS device configurations against baseline security rules."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any

SEVERITY_CRITICAL = "CRITICAL"
SEVERITY_HIGH = "HIGH"
SEVERITY_MEDIUM = "MEDIUM"
SEVERITY_LOW = "LOW"
SEVERITY_ORDER: dict[str, int] = {
    "CRITICAL": 0,
    "HIGH": 1,
    "MEDIUM": 2,
    "LOW": 3,
}

DEFAULT_SNMP_COMMUNITIES = frozenset({"public", "private"})

HOSTNAME_RE = re.compile(r"^hostname\s+(\S+)", re.IGNORECASE)
LINE_HEADER_RE = re.compile(r"^line\s+", re.IGNORECASE)

TRANSPORT_INPUT_RE = re.compile(
    r"^transport\s+input(?:\s+(?P<tokens>.*))?$", re.IGNORECASE
)
NO_TRANSPORT_INPUT_RE = re.compile(r"^no\s+transport\s+input\b", re.IGNORECASE)

EXEC_TIMEOUT_RE = re.compile(r"^exec-timeout\s+(\d+)(?:\s+(\d+))?$", re.IGNORECASE)
NO_EXEC_TIMEOUT_RE = re.compile(r"^no\s+exec-timeout\b", re.IGNORECASE)

PASSWORD_ENC_ON_RE = re.compile(r"^service\s+password-encryption\b", re.IGNORECASE)
PASSWORD_ENC_OFF_RE = re.compile(r"^no\s+service\s+password-encryption\b", re.IGNORECASE)

SNMP_COMMUNITY_RE = re.compile(
    r"^snmp-server\s+community\s+(?P<community>\S+)(?:\s+(?P<rest>.*))?$",
    re.IGNORECASE,
)
NO_SNMP_COMMUNITY_RE = re.compile(
    r"^no\s+snmp-server\s+community\s+(?P<community>\S+)", re.IGNORECASE
)

HTTP_SERVER_ON_RE = re.compile(r"^ip\s+http\s+server(?:\s|$)", re.IGNORECASE)
HTTP_SERVER_OFF_RE = re.compile(r"^no\s+ip\s+http\s+server(?:\s|$)", re.IGNORECASE)

ENABLE_PASSWORD_ON_RE = re.compile(r"^enable\s+password\b", re.IGNORECASE)
ENABLE_PASSWORD_OFF_RE = re.compile(r"^no\s+enable\s+password\b", re.IGNORECASE)
ENABLE_SECRET_ON_RE = re.compile(r"^enable\s+secret\b", re.IGNORECASE)
ENABLE_SECRET_OFF_RE = re.compile(r"^no\s+enable\s+secret\b", re.IGNORECASE)


@dataclass(frozen=True)
class Finding:
    """A single security audit finding produced from configuration analysis."""

    rule_id: str
    title: str
    severity: str
    section: str
    line_number: int | None
    evidence: str
    description: str
    remediation: str

    def to_dict(self) -> dict[str, Any]:
        """Convert the finding to a JSON-serializable dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class AuditReport:
    """Aggregated security audit results for a Cisco IOS configuration."""

    source: str
    hostname: str | None
    findings: tuple[Finding, ...]
    severity_counts: dict[str, int]

    @property
    def total_findings(self) -> int:
        """Total number of findings in the report."""
        return len(self.findings)

    @property
    def passed(self) -> bool:
        """True when the configuration produced zero findings."""
        return len(self.findings) == 0

    def to_dict(self) -> dict[str, Any]:
        """Convert the audit report to a JSON-serializable dictionary."""
        return {
            "source": self.source,
            "hostname": self.hostname,
            "passed": self.passed,
            "total_findings": self.total_findings,
            "severity_counts": dict(self.severity_counts),
            "findings": [finding.to_dict() for finding in self.findings],
        }


@dataclass
class _LineBlock:
    """Mutable directive state tracked inside a single 'line ...' block."""

    header: str
    header_line: int
    transport_input: tuple[int, str, tuple[str, ...]] | None = None
    exec_timeout_compliant: bool = False
    exec_timeout_directive: tuple[int, str] | None = None


def extract_hostname(text: str) -> str | None:
    """Extract the top-level IOS hostname from configuration text."""
    for raw_line in text.splitlines():
        if not raw_line or raw_line[0].isspace():
            continue
        match = HOSTNAME_RE.match(raw_line.rstrip())
        if match:
            return match.group(1)
    return None


def _parse_line_directive(block: _LineBlock, line_number: int, stripped: str) -> None:
    """Update a line block's tracked directives from a single indented child line."""
    if NO_TRANSPORT_INPUT_RE.match(stripped):
        block.transport_input = None
        return

    transport_match = TRANSPORT_INPUT_RE.match(stripped)
    if transport_match:
        raw_tokens = transport_match.group("tokens") or ""
        tokens = tuple(tok.lower() for tok in raw_tokens.split())
        block.transport_input = (line_number, stripped, tokens)
        return

    if NO_EXEC_TIMEOUT_RE.match(stripped):
        block.exec_timeout_compliant = False
        block.exec_timeout_directive = (line_number, stripped)
        return

    timeout_match = EXEC_TIMEOUT_RE.match(stripped)
    if timeout_match:
        minutes = int(timeout_match.group(1))
        seconds = int(timeout_match.group(2)) if timeout_match.group(2) is not None else 0
        block.exec_timeout_compliant = minutes > 0 or seconds > 0
        block.exec_timeout_directive = (line_number, stripped)


def _evaluate_line_block(block: _LineBlock, findings: list[Finding]) -> None:
    """Evaluate TELNET_ENABLED and MISSING_EXEC_TIMEOUT for a parsed line block."""
    if block.transport_input is not None:
        directive_line, evidence, tokens = block.transport_input
        if "telnet" in tokens or "all" in tokens:
            findings.append(
                Finding(
                    rule_id="TELNET_ENABLED",
                    title="Telnet enabled on line",
                    severity=SEVERITY_HIGH,
                    section=block.header,
                    line_number=directive_line,
                    evidence=evidence,
                    description=(
                        f"Unencrypted Telnet input transport is permitted on "
                        f"'{block.header}' ({evidence}), exposing credentials and "
                        f"management sessions to interception."
                    ),
                    remediation=(
                        "Restrict line transport to SSH only using 'transport input ssh' "
                        "(or 'transport input none' if unused)."
                    ),
                )
            )

    if not block.exec_timeout_compliant:
        if block.exec_timeout_directive is not None:
            directive_line, evidence = block.exec_timeout_directive
            description = (
                f"EXEC session timeout is disabled on '{block.header}' ({evidence}), "
                f"allowing idle sessions to remain open indefinitely."
            )
        else:
            directive_line = block.header_line
            evidence = f"{block.header} (no exec-timeout configured)"
            description = (
                f"No EXEC session timeout is configured on '{block.header}', "
                f"leaving idle sessions without an explicit timeout."
            )

        findings.append(
            Finding(
                rule_id="MISSING_EXEC_TIMEOUT",
                title="EXEC session timeout missing or disabled",
                severity=SEVERITY_MEDIUM,
                section=block.header,
                line_number=directive_line,
                evidence=evidence,
                description=description,
                remediation=(
                    "Configure a non-zero EXEC idle timeout on the line "
                    "(for example, 'exec-timeout 10 0')."
                ),
            )
        )


def _finding_sort_key(finding: Finding) -> tuple[int, int, str, str]:
    """Return deterministic sort key for audit findings."""
    return (
        SEVERITY_ORDER[finding.severity],
        finding.line_number if finding.line_number is not None else 10**9,
        finding.rule_id,
        finding.section,
    )


def audit_config(text: str, *, source: str = "<string>") -> AuditReport:
    """Audit Cisco IOS configuration text against all baseline security rules."""
    hostname = extract_hostname(text)

    line_blocks: list[_LineBlock] = []
    current_block: _LineBlock | None = None

    password_encryption_enabled = False
    password_encryption_negation: tuple[int, str] | None = None

    active_communities: dict[str, tuple[int, str, str | None]] = {}
    http_server_enabled: tuple[int, str] | None = None
    enable_password: tuple[int, str] | None = None
    enable_secret_active = False

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped:
            continue

        if stripped.startswith("!"):
            current_block = None
            continue

        if raw_line[0].isspace():
            if current_block is not None:
                _parse_line_directive(current_block, line_number, stripped)
            continue

        current_block = None

        if LINE_HEADER_RE.match(raw_line):
            current_block = _LineBlock(header=stripped, header_line=line_number)
            line_blocks.append(current_block)
            continue

        if PASSWORD_ENC_ON_RE.match(stripped):
            password_encryption_enabled = True
            password_encryption_negation = None
            continue

        if PASSWORD_ENC_OFF_RE.match(stripped):
            password_encryption_enabled = False
            password_encryption_negation = (line_number, stripped)
            continue

        snmp_match = SNMP_COMMUNITY_RE.match(stripped)
        if snmp_match:
            community = snmp_match.group("community")
            rest = snmp_match.group("rest")
            active_communities[community] = (line_number, stripped, rest)
            continue

        no_snmp_match = NO_SNMP_COMMUNITY_RE.match(stripped)
        if no_snmp_match:
            active_communities.pop(no_snmp_match.group("community"), None)
            continue

        if HTTP_SERVER_ON_RE.match(stripped):
            http_server_enabled = (line_number, stripped)
            continue

        if HTTP_SERVER_OFF_RE.match(stripped):
            http_server_enabled = None
            continue

        if ENABLE_PASSWORD_ON_RE.match(stripped):
            enable_password = (line_number, stripped)
            continue

        if ENABLE_PASSWORD_OFF_RE.match(stripped):
            enable_password = None
            continue

        if ENABLE_SECRET_ON_RE.match(stripped):
            enable_secret_active = True
            continue

        if ENABLE_SECRET_OFF_RE.match(stripped):
            enable_secret_active = False
            continue

    findings: list[Finding] = []

    for block in line_blocks:
        _evaluate_line_block(block, findings)

    if not password_encryption_enabled:
        if password_encryption_negation is not None:
            enc_line, enc_evidence = password_encryption_negation
            enc_description = (
                "Global password encryption is explicitly disabled "
                "('no service password-encryption'), leaving type 0 passwords "
                "stored in cleartext."
            )
        else:
            enc_line = None
            enc_evidence = "service password-encryption is not configured"
            enc_description = (
                "Global password encryption ('service password-encryption') is not "
                "configured, leaving local or line passwords potentially stored in cleartext."
            )
        findings.append(
            Finding(
                rule_id="NO_PASSWORD_ENCRYPTION",
                title="Password encryption disabled",
                severity=SEVERITY_MEDIUM,
                section="global",
                line_number=enc_line,
                evidence=enc_evidence,
                description=enc_description,
                remediation="Enable password encryption globally with 'service password-encryption'.",
            )
        )

    for community, (snmp_line, snmp_evidence, rest) in active_communities.items():
        if community.lower() not in DEFAULT_SNMP_COMMUNITIES:
            continue
        rest_tokens = (rest or "").upper().split()
        is_rw = "RW" in rest_tokens
        severity = SEVERITY_CRITICAL if is_rw else SEVERITY_HIGH
        access_desc = " with read-write (RW) privileges" if is_rw else ""
        findings.append(
            Finding(
                rule_id="SNMP_DEFAULT_COMMUNITY",
                title="Default SNMP community string configured",
                severity=severity,
                section="global",
                line_number=snmp_line,
                evidence=snmp_evidence,
                description=(
                    f"Default SNMP community '{community}' is configured{access_desc}, "
                    f"exposing the device via well-known credentials."
                ),
                remediation=(
                    f"Remove the default community with 'no snmp-server community {community}' "
                    f"and migrate to SNMPv3 with authentication and encryption."
                ),
            )
        )

    if http_server_enabled is not None:
        http_line, http_evidence = http_server_enabled
        findings.append(
            Finding(
                rule_id="HTTP_SERVER_ENABLED",
                title="Unencrypted HTTP management server enabled",
                severity=SEVERITY_HIGH,
                section="global",
                line_number=http_line,
                evidence=http_evidence,
                description=(
                    "The unencrypted HTTP management server ('ip http server') is enabled, "
                    "transmitting administrative sessions and credentials in cleartext."
                ),
                remediation=(
                    "Disable the HTTP server with 'no ip http server' and use "
                    "'ip http secure-server' if web management is required."
                ),
            )
        )

    if enable_password is not None:
        ep_line, ep_evidence = enable_password
        if enable_secret_active:
            ep_description = (
                "Legacy 'enable password' is configured alongside 'enable secret'; "
                "although 'enable secret' takes precedence, the weakly obfuscated "
                "'enable password' remains exposed in the configuration."
            )
        else:
            ep_description = (
                "Legacy 'enable password' is configured without 'enable secret'; "
                "cleartext and type 7 enable passwords are trivially reversible."
            )
        findings.append(
            Finding(
                rule_id="ENABLE_PASSWORD_INSECURE",
                title="Insecure enable password configured",
                severity=SEVERITY_HIGH,
                section="global",
                line_number=ep_line,
                evidence=ep_evidence,
                description=ep_description,
                remediation=(
                    "Remove 'enable password' with 'no enable password' and ensure "
                    "a strong 'enable secret' is configured."
                ),
            )
        )

    sorted_findings = tuple(sorted(findings, key=_finding_sort_key))
    severity_counts: dict[str, int] = {sev: 0 for sev in SEVERITY_ORDER}
    for finding in sorted_findings:
        severity_counts[finding.severity] += 1

    return AuditReport(
        source=source,
        hostname=hostname,
        findings=sorted_findings,
        severity_counts=severity_counts,
    )


def audit_file(path: str | Path) -> AuditReport:
    """Read a Cisco IOS configuration file and audit it against baseline security rules."""
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8", errors="replace")
    return audit_config(text, source=str(path))


def format_text_audit(report: AuditReport) -> str:
    """Render an AuditReport as human-readable text."""
    status = "PASS" if report.passed else "FAIL"
    out: list[str] = [
        "Security Audit Report",
        "=====================",
        f"Source:         {report.source}",
        f"Hostname:       {report.hostname or '(unknown)'}",
        f"Status:         {status}",
        f"Total findings: {report.total_findings}",
        "",
        "Summary by Severity",
        "-------------------",
    ]

    for sev in SEVERITY_ORDER:
        out.append(f"  {sev:<8}: {report.severity_counts.get(sev, 0)}")

    header = f"FINDINGS ({report.total_findings})"
    out.extend(["", header, "-" * len(header)])
    if report.findings:
        for finding in report.findings:
            line_label = (
                f"line {finding.line_number}"
                if finding.line_number is not None
                else "not configured"
            )
            out.append(
                f"  [{finding.severity}] {finding.rule_id} "
                f"({finding.section}, {line_label}): {finding.title}"
            )
            out.append(f"    Evidence:    {finding.evidence}")
            out.append(f"    Description: {finding.description}")
            out.append(f"    Remediation: {finding.remediation}")
    else:
        out.append("  (none)")

    return "\n".join(out)


def format_json_audit(report: AuditReport) -> str:
    """Render an AuditReport as formatted JSON."""
    return json.dumps(report.to_dict(), indent=2)


def build_parser() -> argparse.ArgumentParser:
    """Construct the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Audit a Cisco IOS configuration file against baseline security rules."
    )
    parser.add_argument(
        "config",
        help="Path to the Cisco IOS configuration file to audit.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output the audit report as JSON.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        report = audit_file(args.config)
    except OSError as exc:
        print(f"Error reading {args.config}: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(format_json_audit(report))
    else:
        print(format_text_audit(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
