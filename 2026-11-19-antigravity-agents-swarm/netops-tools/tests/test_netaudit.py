"""Unit tests for netaudit.py."""

from __future__ import annotations

import contextlib
import dataclasses
import io
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import netaudit  # noqa: E402
import security_audit  # noqa: E402

SAMPLE_BEFORE = PROJECT_ROOT / "samples" / "backups" / "edge-rtr1_2026-11-18.cfg"
SAMPLE_AFTER = PROJECT_ROOT / "samples" / "backups" / "edge-rtr1_2026-11-19.cfg"


def _hardened_config(hostname: str = "clean-rtr1") -> str:
    return "\n".join(
        [
            f"hostname {hostname}",
            "!",
            "service password-encryption",
            "enable secret 9 $9$examplehashvalue",
            "no ip http server",
            "ip http secure-server",
            "snmp-server community s3cur3-r0-v2 RO",
            "!",
            "interface GigabitEthernet0/0",
            " description Uplink",
            " no shutdown",
            "!",
            "line vty 0 4",
            " exec-timeout 5 0",
            " transport input ssh",
            "!",
            "end",
            "",
        ]
    )


class TestRunAuditAndComparison(unittest.TestCase):
    def test_run_audit_sample_backups(self) -> None:
        result = netaudit.run_audit(
            SAMPLE_BEFORE,
            SAMPLE_AFTER,
            generated_at="2026-11-19T12:00:00Z",
        )

        self.assertEqual(result.hostname, "edge-rtr1")
        self.assertEqual(result.generated_at, "2026-11-19T12:00:00Z")
        self.assertEqual(result.diff.total_added, 7)
        self.assertEqual(result.diff.total_removed, 3)
        self.assertEqual(result.before_audit.total_findings, 2)
        self.assertEqual(result.after_audit.total_findings, 4)

        self.assertEqual(len(result.new_findings), 2)
        self.assertEqual(
            {f.rule_id for f in result.new_findings},
            {"SNMP_DEFAULT_COMMUNITY", "TELNET_ENABLED"},
        )
        self.assertEqual(len(result.existing_findings), 2)
        self.assertEqual(
            {f.rule_id for f in result.existing_findings},
            {"NO_PASSWORD_ENCRYPTION", "MISSING_EXEC_TIMEOUT"},
        )
        self.assertEqual(len(result.resolved_findings), 0)

        payload = result.to_dict()
        for key in (
            "before_path",
            "after_path",
            "hostname",
            "generated_at",
            "diff",
            "before_audit",
            "after_audit",
            "new_findings",
            "existing_findings",
            "resolved_findings",
        ):
            self.assertIn(key, payload)

    def test_finding_key_returns_rule_section_evidence(self) -> None:
        finding = security_audit.Finding(
            rule_id="TELNET_ENABLED",
            title="Telnet enabled",
            severity="HIGH",
            section="line vty 0 4",
            line_number=24,
            evidence="transport input telnet ssh",
            description="desc",
            remediation="rem",
        )
        self.assertEqual(
            netaudit.finding_key(finding),
            ("TELNET_ENABLED", "line vty 0 4", "transport input telnet ssh"),
        )

    def test_resolved_findings_and_shifted_line_numbers(self) -> None:
        before_cfg = "\n".join(
            [
                "hostname shift-rtr",
                "!",
                "ip http server",
                "snmp-server community public RO",
                "!",
                "line vty 0 4",
                " exec-timeout 5 0",
                " transport input ssh",
                "!",
                "end",
                "",
            ]
        )
        after_cfg = "\n".join(
            [
                "hostname shift-rtr",
                "!",
                "service password-encryption",
                "!",
                "interface Loopback0",
                " description inserted block to shift line numbers",
                " ip address 10.255.255.1 255.255.255.255",
                "!",
                "interface Loopback1",
                " ip address 10.255.255.2 255.255.255.255",
                "!",
                "no ip http server",
                "snmp-server community public RO",
                "!",
                "line vty 0 4",
                " exec-timeout 5 0",
                " transport input ssh",
                "!",
                "end",
                "",
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            before_path = Path(tmpdir) / "before.cfg"
            after_path = Path(tmpdir) / "after.cfg"
            before_path.write_text(before_cfg, encoding="utf-8")
            after_path.write_text(after_cfg, encoding="utf-8")

            result = netaudit.run_audit(before_path, after_path)

        self.assertEqual(len(result.new_findings), 0)
        self.assertEqual(len(result.existing_findings), 1)
        self.assertEqual(
            result.existing_findings[0].rule_id,
            "SNMP_DEFAULT_COMMUNITY",
        )
        self.assertEqual(
            {f.rule_id for f in result.resolved_findings},
            {"NO_PASSWORD_ENCRYPTION", "HTTP_SERVER_ENABLED"},
        )
        before_snmp = next(
            f for f in result.before_audit.findings if f.rule_id == "SNMP_DEFAULT_COMMUNITY"
        )
        after_snmp = next(
            f for f in result.after_audit.findings if f.rule_id == "SNMP_DEFAULT_COMMUNITY"
        )
        self.assertNotEqual(before_snmp.line_number, after_snmp.line_number)


class TestReportPathsAndHtml(unittest.TestCase):
    def test_default_report_path(self) -> None:
        default_path = netaudit.default_report_path(SAMPLE_BEFORE, SAMPLE_AFTER)
        self.assertEqual(Path(default_path).parent, Path("reports"))
        self.assertEqual(Path(default_path).suffix, ".html")

        with tempfile.TemporaryDirectory() as tmpdir:
            custom_path = netaudit.default_report_path(
                SAMPLE_BEFORE,
                SAMPLE_AFTER,
                output_dir=tmpdir,
            )
            self.assertEqual(Path(custom_path).parent, Path(tmpdir))
            self.assertEqual(Path(custom_path).suffix, ".html")
            self.assertTrue(Path(custom_path).stem)

    def test_render_html_report_structure_and_no_external_assets(self) -> None:
        result = netaudit.run_audit(
            SAMPLE_BEFORE,
            SAMPLE_AFTER,
            generated_at="2026-11-19T12:00:00Z",
        )
        html_doc = netaudit.render_html_report(result)

        self.assertTrue(html_doc.startswith("<!DOCTYPE html>"))
        self.assertIn("<style", html_doc)
        self.assertIn("</style>", html_doc)
        self.assertIsNone(re.search(r"https?://", html_doc, re.IGNORECASE))
        self.assertIn("edge-rtr1", html_doc)
        self.assertIn("SNMP_DEFAULT_COMMUNITY", html_doc)

    def test_render_html_report_escapes_xss_characters(self) -> None:
        before_cfg = "\n".join(
            [
                'hostname edge-<script>alert(1)</script>&"host"',
                "!",
                "service password-encryption",
                "interface GigabitEthernet0/0",
                " description safe",
                "!",
                "line vty 0 4",
                " exec-timeout 5 0",
                " transport input ssh",
                "!",
                "end",
                "",
            ]
        )
        after_cfg = "\n".join(
            [
                'hostname edge-<script>alert(1)</script>&"host"',
                "!",
                "service password-encryption",
                'enable password <script>alert(3)</script>&"pw"',
                "interface GigabitEthernet0/0",
                ' description <script>alert(2)</script>&"line"',
                "!",
                "line vty 0 4",
                " exec-timeout 5 0",
                " transport input ssh",
                "!",
                "end",
                "",
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            before_path = Path(tmpdir) / "before.cfg"
            after_path = Path(tmpdir) / "after.cfg"
            before_path.write_text(before_cfg, encoding="utf-8")
            after_path.write_text(after_cfg, encoding="utf-8")
            result = netaudit.run_audit(
                before_path,
                after_path,
                generated_at="2026-11-19T12:00:00Z",
            )

        # Inject XSS payload into paths in memory (Windows NTFS forbids '<' and '"' on disk)
        xss_before = type(result.before_path)('/tmp/<script>alert(4)</script>&"before.cfg')
        xss_after = type(result.after_path)('/tmp/<script>alert(4)</script>&"after.cfg')
        patched_diff = dataclasses.replace(
            result.diff,
            before_source=str(xss_before),
            after_source=str(xss_after),
        )
        patched_before_audit = dataclasses.replace(result.before_audit, source=str(xss_before))
        patched_after_audit = dataclasses.replace(result.after_audit, source=str(xss_after))
        patched_result = dataclasses.replace(
            result,
            before_path=xss_before,
            after_path=xss_after,
            diff=patched_diff,
            before_audit=patched_before_audit,
            after_audit=patched_after_audit,
        )

        html_doc = netaudit.render_html_report(patched_result)
        self.assertNotIn("<script>", html_doc)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;&amp;&quot;host", html_doc)
        self.assertIn("&lt;script&gt;alert(2)&lt;/script&gt;&amp;&quot;line", html_doc)
        self.assertIn("&lt;script&gt;alert(3)&lt;/script&gt;&amp;&quot;pw", html_doc)
        self.assertIn("&lt;script&gt;alert(4)&lt;/script&gt;&amp;&quot;", html_doc)

    def test_render_html_report_clean_pass_and_empty_diff(self) -> None:
        cfg = _hardened_config("clean-edge")
        with tempfile.TemporaryDirectory() as tmpdir:
            before_path = Path(tmpdir) / "before.cfg"
            after_path = Path(tmpdir) / "after.cfg"
            before_path.write_text(cfg, encoding="utf-8")
            after_path.write_text(cfg, encoding="utf-8")

            result = netaudit.run_audit(before_path, after_path)

        self.assertFalse(result.diff.has_changes)
        self.assertTrue(result.after_audit.passed)
        self.assertEqual(len(result.new_findings), 0)
        self.assertEqual(len(result.existing_findings), 0)
        self.assertEqual(len(result.resolved_findings), 0)

        html_doc = netaudit.render_html_report(result)
        lowered = html_doc.lower()
        self.assertIsNotNone(
            re.search(r"no (configuration )?(differences|changes)", lowered)
        )
        self.assertTrue("pass" in lowered or "0 findings" in lowered or "no findings" in lowered)

    def test_write_html_report_creates_nested_dirs(self) -> None:
        result = netaudit.run_audit(SAMPLE_BEFORE, SAMPLE_AFTER)
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "nested" / "sub" / "report.html"
            written = netaudit.write_html_report(result, out_path)
            self.assertTrue(out_path.is_file())
            if written is not None:
                self.assertEqual(Path(written), out_path)
            content = out_path.read_text(encoding="utf-8")
            self.assertTrue(content.startswith("<!DOCTYPE html>"))

    def test_format_cli_summary(self) -> None:
        result = netaudit.run_audit(SAMPLE_BEFORE, SAMPLE_AFTER)
        summary = netaudit.format_cli_summary(result, Path("reports/example.html"))
        self.assertIn("edge-rtr1", summary)
        self.assertIn("example.html", summary)


class TestNetAuditCli(unittest.TestCase):
    def test_cli_output_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = netaudit.main(
                    [str(SAMPLE_BEFORE), str(SAMPLE_AFTER), "--output-dir", tmpdir]
                )

            self.assertEqual(code, 0)
            reports = list(Path(tmpdir).glob("*.html"))
            self.assertEqual(len(reports), 1)
            self.assertTrue(reports[0].read_text(encoding="utf-8").startswith("<!DOCTYPE html>"))
            self.assertIn("edge-rtr1", stdout.getvalue())

    def test_cli_output_short_and_long_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            short_out = Path(tmpdir) / "short_report.html"
            stdout_short = io.StringIO()
            with contextlib.redirect_stdout(stdout_short):
                code_short = netaudit.main(
                    [str(SAMPLE_BEFORE), str(SAMPLE_AFTER), "-o", str(short_out)]
                )
            self.assertEqual(code_short, 0)
            self.assertTrue(short_out.is_file())

            long_out = Path(tmpdir) / "sub" / "long_report.html"
            stdout_long = io.StringIO()
            with contextlib.redirect_stdout(stdout_long):
                code_long = netaudit.main(
                    [str(SAMPLE_BEFORE), str(SAMPLE_AFTER), "--output", str(long_out)]
                )
            self.assertEqual(code_long, 0)
            self.assertTrue(long_out.is_file())

    def test_cli_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = netaudit.main(
                    [
                        str(SAMPLE_BEFORE),
                        str(SAMPLE_AFTER),
                        "--output-dir",
                        tmpdir,
                        "--json",
                    ]
                )

            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertIn("report_path", payload)
            report_path = Path(payload["report_path"])
            self.assertTrue(report_path.is_file())
            self.assertEqual(report_path.parent, Path(tmpdir))
            self.assertEqual(payload["hostname"], "edge-rtr1")

    def test_cli_fail_on_thresholds_and_case_insensitive(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Sample backups include CRITICAL + HIGH + MEDIUM findings
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code_crit = netaudit.main(
                    [
                        str(SAMPLE_BEFORE),
                        str(SAMPLE_AFTER),
                        "--output-dir",
                        tmpdir,
                        "--fail-on",
                        "CRITICAL",
                    ]
                )
            self.assertEqual(code_crit, 2)

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code_high_ci = netaudit.main(
                    [
                        str(SAMPLE_BEFORE),
                        str(SAMPLE_AFTER),
                        "--output-dir",
                        tmpdir,
                        "--fail-on",
                        "high",
                    ]
                )
            self.assertEqual(code_high_ci, 2)

            # Medium-only config (clean before -> medium-only after)
            before_clean = Path(tmpdir) / "before_clean.cfg"
            after_medium = Path(tmpdir) / "after_medium.cfg"
            before_clean.write_text(_hardened_config("med-rtr"), encoding="utf-8")
            after_medium.write_text(
                _hardened_config("med-rtr").replace("service password-encryption\n", ""),
                encoding="utf-8",
            )

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code_med_vs_high = netaudit.main(
                    [
                        str(before_clean),
                        str(after_medium),
                        "--output-dir",
                        tmpdir,
                        "--fail-on",
                        "HIGH",
                    ]
                )
            self.assertEqual(code_med_vs_high, 0)

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code_med_vs_high_ci = netaudit.main(
                    [
                        str(before_clean),
                        str(after_medium),
                        "--output-dir",
                        tmpdir,
                        "--fail-on",
                        "high",
                    ]
                )
            self.assertEqual(code_med_vs_high_ci, 0)

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code_med_vs_med = netaudit.main(
                    [
                        str(before_clean),
                        str(after_medium),
                        "--output-dir",
                        tmpdir,
                        "--fail-on",
                        "MEDIUM",
                    ]
                )
            self.assertEqual(code_med_vs_med, 2)

            # Clean configs with 0 findings pass even at --fail-on LOW
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code_clean = netaudit.main(
                    [
                        str(before_clean),
                        str(before_clean),
                        "--output-dir",
                        tmpdir,
                        "--fail-on",
                        "LOW",
                    ]
                )
            self.assertEqual(code_clean, 0)

    def test_cli_missing_file_returns_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                code_before = netaudit.main(
                    ["missing_before.cfg", str(SAMPLE_AFTER), "--output-dir", tmpdir]
                )
            self.assertEqual(code_before, 1)
            self.assertTrue(stderr.getvalue().strip())

            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                code_after = netaudit.main(
                    [str(SAMPLE_BEFORE), "missing_after.cfg", "--output-dir", tmpdir]
                )
            self.assertEqual(code_after, 1)
            self.assertTrue(stderr.getvalue().strip())

    def test_build_parser(self) -> None:
        parser = netaudit.build_parser()
        args = parser.parse_args(
            [
                "before.cfg",
                "after.cfg",
                "--output-dir",
                "out",
                "--json",
                "--fail-on",
                "HIGH",
            ]
        )
        self.assertTrue(args.json)
        self.assertEqual(args.output_dir, "out")
        self.assertEqual(args.fail_on, "HIGH")


if __name__ == "__main__":
    unittest.main()
