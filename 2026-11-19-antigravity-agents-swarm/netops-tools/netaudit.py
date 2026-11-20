#!/usr/bin/env python3
"""Combine Cisco configuration diff and baseline-aware security audit reports."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import html
import json
from pathlib import Path
import sys
from typing import Any

import config_diff
import security_audit

SEVERITY_LEVELS: tuple[str, ...] = (
    security_audit.SEVERITY_CRITICAL,
    security_audit.SEVERITY_HIGH,
    security_audit.SEVERITY_MEDIUM,
    security_audit.SEVERITY_LOW,
)

_ADD_OPS = frozenset({"+", "add", "added", "insert"})
_DEL_OPS = frozenset({"-", "del", "delete", "remove", "removed"})


@dataclass(frozen=True)
class CombinedAuditResult:
    """Unified result of a configuration diff and before/after security audit."""

    before_path: str
    after_path: str
    hostname: str | None
    generated_at: str
    diff: config_diff.ConfigDiff
    before_audit: security_audit.AuditReport
    after_audit: security_audit.AuditReport
    new_findings: tuple[security_audit.Finding, ...]
    existing_findings: tuple[security_audit.Finding, ...]
    resolved_findings: tuple[security_audit.Finding, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable summary of the combined audit."""
        return {
            "before_path": self.before_path,
            "after_path": self.after_path,
            "hostname": self.hostname,
            "generated_at": self.generated_at,
            "diff": self.diff.to_dict(),
            "before_audit": self.before_audit.to_dict(),
            "after_audit": self.after_audit.to_dict(),
            "new_findings": [finding.to_dict() for finding in self.new_findings],
            "existing_findings": [
                finding.to_dict() for finding in self.existing_findings
            ],
            "resolved_findings": [
                finding.to_dict() for finding in self.resolved_findings
            ],
        }


def finding_key(finding: security_audit.Finding) -> tuple[str, str, str]:
    """Return a line-number-independent key identifying a security finding."""
    return (finding.rule_id, finding.section, finding.evidence)


def run_audit(
    before_path: str | Path,
    after_path: str | Path,
    *,
    generated_at: str | None = None,
) -> CombinedAuditResult:
    """Diff two configuration files and compare their security audit findings."""
    diff = config_diff.diff_files(before_path, after_path)
    before_audit = security_audit.audit_file(before_path)
    after_audit = security_audit.audit_file(after_path)

    hostname = after_audit.hostname or before_audit.hostname
    if generated_at is None:
        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    before_keys = {finding_key(finding) for finding in before_audit.findings}
    after_keys = {finding_key(finding) for finding in after_audit.findings}

    new_findings = tuple(
        finding
        for finding in after_audit.findings
        if finding_key(finding) not in before_keys
    )
    existing_findings = tuple(
        finding
        for finding in after_audit.findings
        if finding_key(finding) in before_keys
    )
    resolved_findings = tuple(
        finding
        for finding in before_audit.findings
        if finding_key(finding) not in after_keys
    )

    return CombinedAuditResult(
        before_path=str(before_path),
        after_path=str(after_path),
        hostname=hostname,
        generated_at=generated_at,
        diff=diff,
        before_audit=before_audit,
        after_audit=after_audit,
        new_findings=new_findings,
        existing_findings=existing_findings,
        resolved_findings=resolved_findings,
    )


def default_report_path(
    before_path: str | Path,
    after_path: str | Path,
    output_dir: str | Path = "reports",
) -> Path:
    """Return the default HTML report path for a before/after config pair."""
    before_stem = Path(before_path).stem
    after_stem = Path(after_path).stem
    return Path(output_dir) / f"{before_stem}_vs_{after_stem}.html"


def _esc(value: object) -> str:
    """Escape any value for safe HTML5 text or attribute interpolation."""
    return html.escape(str(value), quote=True)


def _severity_class(severity: str) -> str:
    """Map a severity string to a safe CSS class suffix."""
    mapping = {
        security_audit.SEVERITY_CRITICAL: "critical",
        security_audit.SEVERITY_HIGH: "high",
        security_audit.SEVERITY_MEDIUM: "medium",
        security_audit.SEVERITY_LOW: "low",
    }
    return mapping.get(severity.upper(), "unknown")


def _status_class(status: str) -> str:
    """Map a diff section status string to a safe CSS class suffix."""
    mapping = {
        "ADDED": "added",
        "REMOVED": "removed",
        "MODIFIED": "modified",
    }
    return mapping.get(status.upper(), "modified")


def _is_changed_section(section: Any) -> bool:
    """Return True if a SectionDiff represents an added, removed, or modified section."""
    status = str(getattr(section, "status", "MODIFIED")).upper()
    return status != "UNCHANGED"


def _section_header(section: Any) -> str:
    """Extract a readable header string from a SectionDiff object."""
    for attr in ("header", "name", "section", "title"):
        value = getattr(section, attr, None)
        if isinstance(value, str) and value:
            return value
    return "(section)"


def _normalize_op(raw_op: Any) -> str:
    """Normalize a diff operation indicator to '+', '-', or ' '."""
    op = str(raw_op).strip().lower()
    if op in _ADD_OPS:
        return "+"
    if op in _DEL_OPS:
        return "-"
    return " "


def _parse_diff_item(item: Any) -> tuple[str, str]:
    """Convert a diff line entry (str, tuple, or object) to (op, display_line)."""
    if isinstance(item, str):
        if item.startswith("+"):
            return ("+", item)
        if item.startswith("-"):
            return ("-", item)
        if item.startswith(" "):
            return (" ", item)
        return (" ", f"  {item}")

    if isinstance(item, tuple) and len(item) >= 2:
        op = _normalize_op(item[0])
        return (op, f"{op} {item[1]}")

    for op_attr in ("kind", "op", "tag", "status", "change_type", "prefix", "sign", "type"):
        raw_op = getattr(item, op_attr, None)
        if raw_op is not None:
            op = _normalize_op(raw_op)
            for text_attr in ("line", "text", "content", "value"):
                text = getattr(item, text_attr, None)
                if text is not None:
                    return (op, f"{op} {text}")

    return (" ", f"  {item}")


def _extract_section_diff_lines(section: Any) -> list[tuple[str, str]]:
    """Extract (op, display_line) pairs from a SectionDiff across field conventions."""
    for attr in ("diff_lines", "changes"):
        items = getattr(section, attr, None)
        if items:
            return [_parse_diff_item(item) for item in items]

    lines = getattr(section, "lines", None)
    if isinstance(lines, (list, tuple)) and lines:
        if not all(isinstance(item, str) for item in lines):
            return [_parse_diff_item(item) for item in lines]
        if any(item.startswith(("+", "-")) for item in lines):
            return [_parse_diff_item(item) for item in lines]

    removed_lines: Any = None
    for attr in ("removed_lines", "removed"):
        candidate = getattr(section, attr, None)
        if isinstance(candidate, (list, tuple)) and candidate:
            removed_lines = candidate
            break

    added_lines: Any = None
    for attr in ("added_lines", "added"):
        candidate = getattr(section, attr, None)
        if isinstance(candidate, (list, tuple)) and candidate:
            added_lines = candidate
            break

    if removed_lines is not None or added_lines is not None:
        result: list[tuple[str, str]] = []
        for line in removed_lines or ():
            result.append(("-", f"- {line}"))
        for line in added_lines or ():
            result.append(("+", f"+ {line}"))
        return result

    if isinstance(lines, (list, tuple)) and lines:
        status = str(getattr(section, "status", "MODIFIED")).upper()
        if status == "ADDED":
            return [("+", f"+ {line}") for line in lines]
        if status == "REMOVED":
            return [("-", f"- {line}") for line in lines]
        return [(" ", f"  {line}") for line in lines]

    before_lines = getattr(section, "before_lines", None)
    after_lines = getattr(section, "after_lines", None)
    if isinstance(before_lines, (list, tuple)) or isinstance(after_lines, (list, tuple)):
        before_seq = list(before_lines or ())
        after_seq = list(after_lines or ())
        before_set = set(before_seq)
        after_set = set(after_seq)
        fallback: list[tuple[str, str]] = []
        for line in before_seq:
            if line not in after_set:
                fallback.append(("-", f"- {line}"))
        for line in after_seq:
            if line not in before_set:
                fallback.append(("+", f"+ {line}"))
            else:
                fallback.append((" ", f"  {line}"))
        return fallback

    return []


def _grouped_changed_sections(
    diff: config_diff.ConfigDiff,
) -> dict[str, list[Any]]:
    """Return changed SectionDiff objects grouped by category."""
    grouped_raw = diff.by_category()
    grouped: dict[str, list[Any]] = {}
    for category, sections in grouped_raw.items():
        changed = [section for section in sections if _is_changed_section(section)]
        if changed:
            grouped[category] = changed

    if not grouped and diff.sections:
        for section in diff.sections:
            if _is_changed_section(section):
                category = str(getattr(section, "category", "other"))
                grouped.setdefault(category, []).append(section)

    return grouped


def _format_line_label(line_number: int | None, *, capitalize: bool = False) -> str:
    """Format an optional finding line number for display."""
    prefix = "Line" if capitalize else "line"
    if line_number is None:
        return f"{prefix} N/A"
    return f"{prefix} {line_number}"


def _finding_sort_key(
    finding: security_audit.Finding,
    *,
    is_new: bool = False,
) -> tuple[int, int, int, str]:
    """Return a deterministic sort key handling optional line numbers."""
    return (
        security_audit.SEVERITY_ORDER.get(finding.severity, 99),
        0 if is_new else 1,
        finding.line_number if finding.line_number is not None else sys.maxsize,
        finding.rule_id,
    )


def _render_finding_card(
    finding: security_audit.Finding,
    status_label: str,
    status_css: str,
) -> str:
    """Render a single security finding card as HTML."""
    sev_css = _severity_class(finding.severity)
    line_label = _format_line_label(finding.line_number, capitalize=True)
    return (
        f'<article class="finding-card finding-sev-{sev_css}">\n'
        '  <div class="finding-top">\n'
        '    <div class="finding-badges">\n'
        f'      <span class="badge badge-sev badge-sev-{sev_css}">{_esc(finding.severity)}</span>\n'
        f'      <span class="badge {status_css}">{_esc(status_label)}</span>\n'
        f'      <span class="rule-id">{_esc(finding.rule_id)}</span>\n'
        "    </div>\n"
        '    <div class="finding-location">'
        f'{_esc(line_label)} &middot; Section: <code>{_esc(finding.section)}</code>'
        "</div>\n"
        "  </div>\n"
        f'  <h3 class="finding-title">{_esc(finding.title)}</h3>\n'
        f'  <pre class="evidence-block"><code>{_esc(finding.evidence)}</code></pre>\n'
        f'  <p class="finding-desc">{_esc(finding.description)}</p>\n'
        f'  <p class="finding-remediation"><strong>Remediation:</strong> {_esc(finding.remediation)}</p>\n'
        "</article>"
    )


def _render_diff_section(result: CombinedAuditResult) -> str:
    """Render the Configuration Diff section of the HTML report."""
    if not result.diff.has_changes:
        return (
            '<div class="banner banner-neutral">'
            "No configuration differences detected."
            "</div>"
        )

    grouped = _grouped_changed_sections(result.diff)
    if not grouped:
        return (
            '<div class="banner banner-neutral">'
            "No configuration differences detected."
            "</div>"
        )

    category_blocks: list[str] = []
    for category, sections in grouped.items():
        section_cards: list[str] = []
        for section in sections:
            status = str(getattr(section, "status", "MODIFIED")).upper()
            status_css = _status_class(status)
            header = _section_header(section)
            diff_lines = _extract_section_diff_lines(section)
            line_html: list[str] = []
            for op, display_line in diff_lines:
                if op == "+":
                    line_cls = "diff-add"
                elif op == "-":
                    line_cls = "diff-del"
                else:
                    line_cls = "diff-ctx"
                line_html.append(
                    f'<span class="diff-line {line_cls}">{_esc(display_line)}</span>'
                )
            lines_content = (
                "".join(line_html)
                if line_html
                else '<span class="diff-line diff-ctx">  (no line-level details)</span>'
            )
            section_cards.append(
                '<div class="diff-card">\n'
                '  <div class="diff-card-header">\n'
                f'    <span class="badge badge-status badge-status-{status_css}">{_esc(status)}</span>\n'
                f'    <code class="section-name">{_esc(header)}</code>\n'
                "  </div>\n"
                f'  <div class="diff-lines">{lines_content}</div>\n'
                "</div>"
            )

        category_blocks.append(
            '<div class="diff-category">\n'
            f'  <h3 class="category-heading">{_esc(category)}</h3>\n'
            f'  {"".join(section_cards)}\n'
            "</div>"
        )

    return "\n".join(category_blocks)


_HTML_CSS = """\
:root {
  --bg: #f8fafc;
  --surface: #ffffff;
  --border: #e2e8f0;
  --text: #0f172a;
  --muted: #475569;
  --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
  --sans: system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  padding: 24px;
  font-family: var(--sans);
  background: var(--bg);
  color: var(--text);
  line-height: 1.5;
}
.container {
  max-width: 1120px;
  margin: 0 auto;
}
.report-header {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 20px 24px;
  margin-bottom: 20px;
}
.report-header h1 {
  margin: 0 0 12px 0;
  font-size: 1.5rem;
}
.meta-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 8px 20px;
  font-size: 0.9rem;
  color: var(--muted);
}
.meta-item strong { color: var(--text); }
code {
  font-family: var(--mono);
  font-size: 0.85em;
  background: #f1f5f9;
  padding: 1px 5px;
  border-radius: 4px;
}
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
  margin-bottom: 24px;
}
.kpi-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 14px 16px;
}
.kpi-label {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--muted);
  margin-bottom: 4px;
}
.kpi-value {
  font-size: 1.4rem;
  font-weight: 700;
}
.kpi-add { color: #15803d; }
.kpi-del { color: #b91c1c; }
.kpi-critical { color: #b91c1c; }
.kpi-high { color: #c2410c; }
.kpi-medium { color: #b45309; }
.kpi-low { color: #1d4ed8; }
.section-block {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 20px 24px;
  margin-bottom: 20px;
}
.section-block h2 {
  margin: 0 0 16px 0;
  font-size: 1.2rem;
  border-bottom: 1px solid var(--border);
  padding-bottom: 8px;
}
.banner {
  padding: 14px 16px;
  border-radius: 8px;
  font-weight: 600;
}
.banner-pass {
  background: #dcfce7;
  color: #166534;
  border: 1px solid #86efac;
}
.banner-neutral {
  background: #f1f5f9;
  color: #334155;
  border: 1px solid #cbd5e1;
}
.finding-card {
  border: 1px solid var(--border);
  border-left-width: 4px;
  border-radius: 8px;
  padding: 14px 16px;
  margin-bottom: 12px;
  background: #ffffff;
}
.finding-sev-critical { border-left-color: #dc2626; }
.finding-sev-high { border-left-color: #ea580c; }
.finding-sev-medium { border-left-color: #d97706; }
.finding-sev-low { border-left-color: #2563eb; }
.finding-sev-unknown { border-left-color: #64748b; }
.finding-top {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.finding-badges {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.finding-location {
  font-size: 0.85rem;
  color: var(--muted);
}
.rule-id {
  font-family: var(--mono);
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--muted);
}
.finding-title {
  margin: 4px 0 8px 0;
  font-size: 1rem;
}
.evidence-block {
  margin: 0 0 8px 0;
  padding: 8px 10px;
  background: #0f172a;
  color: #f8fafc;
  border-radius: 6px;
  overflow-x: auto;
  font-family: var(--mono);
  font-size: 0.85rem;
}
.evidence-block code {
  background: transparent;
  padding: 0;
  color: inherit;
}
.finding-desc {
  margin: 0 0 6px 0;
  font-size: 0.92rem;
}
.finding-remediation {
  margin: 0;
  font-size: 0.9rem;
  color: #334155;
}
.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}
.badge-sev-critical { background: #fee2e2; color: #991b1b; }
.badge-sev-high { background: #ffedd5; color: #9a3412; }
.badge-sev-medium { background: #fef3c7; color: #92400e; }
.badge-sev-low { background: #dbeafe; color: #1e40af; }
.badge-sev-unknown { background: #e2e8f0; color: #334155; }
.badge-new { background: #dc2626; color: #ffffff; }
.badge-existing { background: #e2e8f0; color: #334155; }
.badge-resolved { background: #16a34a; color: #ffffff; }
.badge-status-added { background: #dcfce7; color: #166534; }
.badge-status-removed { background: #fee2e2; color: #991b1b; }
.badge-status-modified { background: #dbeafe; color: #1e40af; }
.resolved-block {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px dashed var(--border);
}
.resolved-block h3 {
  margin: 0 0 12px 0;
  font-size: 1.05rem;
  color: #166534;
}
.diff-category {
  margin-bottom: 18px;
}
.category-heading {
  margin: 0 0 10px 0;
  font-size: 1rem;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.diff-card {
  border: 1px solid var(--border);
  border-radius: 8px;
  margin-bottom: 10px;
  overflow: hidden;
}
.diff-card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: #f8fafc;
  border-bottom: 1px solid var(--border);
}
.section-name {
  font-weight: 600;
  background: transparent;
}
.diff-lines {
  font-family: var(--mono);
  font-size: 0.84rem;
  background: #0f172a;
  color: #e2e8f0;
  overflow-x: auto;
}
.diff-line {
  display: block;
  padding: 1px 12px;
  white-space: pre;
}
.diff-add {
  background: #052e16;
  color: #86efac;
}
.diff-del {
  background: #450a0a;
  color: #fca5a5;
}
.diff-ctx {
  color: #cbd5e1;
}
"""


def render_html_report(result: CombinedAuditResult) -> str:
    """Render a self-contained HTML5 report for a CombinedAuditResult."""
    hostname_display = result.hostname or "unknown"
    changed_sections_count = sum(
        1 for section in result.diff.sections if _is_changed_section(section)
    )
    severity_counts = result.after_audit.severity_counts

    kpi_cards = [
        ("Changed Sections", str(changed_sections_count), ""),
        ("Lines Added", f"+{result.diff.total_added}", "kpi-add"),
        ("Lines Removed", f"-{result.diff.total_removed}", "kpi-del"),
        ("Total Findings", str(result.after_audit.total_findings), ""),
        (
            "CRITICAL",
            str(severity_counts.get(security_audit.SEVERITY_CRITICAL, 0)),
            "kpi-critical",
        ),
        (
            "HIGH",
            str(severity_counts.get(security_audit.SEVERITY_HIGH, 0)),
            "kpi-high",
        ),
        (
            "MEDIUM",
            str(severity_counts.get(security_audit.SEVERITY_MEDIUM, 0)),
            "kpi-medium",
        ),
        (
            "LOW",
            str(severity_counts.get(security_audit.SEVERITY_LOW, 0)),
            "kpi-low",
        ),
        ("New Findings", str(len(result.new_findings)), "kpi-critical"),
        ("Pre-Existing", str(len(result.existing_findings)), ""),
        ("Resolved", str(len(result.resolved_findings)), "kpi-add"),
    ]
    kpi_html = "\n".join(
        f'<div class="kpi-card"><div class="kpi-label">{_esc(label)}</div>'
        f'<div class="kpi-value {css_cls}">{_esc(value)}</div></div>'
        for label, value, css_cls in kpi_cards
    )

    active_items: list[tuple[bool, security_audit.Finding]] = [
        *((True, finding) for finding in result.new_findings),
        *((False, finding) for finding in result.existing_findings),
    ]
    active_items.sort(
        key=lambda item: _finding_sort_key(item[1], is_new=item[0])
    )

    findings_parts: list[str] = []
    if result.after_audit.total_findings == 0:
        findings_parts.append(
            '<div class="banner banner-pass">'
            "PASS: No security audit findings detected in the after configuration."
            "</div>"
        )
    if active_items:
        findings_parts.extend(
            _render_finding_card(
                finding,
                "NEW" if is_new else "PRE-EXISTING",
                "badge-new" if is_new else "badge-existing",
            )
            for is_new, finding in active_items
        )

    if result.resolved_findings:
        sorted_resolved = sorted(result.resolved_findings, key=_finding_sort_key)
        resolved_cards = "\n".join(
            _render_finding_card(finding, "RESOLVED", "badge-resolved")
            for finding in sorted_resolved
        )
        findings_parts.append(
            '<div class="resolved-block">\n'
            f"  <h3>Resolved Findings ({len(sorted_resolved)})</h3>\n"
            f"  {resolved_cards}\n"
            "</div>"
        )

    findings_html = "\n".join(findings_parts)
    diff_html = _render_diff_section(result)

    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        f"  <title>NetAudit Report - {_esc(hostname_display)}</title>\n"
        f"  <style>\n{_HTML_CSS}  </style>\n"
        "</head>\n"
        "<body>\n"
        '  <div class="container">\n'
        '    <header class="report-header">\n'
        "      <h1>Network Configuration Diff &amp; Security Audit Report</h1>\n"
        '      <div class="meta-grid">\n'
        f'        <div class="meta-item"><strong>Hostname:</strong> {_esc(hostname_display)}</div>\n'
        f'        <div class="meta-item"><strong>Generated:</strong> {_esc(result.generated_at)}</div>\n'
        f'        <div class="meta-item"><strong>Before:</strong> <code>{_esc(result.before_path)}</code></div>\n'
        f'        <div class="meta-item"><strong>After:</strong> <code>{_esc(result.after_path)}</code></div>\n'
        "      </div>\n"
        "    </header>\n"
        '    <section class="kpi-grid" aria-label="Audit Summary Metrics">\n'
        f"      {kpi_html}\n"
        "    </section>\n"
        '    <section class="section-block" aria-label="Security Audit Findings">\n'
        "      <h2>Security Audit Findings</h2>\n"
        f"      {findings_html}\n"
        "    </section>\n"
        '    <section class="section-block" aria-label="Configuration Diff">\n'
        "      <h2>Configuration Diff</h2>\n"
        f"      {diff_html}\n"
        "    </section>\n"
        "  </div>\n"
        "</body>\n"
        "</html>\n"
    )


def write_html_report(result: CombinedAuditResult, output_path: str | Path) -> Path:
    """Render and write the HTML report to output_path, creating parent directories."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html_report(result), encoding="utf-8")
    return path


def format_cli_summary(result: CombinedAuditResult, report_path: Path) -> str:
    """Format a concise human-readable CLI summary for a CombinedAuditResult."""
    hostname_display = result.hostname or "unknown"
    changed_sections_count = sum(
        1 for section in result.diff.sections if _is_changed_section(section)
    )
    severity_counts = result.after_audit.severity_counts
    sev_summary = ", ".join(
        f"{sev}={severity_counts.get(sev, 0)}" for sev in SEVERITY_LEVELS
    )
    audit_status = (
        "PASS (0 findings)"
        if result.after_audit.total_findings == 0
        else f"FAIL ({result.after_audit.total_findings} findings)"
    )

    lines: list[str] = [
        "Network Audit Summary",
        "=====================",
        f"Hostname    : {hostname_display}",
        f"Before      : {result.before_path}",
        f"After       : {result.after_path}",
        f"Generated   : {result.generated_at}",
        f"HTML Report : {report_path}",
        "",
        "Configuration Diff",
        "------------------",
    ]
    if result.diff.has_changes:
        lines.extend(
            [
                f"  Changed sections : {changed_sections_count}",
                f"  Lines added      : +{result.diff.total_added}",
                f"  Lines removed    : -{result.diff.total_removed}",
            ]
        )
    else:
        lines.append("  No configuration differences detected.")

    lines.extend(
        [
            "",
            "Security Audit",
            "--------------",
            f"  Status         : {audit_status}",
            f"  By Severity    : {sev_summary}",
            (
                "  Baseline Delta : "
                f"NEW={len(result.new_findings)}, "
                f"PRE-EXISTING={len(result.existing_findings)}, "
                f"RESOLVED={len(result.resolved_findings)}"
            ),
        ]
    )

    active_items: list[tuple[bool, security_audit.Finding]] = [
        *((True, finding) for finding in result.new_findings),
        *((False, finding) for finding in result.existing_findings),
    ]
    active_items.sort(
        key=lambda item: _finding_sort_key(item[1], is_new=item[0])
    )
    if active_items:
        lines.extend(["", f"Active Findings ({len(active_items)})", "-------------------"])
        for is_new, finding in active_items:
            tag = "NEW" if is_new else "PRE-EXISTING"
            line_lbl = _format_line_label(finding.line_number)
            lines.append(
                f"  [{finding.severity}] [{tag}] {finding.rule_id} "
                f"({line_lbl}, {finding.section}): {finding.title}"
            )

    if result.resolved_findings:
        lines.extend(
            [
                "",
                f"Resolved Findings ({len(result.resolved_findings)})",
                "---------------------",
            ]
        )
        for finding in sorted(result.resolved_findings, key=_finding_sort_key):
            line_lbl = _format_line_label(finding.line_number)
            lines.append(
                f"  [{finding.severity}] [RESOLVED] {finding.rule_id} "
                f"({line_lbl}, {finding.section}): {finding.title}"
            )

    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    """Construct the CLI argument parser for netaudit."""
    parser = argparse.ArgumentParser(
        description=(
            "Diff two Cisco IOS/ASA configuration files, run security audits, "
            "and generate a self-contained HTML report."
        )
    )
    parser.add_argument("before", help="Path to the baseline (before) configuration file.")
    parser.add_argument("after", help="Path to the target (after) configuration file.")
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Explicit output path for the generated HTML report.",
    )
    parser.add_argument(
        "--output-dir",
        default="reports",
        help="Directory for auto-named HTML reports when --output is not given (default: reports).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print a JSON summary (including report_path) to stdout.",
    )
    parser.add_argument(
        "--fail-on",
        type=str.upper,
        choices=SEVERITY_LEVELS,
        default=None,
        help=(
            "Exit with status 2 if any active finding has severity at or above "
            "this threshold (CRITICAL, HIGH, MEDIUM, LOW)."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    target_path = (
        Path(args.output)
        if args.output is not None
        else default_report_path(args.before, args.after, args.output_dir)
    )

    try:
        result = run_audit(args.before, args.after)
        written_path = write_html_report(result, target_path)
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        payload = result.to_dict()
        payload["report_path"] = str(written_path)
        print(json.dumps(payload, indent=2))
    else:
        print(format_cli_summary(result, written_path))

    if args.fail_on is not None:
        threshold_rank = security_audit.SEVERITY_ORDER[args.fail_on]
        for finding in result.after_audit.findings:
            if security_audit.SEVERITY_ORDER[finding.severity] <= threshold_rank:
                return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
