"""Unit tests for security_audit.py."""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import security_audit  # noqa: E402

SAMPLE_BEFORE = PROJECT_ROOT / "samples" / "backups" / "edge-rtr1_2026-11-18.cfg"
SAMPLE_AFTER = PROJECT_ROOT / "samples" / "backups" / "edge-rtr1_2026-11-19.cfg"


def _build_config(
    *,
    password_encryption: list[str] | None = None,
    enable_lines: list[str] | None = None,
    http_lines: list[str] | None = None,
    snmp_lines: list[str] | None = None,
    vty_lines: list[str] | None = None,
) -> str:
    """Build a hardened baseline Cisco IOS config with selective overrides."""
    lines = ["hostname hardened-rtr1", "!"]
    lines.extend(
        ["service password-encryption"]
        if password_encryption is None
        else password_encryption
    )
    lines.extend(
        ["enable secret 9 $9$examplehashvalue"]
        if enable_lines is None
        else enable_lines
    )
    lines.extend(
        ["no ip http server", "ip http secure-server"]
        if http_lines is None
        else http_lines
    )
    lines.extend(
        ["snmp-server community s3cur3-r0-v2 RO"]
        if snmp_lines is None
        else snmp_lines
    )
    if vty_lines is None:
        lines.extend(["line vty 0 4", " exec-timeout 5 0", " transport input ssh"])
    else:
        lines.extend(vty_lines)
    lines.extend(["!", "end", ""])
    return "\n".join(lines)


class TestSeverityAndDataclasses(unittest.TestCase):
    def test_severity_constants_and_order(self) -> None:
        self.assertEqual(security_audit.SEVERITY_CRITICAL, "CRITICAL")
        self.assertEqual(security_audit.SEVERITY_HIGH, "HIGH")
        self.assertEqual(security_audit.SEVERITY_MEDIUM, "MEDIUM")
        self.assertEqual(security_audit.SEVERITY_LOW, "LOW")
        for sev in (
            security_audit.SEVERITY_CRITICAL,
            security_audit.SEVERITY_HIGH,
            security_audit.SEVERITY_MEDIUM,
            security_audit.SEVERITY_LOW,
        ):
            self.assertIn(sev, security_audit.SEVERITY_ORDER)

    def test_finding_and_report_to_dict(self) -> None:
        finding = security_audit.Finding(
            rule_id="TELNET_ENABLED",
            title="Telnet enabled on VTY lines",
            severity=security_audit.SEVERITY_HIGH,
            section="line vty 0 4",
            line_number=24,
            evidence="transport input telnet ssh",
            description="Cleartext management protocol enabled.",
            remediation="Use transport input ssh.",
        )
        f_dict = finding.to_dict()
        self.assertEqual(
            f_dict,
            {
                "rule_id": "TELNET_ENABLED",
                "title": "Telnet enabled on VTY lines",
                "severity": "HIGH",
                "section": "line vty 0 4",
                "line_number": 24,
                "evidence": "transport input telnet ssh",
                "description": "Cleartext management protocol enabled.",
                "remediation": "Use transport input ssh.",
            },
        )

        report = security_audit.AuditReport(
            source="test.cfg",
            hostname="edge-rtr1",
            findings=(finding,),
            severity_counts={"CRITICAL": 0, "HIGH": 1, "MEDIUM": 0, "LOW": 0},
        )
        self.assertEqual(report.total_findings, 1)
        self.assertFalse(report.passed)
        r_dict = report.to_dict()
        self.assertEqual(r_dict["source"], "test.cfg")
        self.assertEqual(r_dict["hostname"], "edge-rtr1")
        self.assertEqual(r_dict["total_findings"], 1)
        self.assertFalse(r_dict["passed"])
        self.assertEqual(len(r_dict["findings"]), 1)

    def test_clean_hardened_config_passes(self) -> None:
        cfg = _build_config()
        report = security_audit.audit_config(cfg, source="clean.cfg")

        self.assertTrue(report.passed)
        self.assertEqual(report.total_findings, 0)
        self.assertEqual(list(report.findings), [])
        for sev in (
            security_audit.SEVERITY_CRITICAL,
            security_audit.SEVERITY_HIGH,
            security_audit.SEVERITY_MEDIUM,
            security_audit.SEVERITY_LOW,
        ):
            self.assertEqual(report.severity_counts.get(sev, 0), 0)
        self.assertEqual(sum(report.severity_counts.values()), 0)


class TestExtractHostname(unittest.TestCase):
    def test_extract_hostname_present(self) -> None:
        cfg = "! hostname ignored-comment\r\nhostname core-rtr1\r\n!\r\n"
        self.assertEqual(security_audit.extract_hostname(cfg), "core-rtr1")

    def test_extract_hostname_missing(self) -> None:
        cfg = "interface GigabitEthernet0/0\n no shutdown\n"
        self.assertIn(security_audit.extract_hostname(cfg), (None, ""))


class TestSecurityRules(unittest.TestCase):
    def test_telnet_enabled_triggers_high(self) -> None:
        for directive in (
            " transport input telnet",
            " transport input telnet ssh",
            " transport input all",
        ):
            with self.subTest(directive=directive):
                cfg = _build_config(
                    vty_lines=["line vty 0 4", " exec-timeout 5 0", directive]
                )
                report = security_audit.audit_config(cfg)
                self.assertEqual(report.total_findings, 1)
                finding = report.findings[0]
                self.assertEqual(finding.rule_id, "TELNET_ENABLED")
                self.assertEqual(finding.severity, security_audit.SEVERITY_HIGH)
                self.assertEqual(finding.section, "line vty 0 4")
                self.assertIsInstance(finding.line_number, int)

    def test_telnet_safe_configurations_do_not_trigger(self) -> None:
        safe_cases = [
            ["line vty 0 4", " exec-timeout 5 0", " transport input ssh"],
            ["line vty 0 4", " exec-timeout 5 0", " transport input none"],
            ["line vty 0 4", " exec-timeout 5 0"],
            ["line vty 0 4", " exec-timeout 5 0", " no transport input"],
            [
                "line vty 0 4",
                " exec-timeout 5 0",
                " transport input telnet",
                " transport input ssh",
            ],
        ]
        for vty_lines in safe_cases:
            with self.subTest(vty_lines=vty_lines):
                cfg = _build_config(vty_lines=vty_lines)
                report = security_audit.audit_config(cfg)
                self.assertTrue(report.passed)
                self.assertEqual(report.total_findings, 0)

    def test_no_password_encryption_rule(self) -> None:
        # Missing service password-encryption -> line_number=None
        missing_cfg = _build_config(password_encryption=[])
        missing_report = security_audit.audit_config(missing_cfg)
        self.assertEqual(missing_report.total_findings, 1)
        f_missing = missing_report.findings[0]
        self.assertEqual(f_missing.rule_id, "NO_PASSWORD_ENCRYPTION")
        self.assertEqual(f_missing.severity, security_audit.SEVERITY_MEDIUM)
        self.assertIsNone(f_missing.line_number)

        # Explicit negation -> line_number set
        explicit_cfg = _build_config(password_encryption=["no service password-encryption"])
        explicit_report = security_audit.audit_config(explicit_cfg)
        self.assertEqual(explicit_report.total_findings, 1)
        f_explicit = explicit_report.findings[0]
        self.assertEqual(f_explicit.rule_id, "NO_PASSWORD_ENCRYPTION")
        self.assertEqual(f_explicit.severity, security_audit.SEVERITY_MEDIUM)
        self.assertIsInstance(f_explicit.line_number, int)

        # Enablement passes
        enabled_cfg = _build_config(password_encryption=["service password-encryption"])
        self.assertTrue(security_audit.audit_config(enabled_cfg).passed)

        # Negation after enablement triggers with line_number set
        negated_after = _build_config(
            password_encryption=[
                "service password-encryption",
                "no service password-encryption",
            ]
        )
        negated_report = security_audit.audit_config(negated_after)
        self.assertEqual(negated_report.total_findings, 1)
        self.assertEqual(negated_report.findings[0].rule_id, "NO_PASSWORD_ENCRYPTION")
        self.assertIsInstance(negated_report.findings[0].line_number, int)

        # Enablement after negation passes
        enabled_after = _build_config(
            password_encryption=[
                "no service password-encryption",
                "service password-encryption",
            ]
        )
        self.assertTrue(security_audit.audit_config(enabled_after).passed)

    def test_snmp_default_community_rule(self) -> None:
        cases = [
            ("snmp-server community public RO", security_audit.SEVERITY_HIGH),
            ("snmp-server community private", security_audit.SEVERITY_HIGH),
            ("snmp-server community public RW", security_audit.SEVERITY_CRITICAL),
            ("snmp-server community private RW", security_audit.SEVERITY_CRITICAL),
        ]
        for line, expected_sev in cases:
            with self.subTest(line=line):
                cfg = _build_config(snmp_lines=[line])
                report = security_audit.audit_config(cfg)
                self.assertEqual(report.total_findings, 1)
                self.assertEqual(report.findings[0].rule_id, "SNMP_DEFAULT_COMMUNITY")
                self.assertEqual(report.findings[0].severity, expected_sev)

        # Safe custom community passes
        safe_cfg = _build_config(snmp_lines=["snmp-server community netops-ro RO"])
        self.assertTrue(security_audit.audit_config(safe_cfg).passed)

        # Negated default community removes finding
        negated_cfg = _build_config(
            snmp_lines=[
                "snmp-server community public RO",
                "no snmp-server community public",
            ]
        )
        self.assertTrue(security_audit.audit_config(negated_cfg).passed)

    def test_http_server_enabled_rule(self) -> None:
        enabled_cfg = _build_config(http_lines=["ip http server"])
        enabled_report = security_audit.audit_config(enabled_cfg)
        self.assertEqual(enabled_report.total_findings, 1)
        self.assertEqual(enabled_report.findings[0].rule_id, "HTTP_SERVER_ENABLED")
        self.assertEqual(enabled_report.findings[0].severity, security_audit.SEVERITY_HIGH)

        disabled_cfg = _build_config(http_lines=["no ip http server"])
        self.assertTrue(security_audit.audit_config(disabled_cfg).passed)

        re_disabled_cfg = _build_config(http_lines=["ip http server", "no ip http server"])
        self.assertTrue(security_audit.audit_config(re_disabled_cfg).passed)

        secure_only_cfg = _build_config(http_lines=["ip http secure-server"])
        self.assertTrue(security_audit.audit_config(secure_only_cfg).passed)

    def test_missing_exec_timeout_rule(self) -> None:
        failing_cases = [
            ["line vty 0 4", " transport input ssh"],
            ["line vty 0 4", " exec-timeout 0", " transport input ssh"],
            ["line vty 0 4", " exec-timeout 0 0", " transport input ssh"],
            ["line vty 0 4", " no exec-timeout", " transport input ssh"],
            [
                "line vty 0 4",
                " exec-timeout 5 0",
                " no exec-timeout",
                " transport input ssh",
            ],
        ]
        for vty_lines in failing_cases:
            with self.subTest(vty_lines=vty_lines):
                cfg = _build_config(vty_lines=vty_lines)
                report = security_audit.audit_config(cfg)
                self.assertEqual(report.total_findings, 1)
                self.assertEqual(report.findings[0].rule_id, "MISSING_EXEC_TIMEOUT")
                self.assertEqual(
                    report.findings[0].severity,
                    security_audit.SEVERITY_MEDIUM,
                )

        passing_cases = [
            ["line vty 0 4", " exec-timeout 5 0", " transport input ssh"],
            ["line vty 0 4", " exec-timeout 0 30", " transport input ssh"],
            [
                "line vty 0 4",
                " exec-timeout 0 0",
                " exec-timeout 10 0",
                " transport input ssh",
            ],
        ]
        for vty_lines in passing_cases:
            with self.subTest(vty_lines=vty_lines):
                cfg = _build_config(vty_lines=vty_lines)
                self.assertTrue(security_audit.audit_config(cfg).passed)

    def test_enable_password_insecure_rule(self) -> None:
        # Alone
        alone_cfg = _build_config(enable_lines=["enable password mysecret"])
        alone_report = security_audit.audit_config(alone_cfg)
        self.assertEqual(alone_report.total_findings, 1)
        self.assertEqual(alone_report.findings[0].rule_id, "ENABLE_PASSWORD_INSECURE")
        self.assertEqual(alone_report.findings[0].severity, security_audit.SEVERITY_HIGH)

        # Even when enable secret is also present
        both_cfg = _build_config(
            enable_lines=[
                "enable secret 5 $1$abc$hash",
                "enable password 7 0822455D0A16",
            ]
        )
        both_report = security_audit.audit_config(both_cfg)
        self.assertEqual(both_report.total_findings, 1)
        self.assertEqual(both_report.findings[0].rule_id, "ENABLE_PASSWORD_INSECURE")
        self.assertEqual(both_report.findings[0].severity, security_audit.SEVERITY_HIGH)

        # Enable secret alone passes
        secret_only = _build_config(enable_lines=["enable secret 5 $1$abc$hash"])
        self.assertTrue(security_audit.audit_config(secret_only).passed)

        # Neither present passes
        neither = _build_config(enable_lines=[])
        self.assertTrue(security_audit.audit_config(neither).passed)

        # Negation clears finding
        cleared = _build_config(
            enable_lines=["enable password mysecret", "no enable password"]
        )
        self.assertTrue(security_audit.audit_config(cleared).passed)

    def test_findings_sorted_by_severity(self) -> None:
        cfg = _build_config(
            password_encryption=[],  # MEDIUM
            enable_lines=["enable password weak"],  # HIGH
            http_lines=["ip http server"],  # HIGH
            snmp_lines=["snmp-server community public RW"],  # CRITICAL
            vty_lines=["line vty 0 4", " transport input telnet"],  # HIGH + MEDIUM
        )
        report = security_audit.audit_config(cfg)
        ranks = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        severities = [ranks[f.severity] for f in report.findings]

        self.assertEqual(severities, sorted(severities))
        self.assertEqual(report.findings[0].severity, security_audit.SEVERITY_CRITICAL)
        self.assertEqual(report.severity_counts["CRITICAL"], 1)
        self.assertEqual(report.severity_counts["HIGH"], 3)
        self.assertEqual(report.severity_counts["MEDIUM"], 2)


class TestSampleBackupsAndCli(unittest.TestCase):
    def test_audit_sample_before(self) -> None:
        report = security_audit.audit_file(SAMPLE_BEFORE)

        self.assertEqual(report.hostname, "edge-rtr1")
        self.assertFalse(report.passed)
        self.assertEqual(report.total_findings, 2)
        self.assertEqual(report.severity_counts.get("CRITICAL", 0), 0)
        self.assertEqual(report.severity_counts.get("HIGH", 0), 0)
        self.assertEqual(report.severity_counts["MEDIUM"], 2)
        self.assertEqual(
            {f.rule_id: f.severity for f in report.findings},
            {
                "NO_PASSWORD_ENCRYPTION": "MEDIUM",
                "MISSING_EXEC_TIMEOUT": "MEDIUM",
            },
        )

    def test_audit_sample_after(self) -> None:
        report = security_audit.audit_file(SAMPLE_AFTER)

        self.assertEqual(report.hostname, "edge-rtr1")
        self.assertFalse(report.passed)
        self.assertEqual(report.total_findings, 4)
        self.assertEqual(report.severity_counts["CRITICAL"], 1)
        self.assertEqual(report.severity_counts["HIGH"], 1)
        self.assertEqual(report.severity_counts["MEDIUM"], 2)

        self.assertEqual(report.findings[0].rule_id, "SNMP_DEFAULT_COMMUNITY")
        self.assertEqual(report.findings[0].severity, "CRITICAL")
        self.assertEqual(report.findings[1].rule_id, "TELNET_ENABLED")
        self.assertEqual(report.findings[1].severity, "HIGH")
        self.assertEqual(
            {(f.rule_id, f.severity) for f in report.findings[2:]},
            {
                ("NO_PASSWORD_ENCRYPTION", "MEDIUM"),
                ("MISSING_EXEC_TIMEOUT", "MEDIUM"),
            },
        )

    def test_format_text_and_json_audit(self) -> None:
        report = security_audit.audit_file(SAMPLE_AFTER)
        text = security_audit.format_text_audit(report)
        self.assertIn("edge-rtr1", text)
        self.assertIn("SNMP_DEFAULT_COMMUNITY", text)
        self.assertIn("TELNET_ENABLED", text)

        parsed = json.loads(security_audit.format_json_audit(report))
        self.assertEqual(parsed, report.to_dict())

    def test_cli_text_output(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = security_audit.main([str(SAMPLE_AFTER)])

        self.assertEqual(code, 0)
        output = stdout.getvalue()
        self.assertIn("edge-rtr1", output)
        self.assertIn("CRITICAL", output)
        self.assertIn("SNMP_DEFAULT_COMMUNITY", output)

    def test_cli_json_output(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = security_audit.main([str(SAMPLE_AFTER), "--json"])

        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["hostname"], "edge-rtr1")
        self.assertFalse(payload["passed"])
        self.assertEqual(payload["total_findings"], 4)
        self.assertEqual(payload["severity_counts"]["CRITICAL"], 1)
        self.assertEqual(payload["severity_counts"]["HIGH"], 1)
        self.assertEqual(payload["severity_counts"]["MEDIUM"], 2)
        self.assertEqual(len(payload["findings"]), 4)

    def test_cli_missing_file_returns_error(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = security_audit.main(["does_not_exist.cfg"])

        self.assertEqual(code, 1)
        self.assertTrue(stderr.getvalue().strip())

    def test_build_parser(self) -> None:
        parser = security_audit.build_parser()
        args = parser.parse_args(["backup.cfg", "--json"])
        self.assertTrue(args.json)


if __name__ == "__main__":
    unittest.main()
