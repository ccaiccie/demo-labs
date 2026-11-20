"""Unit tests for incidentbot.parser."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

import incidentbot.parser as parser_mod
from incidentbot.models import (
    EVENT_AUTH_FAILED,
    EVENT_AUTH_SUCCESS,
    EVENT_BGP_DOWN,
    EVENT_BGP_UP,
    EVENT_CONFIG_CHANGE,
    EVENT_INTERFACE_DOWN,
    EVENT_INTERFACE_UP,
    VENDOR_CISCO,
    VENDOR_FORTIGATE,
)
from incidentbot.parser import Event, parse_line, parse_lines


class TestParserExportsAndBasics(unittest.TestCase):
    def test_module_exports(self) -> None:
        self.assertIn("Event", parser_mod.__all__)
        self.assertIn("parse_line", parser_mod.__all__)
        self.assertIn("parse_lines", parser_mod.__all__)
        self.assertIs(Event, parser_mod.Event)

    def test_blank_and_garbage_lines_return_none(self) -> None:
        ref = datetime(2026, 11, 20, 12, 0, 0, tzinfo=timezone.utc)
        for line in (
            "",
            "   \t  ",
            "\r\n",
            "   \r\n",
            "<189>",
            "<189>   ",
            "not a syslog message",
            "<189>Nov 20 12:00:00 lab-core-r1 random unstructured log text",
            "<189>Feb 30 12:00:00 lab-core-r1 %LINK-3-UPDOWN: Interface GigabitEthernet0/1, changed state to down",
            'date=2026-11-20 devname="lab-fw-01" msg="unclosed quote',
            "foo=1 bar=2",
            "devname=lab-fw-01",
            "date=2026-11-20 stray_token devname=lab-fw-01",
        ):
            with self.subTest(line=line):
                self.assertIsNone(parse_line(line, reference_time=ref))

    def test_raw_strips_trailing_crlf_only(self) -> None:
        ref = datetime(2026, 11, 20, 12, 0, 0, tzinfo=timezone.utc)
        line = "<189>Nov 20 12:00:00 lab-core-r1 %LINK-3-UPDOWN: Interface GigabitEthernet0/1, changed state to down\r\n"
        ev = parse_line(line, reference_time=ref)
        self.assertIsNotNone(ev)
        assert ev is not None
        self.assertEqual(ev.raw, line[:-2])
        self.assertFalse(ev.raw.endswith("\n"))
        self.assertFalse(ev.raw.endswith("\r"))


class TestCiscoParser(unittest.TestCase):
    def setUp(self) -> None:
        self.ref = datetime(2026, 11, 20, 12, 30, 0, tzinfo=timezone.utc)

    def test_link_down_up_and_admin_down(self) -> None:
        down_line = "<187>Nov 20 12:00:01 lab-core-r1 %LINK-3-UPDOWN: Interface GigabitEthernet0/1, changed state to down"
        ev_down = parse_line(down_line, reference_time=self.ref)
        self.assertEqual(
            ev_down,
            Event(
                timestamp=datetime(2026, 11, 20, 12, 0, 1, tzinfo=timezone.utc),
                host="lab-core-r1",
                vendor=VENDOR_CISCO,
                kind=EVENT_INTERFACE_DOWN,
                severity="error",
                interface="GigabitEthernet0/1",
                raw=down_line,
            ),
        )

        admin_down = "<189>Nov 20 12:00:05 lab-core-r1: %LINK-3-UPDOWN: Interface TenGigabitEthernet1/0/2, changed state to administratively down"
        ev_admin = parse_line(admin_down, reference_time=self.ref)
        assert ev_admin is not None
        self.assertEqual(ev_admin.host, "lab-core-r1")
        self.assertEqual(ev_admin.kind, EVENT_INTERFACE_DOWN)
        self.assertEqual(ev_admin.interface, "TenGigabitEthernet1/0/2")
        self.assertEqual(ev_admin.severity, "error")

        up_line = "Nov 20 12:00:10 lab-core-r1 %LINK-4-UPDOWN: Interface GigabitEthernet0/1, changed state to up"
        ev_up = parse_line(up_line, reference_time=self.ref)
        assert ev_up is not None
        self.assertEqual(ev_up.kind, EVENT_INTERFACE_UP)
        self.assertEqual(ev_up.severity, "warning")
        self.assertEqual(ev_up.interface, "GigabitEthernet0/1")

    def test_lineproto_up_and_down(self) -> None:
        down_line = "<189>Nov 20 12:01:00 lab-dist-sw1 %LINEPROTO-5-UPDOWN: Line protocol on Interface Port-channel1, changed state to down"
        ev_down = parse_line(down_line, reference_time=self.ref)
        assert ev_down is not None
        self.assertEqual(ev_down.vendor, VENDOR_CISCO)
        self.assertEqual(ev_down.kind, EVENT_INTERFACE_DOWN)
        self.assertEqual(ev_down.severity, "notice")
        self.assertEqual(ev_down.interface, "Port-channel1")
        self.assertEqual(ev_down.host, "lab-dist-sw1")

        up_line = "<189>Nov 20 12:01:05 lab-dist-sw1 %LINEPROTO-5-UPDOWN: Line protocol on interface Vlan100, changed state to UP"
        ev_up = parse_line(up_line, reference_time=self.ref)
        assert ev_up is not None
        self.assertEqual(ev_up.kind, EVENT_INTERFACE_UP)
        self.assertEqual(ev_up.interface, "Vlan100")

    def test_bgp_adjchange_variants(self) -> None:
        down_line = "<189>Nov 20 12:02:00 lab-edge-r2 %BGP-5-ADJCHANGE: neighbor 203.0.113.10 Down BGP Notification sent"
        ev_down = parse_line(down_line, reference_time=self.ref)
        assert ev_down is not None
        self.assertEqual(ev_down.kind, EVENT_BGP_DOWN)
        self.assertEqual(ev_down.peer, "203.0.113.10")
        self.assertEqual(ev_down.severity, "notice")
        self.assertEqual(ev_down.host, "lab-edge-r2")

        up_line = "<189>Nov 20 12:03:00 lab-edge-r2 %BGP-5-ADJCHANGE: neighbor 203.0.113.10 Up"
        ev_up = parse_line(up_line, reference_time=self.ref)
        assert ev_up is not None
        self.assertEqual(ev_up.kind, EVENT_BGP_UP)
        self.assertEqual(ev_up.peer, "203.0.113.10")

        vrf_after = "%BGP-3-ADJCHANGE: neighbor 198.51.100.254 vpn vrf CUST_A Down Peer closed the session"
        ev_vrf_after = parse_line(vrf_after, reference_time=self.ref)
        assert ev_vrf_after is not None
        self.assertEqual(ev_vrf_after.kind, EVENT_BGP_DOWN)
        self.assertEqual(ev_vrf_after.peer, "198.51.100.254")
        self.assertEqual(ev_vrf_after.severity, "error")
        self.assertEqual(ev_vrf_after.host, "unknown")

        vrf_before = "%BGP-5-ADJCHANGE: vrf CORE_VRF neighbor 192.0.2.1 Up"
        ev_vrf_before = parse_line(vrf_before, reference_time=self.ref)
        assert ev_vrf_before is not None
        self.assertEqual(ev_vrf_before.kind, EVENT_BGP_UP)
        self.assertEqual(ev_vrf_before.peer, "192.0.2.1")

        vpn_vrf_before = "%BGP-5-ADJCHANGE: vpn vrf EDGE_VRF neighbor 192.0.2.2 Down Interface flap"
        ev_vpn_before = parse_line(vpn_vrf_before, reference_time=self.ref)
        assert ev_vpn_before is not None
        self.assertEqual(ev_vpn_before.kind, EVENT_BGP_DOWN)
        self.assertEqual(ev_vpn_before.peer, "192.0.2.2")

    def test_sec_login_failed_with_and_without_user(self) -> None:
        with_user = (
            "<188>Nov 20 12:04:00 lab-core-r1 %SEC_LOGIN-4-LOGIN_FAILED: "
            "Login failed [user: netadmin] [Source: 198.51.100.42] [localport: 22] [Reason: Login Authentication Failed]"
        )
        ev1 = parse_line(with_user, reference_time=self.ref)
        assert ev1 is not None
        self.assertEqual(ev1.kind, EVENT_AUTH_FAILED)
        self.assertEqual(ev1.severity, "warning")
        self.assertEqual(ev1.user, "netadmin")
        self.assertEqual(ev1.src_ip, "198.51.100.42")
        self.assertEqual(ev1.host, "lab-core-r1")

        empty_user = (
            "<188>Nov 20 12:04:05 lab-core-r1 %SEC_LOGIN-4-LOGIN_FAILED: "
            "Login failed [USER: ] [source: 198.51.100.99] [localport: 22]"
        )
        ev2 = parse_line(empty_user, reference_time=self.ref)
        assert ev2 is not None
        self.assertEqual(ev2.kind, EVENT_AUTH_FAILED)
        self.assertIsNone(ev2.user)
        self.assertEqual(ev2.src_ip, "198.51.100.99")

        no_source = "%SEC_LOGIN-3-LOGIN_FAILED: Login failed [user: ops]"
        ev3 = parse_line(no_source, reference_time=self.ref)
        assert ev3 is not None
        self.assertEqual(ev3.user, "ops")
        self.assertIsNone(ev3.src_ip)
        self.assertEqual(ev3.severity, "error")

    def test_single_digit_day_case_insensitive_month_and_default_year(self) -> None:
        line = "<189>nov  5 08:09:10 lab-core-r1 %LINK-3-UPDOWN: Interface GigabitEthernet0/0, changed state to down"
        ev = parse_line(
            line,
            reference_time=datetime(2026, 11, 20, 0, 0, tzinfo=timezone.utc),
            default_year=2024,
        )
        assert ev is not None
        self.assertEqual(
            ev.timestamp,
            datetime(2024, 11, 5, 8, 9, 10, tzinfo=timezone.utc),
        )

    def test_ios_sequence_number_and_internal_timestamps(self) -> None:
        line1 = (
            "1234: *Nov 20 12:00:01.123: %LINK-3-UPDOWN: "
            "Interface GigabitEthernet0/1, changed state to down"
        )
        ev1 = parse_line(line1, reference_time=self.ref)
        assert ev1 is not None
        self.assertEqual(ev1.host, "unknown")
        self.assertEqual(
            ev1.timestamp,
            datetime(2026, 11, 20, 12, 0, 1, 123000, tzinfo=timezone.utc),
        )

        line2 = (
            "<189>.Nov  5 12:00:01.005 UTC: %LINEPROTO-5-UPDOWN: "
            "Line protocol on Interface GigabitEthernet0/1, changed state to up"
        )
        ev2 = parse_line(line2, reference_time=self.ref)
        assert ev2 is not None
        self.assertEqual(ev2.host, "unknown")
        self.assertEqual(
            ev2.timestamp,
            datetime(2026, 11, 5, 12, 0, 1, 5000, tzinfo=timezone.utc),
        )

        line3 = (
            "Nov 20 12:00:01.450 UTC: %BGP-5-ADJCHANGE: "
            "neighbor 203.0.113.10 Up"
        )
        ev3 = parse_line(line3, reference_time=self.ref)
        assert ev3 is not None
        self.assertEqual(ev3.host, "unknown")
        self.assertEqual(ev3.peer, "203.0.113.10")
        self.assertEqual(
            ev3.timestamp,
            datetime(2026, 11, 20, 12, 0, 1, 450000, tzinfo=timezone.utc),
        )

        # Header timestamp takes precedence over internal IOS timestamp
        line4 = (
            "<189>Nov 20 12:00:00 lab-core-r1 456: *Nov 20 12:00:05.999 UTC: "
            "%LINK-3-UPDOWN: Interface GigabitEthernet0/1, changed state to up"
        )
        ev4 = parse_line(line4, reference_time=self.ref)
        assert ev4 is not None
        self.assertEqual(ev4.host, "lab-core-r1")
        self.assertEqual(
            ev4.timestamp,
            datetime(2026, 11, 20, 12, 0, 0, tzinfo=timezone.utc),
        )

    def test_optional_host_without_rfc3164_timestamp_and_pri_only(self) -> None:
        line_host = "lab-core-r1 %LINK-3-UPDOWN: Interface GigabitEthernet0/2, changed state to down"
        ev_host = parse_line(line_host, reference_time=self.ref)
        assert ev_host is not None
        self.assertEqual(ev_host.host, "lab-core-r1")
        self.assertEqual(ev_host.timestamp, self.ref)

        line_pri = "<187>%LINK-3-UPDOWN: Interface GigabitEthernet0/2, changed state to up"
        ev_pri = parse_line(line_pri, reference_time=self.ref)
        assert ev_pri is not None
        self.assertEqual(ev_pri.host, "unknown")
        self.assertEqual(ev_pri.timestamp, self.ref)

    def test_sys_config_i_variants(self) -> None:
        sample_line = (
            "<190>Nov 20 12:00:01 lab-edge-rtr-01 1001: %SYS-5-CONFIG_I: "
            "Configured from console by labops on vty0 (192.0.2.10)"
        )
        ev = parse_line(sample_line, reference_time=self.ref)
        self.assertEqual(
            ev,
            Event(
                timestamp=datetime(2026, 11, 20, 12, 0, 1, tzinfo=timezone.utc),
                host="lab-edge-rtr-01",
                vendor=VENDOR_CISCO,
                kind=EVENT_CONFIG_CHANGE,
                severity="notice",
                interface="vty0",
                user="labops",
                src_ip="192.0.2.10",
                raw=sample_line,
            ),
        )

        # Console config change with user and line but no source IP
        console_line = (
            "<189>Nov 20 12:05:00 lab-core-r1 %SYS-5-CONFIG_I: "
            "Configured from console by netadmin on console"
        )
        ev_console = parse_line(console_line, reference_time=self.ref)
        assert ev_console is not None
        self.assertEqual(ev_console.kind, EVENT_CONFIG_CHANGE)
        self.assertEqual(ev_console.host, "lab-core-r1")
        self.assertEqual(ev_console.severity, "notice")
        self.assertEqual(ev_console.user, "netadmin")
        self.assertEqual(ev_console.interface, "console")
        self.assertIsNone(ev_console.src_ip)

        # Line and source IP without username (e.g. non-AAA vty session)
        no_user_line = (
            "<189>Nov 20 12:06:00 lab-core-r1 %SYS-5-CONFIG_I: "
            "Configured from console by vty0 (198.51.100.5)"
        )
        ev_no_user = parse_line(no_user_line, reference_time=self.ref)
        assert ev_no_user is not None
        self.assertEqual(ev_no_user.kind, EVENT_CONFIG_CHANGE)
        self.assertIsNone(ev_no_user.user)
        self.assertEqual(ev_no_user.interface, "vty0")
        self.assertEqual(ev_no_user.src_ip, "198.51.100.5")

        # Minimal config-change message without user, line, or source IP
        minimal_line = (
            "<189>Nov 20 12:07:00 lab-core-r1 %SYS-5-CONFIG_I: "
            "Configured from console"
        )
        ev_minimal = parse_line(minimal_line, reference_time=self.ref)
        assert ev_minimal is not None
        self.assertEqual(ev_minimal.kind, EVENT_CONFIG_CHANGE)
        self.assertIsNone(ev_minimal.user)
        self.assertIsNone(ev_minimal.interface)
        self.assertIsNone(ev_minimal.src_ip)

    def test_unrecognized_cisco_mnemonic_returns_none(self) -> None:
        lines = [
            "<189>Nov 20 12:00:00 lab-core-r1 %SYS-5-RESTART: System restarted --",
            "%OSPF-5-ADJCHG: Process 1, Nbr 192.0.2.2 on GigabitEthernet0/1 from LOADING to FULL, Loading Done",
            "%LINK-3-UPDOWN: Unexpected format without interface",
            "%BGP-5-ADJCHANGE: neighbor 203.0.113.10 active",
        ]
        for line in lines:
            with self.subTest(line=line):
                self.assertIsNone(parse_line(line, reference_time=self.ref))


class TestFortiGateParser(unittest.TestCase):
    def setUp(self) -> None:
        self.ref = datetime(2026, 11, 20, 12, 30, 0, tzinfo=timezone.utc)

    def test_login_failed_with_tz_conversion_and_quoted_escapes(self) -> None:
        line = (
            '<188>date=2026-11-20 time=04:15:30 tz="-0800" devname="lab-fw-01" '
            'devid="FGVM010000000001" logid="0100032002" type="event" '
            'subtype="system" level="warning" logdesc="Admin login failed" '
            'user="netadmin" srcip=198.51.100.42 action="login" status="failed" '
            'msg="Administrator \\"netadmin\\" login failed from https(198.51.100.42)"'
        )
        ev = parse_line(line, reference_time=self.ref)
        self.assertEqual(
            ev,
            Event(
                timestamp=datetime(2026, 11, 20, 12, 15, 30, tzinfo=timezone.utc),
                host="lab-fw-01",
                vendor=VENDOR_FORTIGATE,
                kind=EVENT_AUTH_FAILED,
                severity="warning",
                user="netadmin",
                src_ip="198.51.100.42",
                raw=line,
            ),
        )

    def test_login_success_and_rfc3164_prefix(self) -> None:
        line = (
            '<190>Nov 20 12:20:00 lab-fw-02 date=2026-11-20 time=14:20:00 tz="+02:00" '
            'devname="lab-fw-02" type="event" level="information" '
            'logdesc="Admin login successful" user="secops" remip=203.0.113.55 '
            'action="login" status="success"'
        )
        ev = parse_line(line, reference_time=self.ref)
        assert ev is not None
        self.assertEqual(
            ev.timestamp,
            datetime(2026, 11, 20, 12, 20, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(ev.host, "lab-fw-02")
        self.assertEqual(ev.kind, EVENT_AUTH_SUCCESS)
        self.assertEqual(ev.severity, "info")
        self.assertEqual(ev.user, "secops")
        self.assertEqual(ev.src_ip, "203.0.113.55")

    def test_generic_logdesc_and_interface_events(self) -> None:
        logout_line = (
            'Nov 20 12:25:00 lab-fw-01 date=2026-11-20 time=12:25:00 tz="UTC" '
            'devname="lab-fw-01" type="event" level="informational" '
            'logdesc="Admin logout successful" user="" srcip="" remip=198.51.100.77'
        )
        ev_logout = parse_line(logout_line, reference_time=self.ref)
        assert ev_logout is not None
        self.assertEqual(ev_logout.kind, "admin_logout_successful")
        self.assertEqual(ev_logout.severity, "info")
        self.assertIsNone(ev_logout.user)
        self.assertEqual(ev_logout.src_ip, "198.51.100.77")

        link_down = (
            'devname="lab-fw-01" type="event" level="err" '
            'logdesc="Interface status changed" status="down" intf="port1" peer="203.0.113.9"'
        )
        ev_link = parse_line(link_down, reference_time=self.ref)
        assert ev_link is not None
        self.assertEqual(ev_link.kind, EVENT_INTERFACE_DOWN)
        self.assertEqual(ev_link.severity, "error")
        self.assertEqual(ev_link.interface, "port1")
        self.assertEqual(ev_link.peer, "203.0.113.9")
        self.assertEqual(ev_link.timestamp, self.ref)

        link_up = (
            'devid="FGVM01" type="event" level="notice" '
            'logdesc="Link monitor status" status="up" interface="wan1"'
        )
        ev_link_up = parse_line(link_up, reference_time=self.ref)
        assert ev_link_up is not None
        self.assertEqual(ev_link_up.kind, EVENT_INTERFACE_UP)
        self.assertEqual(ev_link_up.interface, "wan1")
        self.assertEqual(ev_link_up.host, "FGVM01")

    def test_eventtime_epoch_and_header_timestamp_fallbacks(self) -> None:
        # 19-digit nanosecond epoch
        target_dt = datetime(2026, 11, 20, 12, 0, 0, 123456, tzinfo=timezone.utc)
        ns_epoch = int(target_dt.timestamp()) * 1_000_000_000 + 123456789
        ns_line = f'devname="lab-fw-01" eventtime={ns_epoch} logdesc="System rebooted"'
        ev_ns = parse_line(ns_line, reference_time=self.ref)
        assert ev_ns is not None
        self.assertEqual(ev_ns.timestamp, target_dt)
        self.assertEqual(ev_ns.kind, "system_rebooted")

        # Millisecond epoch
        ms_epoch = int(datetime(2026, 11, 20, 12, 0, 0, tzinfo=timezone.utc).timestamp()) * 1000 + 500
        ms_line = f'devname="lab-fw-01" eventtime={ms_epoch} logdesc="HA failover"'
        ev_ms = parse_line(ms_line, reference_time=self.ref)
        assert ev_ms is not None
        self.assertEqual(
            ev_ms.timestamp,
            datetime(2026, 11, 20, 12, 0, 0, 500000, tzinfo=timezone.utc),
        )

        # Seconds epoch
        sec_epoch = int(datetime(2026, 11, 20, 12, 0, 0, tzinfo=timezone.utc).timestamp())
        sec_line = f'devname="lab-fw-01" eventtime={sec_epoch} logid="0100032000"'
        ev_sec = parse_line(sec_line, reference_time=self.ref)
        assert ev_sec is not None
        self.assertEqual(
            ev_sec.timestamp,
            datetime(2026, 11, 20, 12, 0, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(ev_sec.kind, "event")

        # Header timestamp takes precedence over eventtime when date/time absent
        hdr_line = (
            f'Nov 20 12:10:00 192.0.2.50 devid="FGVM01" eventtime={sec_epoch} '
            'logdesc="Configuration changed"'
        )
        ev_hdr = parse_line(hdr_line, reference_time=self.ref)
        assert ev_hdr is not None
        self.assertEqual(
            ev_hdr.timestamp,
            datetime(2026, 11, 20, 12, 10, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(ev_hdr.host, "192.0.2.50")

    def test_severity_normalization_and_fallbacks(self) -> None:
        cases = [
            ("emerg", "emergency"),
            ("alert", "alert"),
            ("crit", "critical"),
            ("err", "error"),
            ("warn", "warning"),
            ("notice", "notice"),
            ("information", "info"),
            ("debug", "debug"),
        ]
        for raw_level, expected in cases:
            with self.subTest(level=raw_level):
                ev = parse_line(
                    f'devname="lab-fw-01" level="{raw_level}" logdesc="Test event"',
                    reference_time=self.ref,
                )
                assert ev is not None
                self.assertEqual(ev.severity, expected)

        # Fallback to <PRI> % 8 (187 % 8 = 3 -> error)
        ev_pri = parse_line(
            '<187>devname="lab-fw-01" logdesc="Test event"',
            reference_time=self.ref,
        )
        assert ev_pri is not None
        self.assertEqual(ev_pri.severity, "error")

        # Fallback to "notice" when neither level nor <PRI> is present
        ev_default = parse_line(
            'devname="lab-fw-01" logdesc="Test event"',
            reference_time=self.ref,
        )
        assert ev_default is not None
        self.assertEqual(ev_default.severity, "notice")

    def test_ignore_non_event_types_unless_login_failed(self) -> None:
        traffic = (
            'date=2026-11-20 time=12:00:00 devname="lab-fw-01" type="traffic" '
            'subtype="forward" level="notice" srcip=198.51.100.10 dstip=203.0.113.10 '
            'action="accept" msg="%LINK-3-UPDOWN: Interface eth0, changed state to down"'
        )
        self.assertIsNone(parse_line(traffic, reference_time=self.ref))

        utm_login_failed = (
            'date=2026-11-20 time=12:00:00 devname="lab-fw-01" type="utm" '
            'level="alert" action="login" status="failed" user="admin" srcip=198.51.100.88'
        )
        ev = parse_line(utm_login_failed, reference_time=self.ref)
        assert ev is not None
        self.assertEqual(ev.kind, EVENT_AUTH_FAILED)
        self.assertEqual(ev.severity, "alert")
        self.assertEqual(ev.user, "admin")
        self.assertEqual(ev.src_ip, "198.51.100.88")

    def test_login_failed_logdesc_with_success_status_not_auth_failed(self) -> None:
        line = (
            'devname="lab-fw-01" type="event" logdesc="Login failed alert cleared" '
            'action="clear" status="success"'
        )
        ev = parse_line(line, reference_time=self.ref)
        assert ev is not None
        self.assertEqual(ev.kind, "login_failed_alert_cleared")

    def test_tz_z_and_escaped_backslash(self) -> None:
        line = (
            'date=2026-11-20 time=12:00:00 tz="Z" devname="lab-fw-01" '
            'logdesc="Admin login failed" status="failed" '
            'msg="path C:\\\\admin\\\\"'
        )
        ev = parse_line(line, reference_time=self.ref)
        assert ev is not None
        self.assertEqual(ev.timestamp, datetime(2026, 11, 20, 12, 0, 0, tzinfo=timezone.utc))
        self.assertEqual(ev.kind, EVENT_AUTH_FAILED)


class TestParseLines(unittest.TestCase):
    def test_parse_lines_filters_blank_garbage_and_unrecognized(self) -> None:
        ref = datetime(2026, 11, 20, 12, 0, 0, tzinfo=timezone.utc)
        lines = (
            "",
            "   ",
            "<189>Nov 20 12:00:01 lab-core-r1 %LINK-3-UPDOWN: Interface GigabitEthernet0/1, changed state to down",
            "garbage line",
            "<189>Nov 20 12:00:02 lab-core-r1 %SYS-5-RESTART: System restarted --",
            'date=2026-11-20 time=12:00:03 devname="lab-fw-01" type="traffic" action="accept"',
            'date=2026-11-20 time=12:00:04 devname="lab-fw-01" type="event" action="login" status="failed" user="ops" srcip=198.51.100.42',
        )
        events = parse_lines(lines, reference_time=ref)
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].vendor, VENDOR_CISCO)
        self.assertEqual(events[0].kind, EVENT_INTERFACE_DOWN)
        self.assertEqual(events[1].vendor, VENDOR_FORTIGATE)
        self.assertEqual(events[1].kind, EVENT_AUTH_FAILED)

    def test_naive_and_offset_reference_time_normalized(self) -> None:
        tz_minus8 = timezone(timedelta(hours=-8))
        ref_offset = datetime(2026, 11, 20, 4, 0, 0, tzinfo=tz_minus8)
        ev = parse_line(
            "%LINK-3-UPDOWN: Interface GigabitEthernet0/1, changed state to up",
            reference_time=ref_offset,
        )
        assert ev is not None
        self.assertEqual(
            ev.timestamp,
            datetime(2026, 11, 20, 12, 0, 0, tzinfo=timezone.utc),
        )


if __name__ == "__main__":
    unittest.main()
