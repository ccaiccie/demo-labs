#!/usr/bin/env python3
"""Parse and triage Cisco IOS and ASA RFC 3164 syslog files."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable

FACILITIES: dict[int, str] = {
    0: "kern",
    1: "user",
    2: "mail",
    3: "daemon",
    4: "auth",
    5: "syslog",
    6: "lpr",
    7: "news",
    8: "uucp",
    9: "cron",
    10: "authpriv",
    11: "ftp",
    12: "ntp",
    13: "logaudit",
    14: "logalert",
    15: "clock",
    16: "local0",
    17: "local1",
    18: "local2",
    19: "local3",
    20: "local4",
    21: "local5",
    22: "local6",
    23: "local7",
}

SEVERITIES: dict[int, str] = {
    0: "emerg",
    1: "alert",
    2: "crit",
    3: "err",
    4: "warning",
    5: "notice",
    6: "info",
    7: "debug",
}

SYSLOG_RE = re.compile(
    r"^<(?P<pri>\d{1,3})>"
    r"(?P<timestamp>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    r"\s+\d{1,2}(?:\s+\d{4})?\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?)\s+"
    r"(?P<host>\S+?)(?:\s*:\s*|\s+)"
    r"(?:(?P<tag>%(?P<tag_facility>[A-Z0-9_]+)-(?P<tag_severity>[0-7])-(?P<mnemonic>[A-Z0-9_]+)):\s*)?"
    r"(?P<message>.*)$"
)

LOGIN_FAILED_RE = re.compile(r"\blogin_failed\b", re.IGNORECASE)
BPDU_GUARD_RE = re.compile(r"bpdu[\s_-]*guard", re.IGNORECASE)
ERR_DISABLE_RE = re.compile(r"err[\s_-]*disable", re.IGNORECASE)


@dataclass(frozen=True)
class SyslogEntry:
    """Structured representation of a parsed Cisco syslog line."""

    line_number: int
    pri: int
    facility: int
    facility_name: str
    pri_severity: int
    pri_severity_name: str
    severity: int
    severity_name: str
    timestamp: str
    host: str
    tag: str | None
    tag_facility: str | None
    tag_severity: int | None
    mnemonic: str | None
    message: str


@dataclass(frozen=True)
class AlertItem:
    """A syslog entry flagged for attention along with its trigger reasons."""

    entry: SyslogEntry
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self.entry)
        data["alert_reasons"] = list(self.reasons)
        return data


@dataclass(frozen=True)
class TriageReport:
    """Aggregated syslog parsing and triage results."""

    total_lines: int
    parsed_lines: int
    unparsed_lines: int
    by_severity: dict[int, int]
    by_host: dict[str, int]
    alerts: tuple[AlertItem, ...]
    mismatches: tuple[SyslogEntry, ...]

    def to_dict(self) -> dict[str, Any]:
        severity_summary = [
            {
                "severity": sev,
                "severity_name": SEVERITIES[sev],
                "count": count,
            }
            for sev, count in sorted(self.by_severity.items())
        ]
        sorted_hosts = dict(
            sorted(self.by_host.items(), key=lambda item: (-item[1], item[0]))
        )
        return {
            "total_lines": self.total_lines,
            "parsed_lines": self.parsed_lines,
            "unparsed_lines": self.unparsed_lines,
            "summary": {
                "by_severity": severity_summary,
                "by_host": sorted_hosts,
            },
            "alerts": [alert.to_dict() for alert in self.alerts],
            "mismatches": [asdict(entry) for entry in self.mismatches],
        }


def decode_pri(pri: int) -> tuple[int, str, int, str]:
    """Decode RFC 3164 PRI (0-191) into (facility, facility_name, severity, severity_name)."""
    if not 0 <= pri <= 191:
        raise ValueError(f"RFC 3164 PRI out of range (0-191): {pri}")
    facility = pri // 8
    severity = pri % 8
    return facility, FACILITIES[facility], severity, SEVERITIES[severity]


def parse_line(line: str, line_number: int = 0) -> SyslogEntry | None:
    """Parse a single Cisco IOS/ASA RFC 3164 syslog line, or return None if unparsed."""
    cleaned = line.rstrip("\r\n")
    match = SYSLOG_RE.match(cleaned)
    if not match:
        return None

    pri = int(match.group("pri"))
    try:
        facility, facility_name, pri_severity, pri_severity_name = decode_pri(pri)
    except ValueError:
        return None

    tag = match.group("tag")
    tag_severity_raw = match.group("tag_severity")
    tag_severity = int(tag_severity_raw) if tag_severity_raw is not None else None

    effective_severity = tag_severity if tag_severity is not None else pri_severity
    effective_severity_name = SEVERITIES[effective_severity]

    return SyslogEntry(
        line_number=line_number,
        pri=pri,
        facility=facility,
        facility_name=facility_name,
        pri_severity=pri_severity,
        pri_severity_name=pri_severity_name,
        severity=effective_severity,
        severity_name=effective_severity_name,
        timestamp=match.group("timestamp"),
        host=match.group("host"),
        tag=tag,
        tag_facility=match.group("tag_facility"),
        tag_severity=tag_severity,
        mnemonic=match.group("mnemonic"),
        message=match.group("message"),
    )


def get_alert_reasons(entry: SyslogEntry) -> list[str]:
    """Return all alert reasons matching the given syslog entry."""
    reasons: list[str] = []
    combined = f"{entry.tag or ''} {entry.message}"

    if 0 <= entry.severity <= 3:
        reasons.append("severity<=3")
    if (entry.mnemonic and entry.mnemonic.upper() == "LOGIN_FAILED") or LOGIN_FAILED_RE.search(combined):
        reasons.append("LOGIN_FAILED")
    if BPDU_GUARD_RE.search(combined):
        reasons.append("BPDU_GUARD")
    if ERR_DISABLE_RE.search(combined):
        reasons.append("ERR_DISABLE")

    return reasons


def triage_lines(lines: Iterable[str]) -> TriageReport:
    """Parse an iterable of syslog lines and build a TriageReport."""
    parsed_lines = 0
    unparsed_lines = 0
    severity_counts: Counter[int] = Counter()
    host_counts: Counter[str] = Counter()
    alerts: list[AlertItem] = []
    mismatches: list[SyslogEntry] = []

    for line_number, raw_line in enumerate(lines, start=1):
        if not raw_line.strip():
            continue

        entry = parse_line(raw_line, line_number=line_number)
        if entry is None:
            unparsed_lines += 1
            continue

        parsed_lines += 1
        severity_counts[entry.severity] += 1
        host_counts[entry.host] += 1

        if entry.tag_severity is not None and entry.tag_severity != entry.pri_severity:
            mismatches.append(entry)

        reasons = get_alert_reasons(entry)
        if reasons:
            alerts.append(AlertItem(entry=entry, reasons=tuple(reasons)))

    return TriageReport(
        total_lines=parsed_lines + unparsed_lines,
        parsed_lines=parsed_lines,
        unparsed_lines=unparsed_lines,
        by_severity=dict(severity_counts),
        by_host=dict(host_counts),
        alerts=tuple(alerts),
        mismatches=tuple(mismatches),
    )


def format_text_report(report: TriageReport) -> str:
    """Render a TriageReport as human-readable text."""
    out: list[str] = [
        "Syslog Triage Report",
        "====================",
        f"Total lines:    {report.total_lines}",
        f"Parsed lines:   {report.parsed_lines}",
        f"Unparsed lines: {report.unparsed_lines}",
        "",
        "Summary by Severity",
        "-------------------",
    ]

    if report.by_severity:
        for sev in sorted(report.by_severity):
            label = f"{sev} ({SEVERITIES[sev]})"
            out.append(f"  {label:<12}: {report.by_severity[sev]}")
    else:
        out.append("  (none)")

    out.extend(["", "Summary by Host", "---------------"])
    if report.by_host:
        sorted_hosts = sorted(
            report.by_host.items(), key=lambda item: (-item[1], item[0])
        )
        width = max(len(host) for host, _ in sorted_hosts)
        for host, count in sorted_hosts:
            out.append(f"  {host:<{width}} : {count}")
    else:
        out.append("  (none)")

    out.extend(["", f"ALERTS ({len(report.alerts)})", "-----------"])
    if report.alerts:
        for item in report.alerts:
            e = item.entry
            reason_str = ", ".join(item.reasons)
            tag_prefix = f"{e.tag}: " if e.tag else ""
            out.append(
                f"  [line {e.line_number}] [{e.severity}/{e.severity_name}] "
                f"{e.timestamp} {e.host} {tag_prefix}{e.message} "
                f"(reasons: {reason_str})"
            )
    else:
        out.append("  (none)")

    out.extend(["", f"MISMATCHES ({len(report.mismatches)})", "---------------"])
    if report.mismatches:
        for e in report.mismatches:
            out.append(
                f"  [line {e.line_number}] PRI={e.pri_severity} ({e.pri_severity_name}) "
                f"vs TAG={e.tag_severity} ({e.severity_name}) | "
                f"{e.timestamp} {e.host} {e.tag}: {e.message}"
            )
    else:
        out.append("  (none)")

    return "\n".join(out)


def format_json_report(report: TriageReport) -> str:
    """Render a TriageReport as formatted JSON."""
    return json.dumps(report.to_dict(), indent=2)


def build_parser() -> argparse.ArgumentParser:
    """Construct the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Parse and triage Cisco IOS and ASA RFC 3164 syslog files."
    )
    parser.add_argument(
        "file",
        nargs="?",
        default="-",
        help="Path to the syslog file (use '-' or omit to read from stdin).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output the triage report as JSON.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.file == "-":
        report = triage_lines(sys.stdin)
    else:
        path = Path(args.file)
        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                report = triage_lines(handle)
        except OSError as exc:
            print(f"Error reading {path}: {exc}", file=sys.stderr)
            return 1

    if args.json:
        print(format_json_report(report))
    else:
        print(format_text_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
