"""Unit tests for incidentbot.models."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from incidentbot.models import (
    EVENT_AUTH_FAILED,
    EVENT_INTERFACE_DOWN,
    INCIDENT_BGP_NEIGHBOR_DOWN,
    SEVERITY_CRITICAL,
    STATUS_OPEN,
    STATUS_RESOLVED,
    SYSLOG_SEVERITIES,
    VENDOR_CISCO,
    Event,
    Incident,
    format_human_timestamp,
    format_timestamp,
    normalize_timestamp,
)


class TestTimestampHelpers(unittest.TestCase):
    def test_normalize_timestamp_naive_and_aware(self) -> None:
        naive = datetime(2026, 11, 20, 12, 30, 45)
        self.assertEqual(
            normalize_timestamp(naive),
            datetime(2026, 11, 20, 12, 30, 45, tzinfo=timezone.utc),
        )

        tz_plus2 = timezone(timedelta(hours=2))
        aware = datetime(2026, 11, 20, 14, 30, 45, tzinfo=tz_plus2)
        self.assertEqual(
            normalize_timestamp(aware),
            datetime(2026, 11, 20, 12, 30, 45, tzinfo=timezone.utc),
        )

    def test_normalize_timestamp_iso_strings(self) -> None:
        dt_z = normalize_timestamp("2026-11-20T12:30:45.123456Z")
        self.assertEqual(
            dt_z,
            datetime(2026, 11, 20, 12, 30, 45, 123456, tzinfo=timezone.utc),
        )

        dt_offset = normalize_timestamp("2026-11-20T04:30:45-08:00")
        self.assertEqual(
            dt_offset,
            datetime(2026, 11, 20, 12, 30, 45, tzinfo=timezone.utc),
        )

        dt_naive_str = normalize_timestamp("2026-11-20T12:30:45")
        self.assertEqual(
            dt_naive_str,
            datetime(2026, 11, 20, 12, 30, 45, tzinfo=timezone.utc),
        )

    def test_normalize_timestamp_invalid_type(self) -> None:
        with self.assertRaises(TypeError):
            normalize_timestamp(12345)  # type: ignore[arg-type]

    def test_format_timestamp_fixed_width_ordering(self) -> None:
        t1 = datetime(2026, 11, 20, 12, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 11, 20, 12, 0, 0, 500, tzinfo=timezone.utc)
        t3 = datetime(2026, 11, 20, 12, 0, 1, tzinfo=timezone.utc)

        s1 = format_timestamp(t1)
        s2 = format_timestamp(t2)
        s3 = format_timestamp(t3)

        self.assertEqual(len(s1), 27)
        self.assertEqual(s1, "2026-11-20T12:00:00.000000Z")
        self.assertEqual(s2, "2026-11-20T12:00:00.000500Z")
        self.assertLess(s1, s2)
        self.assertLess(s2, s3)

        self.assertEqual(format_human_timestamp(t2), "2026-11-20T12:00:00Z")


class TestModels(unittest.TestCase):
    def test_syslog_severities(self) -> None:
        self.assertEqual(SYSLOG_SEVERITIES[0], "emergency")
        self.assertEqual(SYSLOG_SEVERITIES[3], "error")
        self.assertEqual(SYSLOG_SEVERITIES[7], "debug")
        self.assertEqual(len(SYSLOG_SEVERITIES), 8)

    def test_event_defaults_and_round_trip(self) -> None:
        ev = Event(
            timestamp=datetime(2026, 11, 20, 5, 0, 0),
            host="lab-core-r1",
            vendor=VENDOR_CISCO,
            kind=EVENT_INTERFACE_DOWN,
            severity="error",
            interface="GigabitEthernet0/1",
            raw="raw-line",
        )
        self.assertEqual(ev.timestamp.tzinfo, timezone.utc)
        self.assertIsNone(ev.peer)
        self.assertIsNone(ev.user)
        self.assertIsNone(ev.src_ip)

        as_dict = ev.to_dict()
        self.assertEqual(as_dict["timestamp"], "2026-11-20T05:00:00.000000Z")
        rehydrated = Event.from_dict(as_dict)
        self.assertEqual(rehydrated, ev)

    def test_event_from_dict_with_auth_fields(self) -> None:
        ev = Event.from_dict(
            {
                "timestamp": "2026-11-20T05:10:00-08:00",
                "host": "lab-fw-01",
                "vendor": "fortigate",
                "kind": EVENT_AUTH_FAILED,
                "severity": "warning",
                "user": "netadmin",
                "src_ip": "198.51.100.42",
            }
        )
        self.assertEqual(
            ev.timestamp,
            datetime(2026, 11, 20, 13, 10, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(ev.raw, "")
        self.assertEqual(ev.src_ip, "198.51.100.42")

    def test_incident_validation_and_round_trip(self) -> None:
        inc = Incident(
            id="inc-abc123def456",
            type=INCIDENT_BGP_NEIGHBOR_DOWN,
            severity=SEVERITY_CRITICAL,
            host="lab-edge-r2",
            key="bgp_neighbor_down:lab-edge-r2:203.0.113.10",
            first_seen=datetime(2026, 11, 20, 5, 0, 0),
            last_seen=datetime(2026, 11, 20, 5, 2, 0, tzinfo=timezone.utc),
            count=2,
            status=STATUS_OPEN,
            summary="BGP neighbor 203.0.113.10 on lab-edge-r2 went Down.",
        )
        self.assertEqual(inc.first_seen.tzinfo, timezone.utc)
        rehydrated = Incident.from_dict(inc.to_dict())
        self.assertEqual(rehydrated, inc)

        resolved = Incident.from_dict({**inc.to_dict(), "status": STATUS_RESOLVED})
        self.assertEqual(resolved.status, STATUS_RESOLVED)

    def test_incident_invalid_status_or_count(self) -> None:
        base = {
            "id": "inc-1",
            "type": INCIDENT_BGP_NEIGHBOR_DOWN,
            "severity": SEVERITY_CRITICAL,
            "host": "lab-core-r1",
            "key": "k",
            "first_seen": datetime(2026, 11, 20, 5, 0, 0, tzinfo=timezone.utc),
            "last_seen": datetime(2026, 11, 20, 5, 0, 0, tzinfo=timezone.utc),
            "count": 1,
            "status": STATUS_OPEN,
            "summary": "s",
        }
        with self.assertRaises(ValueError):
            Incident(**{**base, "status": "closed"})

        with self.assertRaises(ValueError):
            Incident(**{**base, "count": -1})


if __name__ == "__main__":
    unittest.main()
