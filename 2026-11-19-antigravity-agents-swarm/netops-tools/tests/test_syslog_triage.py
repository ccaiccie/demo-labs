"""Unit tests for syslog_triage.py."""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import syslog_triage  # noqa: E402


class TestDecodePri(unittest.TestCase):
    def test_valid_pri_values(self) -> None:
        self.assertEqual(syslog_triage.decode_pri(0), (0, "kern", 0, "emerg"))
        self.assertEqual(syslog_triage.decode_pri(189), (23, "local7", 5, "notice"))
        self.assertEqual(syslog_triage.decode_pri(185), (23, "local7", 1, "alert"))
        self.assertEqual(syslog_triage.decode_pri(191), (23, "local7", 7, "debug"))

    def test_out_of_range_pri_raises(self) -> None:
        with self.assertRaises(ValueError):
            syslog_triage.decode_pri(-1)
        with self.assertRaises(ValueError):
            syslog_triage.decode_pri(192)


class TestParseLine(unittest.TestCase):
    def test_parse_cisco_ios_line(self) -> None:
        line = (
            "<189>Nov 19 09:14:02 core-sw1 %LINK-3-UPDOWN: "
            "Interface GigabitEthernet1/0/24, changed state to down\r\n"
        )
        entry = syslog_triage.parse_line(line, line_number=1)
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry.line_number, 1)
        self.assertEqual(entry.pri, 189)
        self.assertEqual(entry.facility, 23)
        self.assertEqual(entry.facility_name, "local7")
        self.assertEqual(entry.pri_severity, 5)
        self.assertEqual(entry.pri_severity_name, "notice")
        self.assertEqual(entry.severity, 3)
        self.assertEqual(entry.severity_name, "err")
        self.assertEqual(entry.timestamp, "Nov 19 09:14:02")
        self.assertEqual(entry.host, "core-sw1")
        self.assertEqual(entry.tag, "%LINK-3-UPDOWN")
        self.assertEqual(entry.tag_facility, "LINK")
        self.assertEqual(entry.tag_severity, 3)
        self.assertEqual(entry.mnemonic, "UPDOWN")
        self.assertEqual(
            entry.message,
            "Interface GigabitEthernet1/0/24, changed state to down",
        )

    def test_parse_cisco_asa_line(self) -> None:
        line = (
            "<188>Nov 19 09:19:45 fw1 %ASA-4-106023: "
            'Deny tcp src outside:203.0.113.9/51516 dst inside:10.20.0.15/23 by access-group "OUTSIDE_IN"'
        )
        entry = syslog_triage.parse_line(line, line_number=10)
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry.facility_name, "local7")
        self.assertEqual(entry.severity, 4)
        self.assertEqual(entry.severity_name, "warning")
        self.assertEqual(entry.host, "fw1")
        self.assertEqual(entry.tag, "%ASA-4-106023")
        self.assertEqual(entry.tag_facility, "ASA")
        self.assertEqual(entry.tag_severity, 4)
        self.assertEqual(entry.mnemonic, "106023")

    def test_parse_single_digit_day_and_optional_year(self) -> None:
        line = "<190>Nov  5 2026 08:01:02 fw1: %ASA-6-302013: Built connection"
        entry = syslog_triage.parse_line(line, line_number=2)
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry.timestamp, "Nov  5 2026 08:01:02")
        self.assertEqual(entry.host, "fw1")
        self.assertEqual(entry.tag, "%ASA-6-302013")

    def test_parse_untagged_line_falls_back_to_pri_severity(self) -> None:
        line = "<187>Nov 19 09:30:00 core-sw1 Plain syslog message without tag"
        entry = syslog_triage.parse_line(line, line_number=3)
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertIsNone(entry.tag)
        self.assertIsNone(entry.tag_severity)
        self.assertEqual(entry.pri_severity, 3)
        self.assertEqual(entry.severity, 3)
        self.assertEqual(entry.severity_name, "err")
        self.assertEqual(entry.message, "Plain syslog message without tag")

    def test_unparsed_lines_return_none(self) -> None:
        bad_lines = [
            "garbage line without a priority",
            "<192>Nov 19 09:14:02 core-sw1 %LINK-3-UPDOWN: invalid pri",
            "<189>BadMonth 19 09:14:02 core-sw1 %LINK-3-UPDOWN: bad month",
        ]
        for bad in bad_lines:
            self.assertIsNone(syslog_triage.parse_line(bad))


class TestAlertDetection(unittest.TestCase):
    def test_tag_severity_0_to_3_triggers_alert(self) -> None:
        for tag_sev in (0, 1, 2, 3):
            # PRI 190 = local7.info (6), but tag severity is authoritative
            line = f"<190>Nov 19 09:00:00 rtr1 %SYS-{tag_sev}-TEST: severity test"
            entry = syslog_triage.parse_line(line)
            assert entry is not None
            self.assertEqual(entry.pri_severity, 6)
            self.assertEqual(entry.severity, tag_sev)
            self.assertIn("severity<=3", syslog_triage.get_alert_reasons(entry))

    def test_untagged_pri_severity_0_to_3_triggers_alert(self) -> None:
        line = "<186>Nov 19 09:00:00 rtr1 Untagged critical event"
        entry = syslog_triage.parse_line(line)
        assert entry is not None
        self.assertEqual(entry.severity, 2)
        self.assertEqual(syslog_triage.get_alert_reasons(entry), ["severity<=3"])

    def test_tag_severity_4_to_7_overrides_low_pri_severity(self) -> None:
        # PRI 186 = crit (2), but tag severity is 6 (info) -> not an alert, recorded as mismatch
        line = "<186>Nov 19 09:19:44 fw1 %ASA-6-302013: Built inbound TCP connection"
        report = syslog_triage.triage_lines([line])
        self.assertEqual(report.alerts, ())
        self.assertEqual(len(report.mismatches), 1)
        self.assertEqual(report.mismatches[0].pri_severity, 2)
        self.assertEqual(report.mismatches[0].tag_severity, 6)

    def test_severity_4_to_7_normal_event_not_alert(self) -> None:
        line = "<190>Nov 19 09:15:42 edge-rtr1 %SYS-6-LOGGINGHOST_STARTSTOP: Logging started"
        entry = syslog_triage.parse_line(line)
        assert entry is not None
        self.assertEqual(syslog_triage.get_alert_reasons(entry), [])

    def test_login_failed_triggers_alert_even_at_severity_4(self) -> None:
        line = (
            "<188>Nov 19 09:24:52 edge-rtr1 %SEC_LOGIN-4-LOGIN_FAILED: "
            "Login failed [user: admin]"
        )
        entry = syslog_triage.parse_line(line)
        assert entry is not None
        self.assertEqual(syslog_triage.get_alert_reasons(entry), ["LOGIN_FAILED"])

    def test_bpdu_guard_and_err_disable_deduplicated(self) -> None:
        line = (
            "<189>Nov 19 09:16:11 core-sw1 %PM-4-ERR_DISABLE: "
            "bpduguard error detected on Gi1/0/7, putting Gi1/0/7 in err-disable state"
        )
        report = syslog_triage.triage_lines([line])
        self.assertEqual(len(report.alerts), 1)
        self.assertEqual(report.alerts[0].reasons, ("BPDU_GUARD", "ERR_DISABLE"))

    def test_bpdu_guard_with_high_severity_records_both_reasons(self) -> None:
        line = (
            "<185>Nov 19 09:16:10 core-sw1 %SPANTREE-2-BLOCK_BPDUGUARD: "
            "Received BPDU on port Gi1/0/7 with BPDU Guard enabled. Disabling port."
        )
        entry = syslog_triage.parse_line(line)
        assert entry is not None
        self.assertEqual(
            syslog_triage.get_alert_reasons(entry),
            ["severity<=3", "BPDU_GUARD"],
        )


class TestSampleLogAndCli(unittest.TestCase):
    SAMPLE_LOG = PROJECT_ROOT / "samples" / "sample.log"

    def test_triage_sample_log(self) -> None:
        with self.SAMPLE_LOG.open("r", encoding="utf-8") as handle:
            report = syslog_triage.triage_lines(handle)

        self.assertEqual(report.total_lines, 19)
        self.assertEqual(report.parsed_lines, 18)
        self.assertEqual(report.unparsed_lines, 1)
        self.assertEqual(
            report.by_severity,
            {1: 1, 2: 1, 3: 2, 4: 5, 5: 7, 6: 2},
        )
        self.assertEqual(
            report.by_host,
            {"core-sw1": 7, "edge-rtr1": 6, "fw1": 3, "dist-sw2": 2},
        )
        # 4 events with tag severity 0..3 + 1 ERR_DISABLE/bpduguard (sev 4) + 2 LOGIN_FAILED (sev 4)
        self.assertEqual(len(report.alerts), 7)
        alert_lines = [item.entry.line_number for item in report.alerts]
        self.assertEqual(alert_lines, [1, 5, 6, 7, 16, 17, 18])

        self.assertEqual(len(report.mismatches), 10)
        mismatch_lines = [entry.line_number for entry in report.mismatches]
        self.assertEqual(mismatch_lines, [1, 3, 5, 6, 7, 8, 9, 13, 14, 15])

    def test_cli_text_output(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = syslog_triage.main([str(self.SAMPLE_LOG)])

        self.assertEqual(code, 0)
        output = stdout.getvalue()
        self.assertIn("Parsed lines:   18", output)
        self.assertIn("Unparsed lines: 1", output)
        self.assertIn("Summary by Severity", output)
        self.assertIn("Summary by Host", output)
        self.assertIn("ALERTS (7)", output)
        self.assertIn("MISMATCHES (10)", output)
        self.assertIn("%PLATFORM_ENV-1-FAN", output)
        self.assertIn("%PM-4-ERR_DISABLE", output)
        self.assertIn("%SEC_LOGIN-4-LOGIN_FAILED", output)

    def test_cli_json_output(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = syslog_triage.main([str(self.SAMPLE_LOG), "--json"])

        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["total_lines"], 19)
        self.assertEqual(payload["parsed_lines"], 18)
        self.assertEqual(payload["unparsed_lines"], 1)
        self.assertEqual(payload["summary"]["by_host"]["core-sw1"], 7)
        self.assertEqual(len(payload["alerts"]), 7)
        self.assertEqual(len(payload["mismatches"]), 10)
        self.assertIn("alert_reasons", payload["alerts"][0])

    def test_cli_stdin_input(self) -> None:
        sample_input = (
            "<185>Nov 19 09:26:00 core-sw1 %PLATFORM_ENV-1-FAN: Fan 2 failure detected\n"
            "\n"
            "not a syslog line\n"
        )
        stdout = io.StringIO()
        with mock.patch.object(sys, "stdin", io.StringIO(sample_input)):
            with contextlib.redirect_stdout(stdout):
                code = syslog_triage.main(["--json"])

        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["total_lines"], 2)
        self.assertEqual(payload["parsed_lines"], 1)
        self.assertEqual(payload["unparsed_lines"], 1)
        self.assertEqual(len(payload["alerts"]), 1)

    def test_cli_missing_file_returns_error(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = syslog_triage.main(["does_not_exist.log"])

        self.assertEqual(code, 1)
        self.assertIn("Error reading", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
