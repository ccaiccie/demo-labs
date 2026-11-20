#!/usr/bin/env python3
"""Parse and diff Cisco-style network device configurations by section."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import difflib
import json
from pathlib import Path
import sys
from typing import Any

SECTION_PREFIXES: tuple[str, ...] = (
    "interface ",
    "router ",
    "line ",
    "ip access-list ",
    "ipv6 access-list ",
    "route-map ",
    "class-map ",
    "policy-map ",
    "crypto map ",
    "crypto isakmp ",
    "crypto ipsec ",
    "crypto pki ",
    "vlan ",
    "vrf definition ",
    "ip vrf ",
    "controller ",
    "track ",
    "key chain ",
    "aaa group server ",
    "tacacs server ",
    "radius server ",
    "control-plane",
)

_CLASSIFY_PREFIXES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("interface ",), "interface"),
    (("router ",), "router"),
    (("line ",), "line"),
    (("ip access-list ", "ipv6 access-list ", "access-list "), "access-list"),
    (("route-map ",), "route-map"),
    (("policy-map ",), "policy-map"),
    (("class-map ",), "class-map"),
    (("crypto ",), "crypto"),
    (("vlan ",), "vlan"),
    (("vrf ", "ip vrf "), "vrf"),
)


@dataclass(frozen=True)
class ConfigSection:
    """A logical configuration section and its stripped child lines."""

    name: str
    category: str
    lines: tuple[str, ...]
    start_line: int | None = None


@dataclass(frozen=True)
class SectionDiff:
    """Line-level diff summary for a single configuration section."""

    section: str
    category: str
    status: str
    added: tuple[str, ...]
    removed: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Serialize this section diff to a JSON-compatible dictionary."""
        return {
            "section": self.section,
            "category": self.category,
            "status": self.status,
            "added": list(self.added),
            "removed": list(self.removed),
        }


@dataclass(frozen=True)
class ConfigDiff:
    """Structured section-by-section diff between two configurations."""

    before_source: str
    after_source: str
    sections: tuple[SectionDiff, ...]

    @property
    def total_added(self) -> int:
        """Total number of added lines across all changed sections."""
        return sum(len(item.added) for item in self.sections)

    @property
    def total_removed(self) -> int:
        """Total number of removed lines across all changed sections."""
        return sum(len(item.removed) for item in self.sections)

    @property
    def has_changes(self) -> bool:
        """Return True if any section was added, removed, or modified."""
        return bool(self.sections)

    def by_category(self) -> dict[str, list[SectionDiff]]:
        """Group changed sections by category, preserving first-seen order."""
        grouped: dict[str, list[SectionDiff]] = {}
        for item in self.sections:
            grouped.setdefault(item.category, []).append(item)
        return grouped

    def to_dict(self) -> dict[str, Any]:
        """Serialize this diff report to a JSON-compatible dictionary."""
        grouped = self.by_category()
        return {
            "before_source": self.before_source,
            "after_source": self.after_source,
            "has_changes": self.has_changes,
            "total_added": self.total_added,
            "total_removed": self.total_removed,
            "changed_sections": len(self.sections),
            "sections": [item.to_dict() for item in self.sections],
            "by_category": {
                category: [item.to_dict() for item in items]
                for category, items in grouped.items()
            },
        }


def classify_section(header: str) -> str:
    """Classify a configuration section header into a normalized category."""
    normalized = header.strip().lower()
    if normalized == "global":
        return "global"

    for prefixes, category in _CLASSIFY_PREFIXES:
        if normalized.startswith(prefixes):
            return category

    tokens = normalized.split()
    return tokens[0] if tokens else ""


def _is_known_section_header(stripped: str) -> bool:
    """Return True if a stripped line matches any known section header prefix."""
    lowered = stripped.lower()
    for prefix in SECTION_PREFIXES:
        if prefix.endswith(" "):
            if lowered.startswith(prefix):
                return True
        elif lowered == prefix or lowered.startswith(f"{prefix} "):
            return True
    return False


def _next_significant_line_is_indented(raw_lines: list[str], start_index: int) -> bool:
    """Return True if the next non-blank, non-'!' line begins with whitespace."""
    for idx in range(start_index, len(raw_lines)):
        candidate = raw_lines[idx]
        stripped = candidate.strip()
        if not stripped or stripped.startswith("!"):
            continue
        return candidate[0].isspace()
    return False


def parse_config(text: str) -> dict[str, ConfigSection]:
    """Parse Cisco-style configuration text into ordered ConfigSection objects."""
    raw_lines = text.splitlines()
    section_lines: dict[str, list[str]] = {}
    section_start_lines: dict[str, int | None] = {}
    section_categories: dict[str, str] = {}
    active_section: str | None = None

    for index, raw_line in enumerate(raw_lines):
        line_number = index + 1
        stripped = raw_line.strip()
        if not stripped:
            continue
        if stripped.startswith("!"):
            # Top-level '!' separators close the active block; indented ' !' spacers do not.
            if not raw_line[0].isspace():
                active_section = None
            continue

        if raw_line[0].isspace():
            if active_section is not None:
                section_lines[active_section].append(stripped)
            continue

        active_section = None
        if _is_known_section_header(stripped) or _next_significant_line_is_indented(
            raw_lines, index + 1
        ):
            if stripped not in section_lines:
                section_lines[stripped] = []
                section_start_lines[stripped] = line_number
                section_categories[stripped] = classify_section(stripped)
            active_section = stripped
        else:
            if "global" not in section_lines:
                section_lines["global"] = []
                section_start_lines["global"] = None
                section_categories["global"] = "global"
            section_lines["global"].append(stripped)

    return {
        name: ConfigSection(
            name=name,
            category=section_categories[name],
            lines=tuple(lines),
            start_line=section_start_lines[name],
        )
        for name, lines in section_lines.items()
    }


def _diff_section_lines(
    before_lines: tuple[str, ...], after_lines: tuple[str, ...]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Compute (added, removed) line tuples for two versions of a section."""
    matcher = difflib.SequenceMatcher(None, before_lines, after_lines)
    added: list[str] = []
    removed: list[str] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "delete":
            removed.extend(before_lines[i1:i2])
        elif tag == "insert":
            added.extend(after_lines[j1:j2])
        elif tag == "replace":
            removed.extend(before_lines[i1:i2])
            added.extend(after_lines[j1:j2])
    return tuple(added), tuple(removed)


def diff_configs(
    before_text: str,
    after_text: str,
    *,
    before_source: str = "before",
    after_source: str = "after",
) -> ConfigDiff:
    """Compute a section-aware diff between two configuration strings."""
    before_sections = parse_config(before_text)
    after_sections = parse_config(after_text)

    ordered_names = list(dict.fromkeys([*before_sections, *after_sections]))
    diffs: list[SectionDiff] = []

    for name in ordered_names:
        in_before = name in before_sections
        in_after = name in after_sections

        if not in_before:
            after_sec = after_sections[name]
            diffs.append(
                SectionDiff(
                    section=name,
                    category=after_sec.category,
                    status="added",
                    added=after_sec.lines,
                    removed=(),
                )
            )
            continue

        if not in_after:
            before_sec = before_sections[name]
            diffs.append(
                SectionDiff(
                    section=name,
                    category=before_sec.category,
                    status="removed",
                    added=(),
                    removed=before_sec.lines,
                )
            )
            continue

        before_sec = before_sections[name]
        after_sec = after_sections[name]
        added, removed = _diff_section_lines(before_sec.lines, after_sec.lines)
        if added or removed:
            diffs.append(
                SectionDiff(
                    section=name,
                    category=after_sec.category,
                    status="modified",
                    added=added,
                    removed=removed,
                )
            )

    return ConfigDiff(
        before_source=before_source,
        after_source=after_source,
        sections=tuple(diffs),
    )


def diff_files(before_path: str | Path, after_path: str | Path) -> ConfigDiff:
    """Read two configuration files and compute their section-aware diff."""
    before_text = Path(before_path).read_text(encoding="utf-8", errors="replace")
    after_text = Path(after_path).read_text(encoding="utf-8", errors="replace")
    return diff_configs(
        before_text,
        after_text,
        before_source=str(before_path),
        after_source=str(after_path),
    )


def format_text_diff(diff: ConfigDiff) -> str:
    """Render a ConfigDiff as a human-readable report grouped by category."""
    out: list[str] = [
        "Config Diff Report",
        "==================",
        f"Before:           {diff.before_source}",
        f"After:            {diff.after_source}",
        f"Changed sections: {len(diff.sections)}",
        f"Total added:      {diff.total_added}",
        f"Total removed:    {diff.total_removed}",
    ]

    if not diff.has_changes:
        out.extend(["", "No changes detected."])
        return "\n".join(out)

    for category, items in diff.by_category().items():
        out.extend(["", f"[{category}]"])
        for item in items:
            out.append(f"  {item.section} ({item.status})")
            if not item.removed and not item.added:
                out.append("    (no child lines)")
                continue
            for line in item.removed:
                out.append(f"    - {line}")
            for line in item.added:
                out.append(f"    + {line}")

    return "\n".join(out)


def format_json_diff(diff: ConfigDiff) -> str:
    """Render a ConfigDiff as formatted JSON."""
    return json.dumps(diff.to_dict(), indent=2)


def build_parser() -> argparse.ArgumentParser:
    """Construct the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Compare two Cisco-style network configuration files by section."
    )
    parser.add_argument(
        "before",
        help="Path to the baseline ('before') configuration file.",
    )
    parser.add_argument(
        "after",
        help="Path to the updated ('after') configuration file.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output the config diff as JSON.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        diff = diff_files(args.before, args.after)
    except OSError as exc:
        target = exc.filename if exc.filename else f"{args.before} / {args.after}"
        print(f"Error reading {target}: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(format_json_diff(diff))
    else:
        print(format_text_diff(diff))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
