"""End-to-end integration tests for parser, correlator, and store."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from incidentbot import (
    INCIDENT_AUTH_BRUTE_FORCE,
    INCIDENT_BGP_NEIGHBOR_DOWN,
    INCIDENT_INTERFACE_FLAP,
    STATUS_OPEN,
    STATUS_RESOLVED,
    Correlator,
    IncidentStore,
    parse_lines,
)


def _ingest(
    lines: list[str],
    correlator: Correlator,
    store: IncidentStore,
    *,
    default_year: int = 2026,
) -> None:
    events = parse_lines(lines, default_year=default_year)
    for event in events:
        store.add_event(event)
        for incident in correlator.process_event(event):
            store.upsert_incident(incident)


class TestEngineIntegration(unittest.TestCase):
    def test_interface_flap_pipeline_and_manual_resolve(self) -> None:
        lines = [
            "<187>Nov 20 12:00:00 lab-core-r1 %LINK-3-UPDOWN: Interface GigabitEthernet0/1, changed state to down",
            "<189>Nov 20 12:00:05 lab-core-r1 %LINEPROTO-5-UPDOWN: Line protocol on Interface GigabitEthernet0/1, changed state to down",
            "<187>Nov 20 12:00:30 lab-core-r1 %LINK-3-UPDOWN: Interface GigabitEthernet0/1, changed state to up",
            "<189>Nov 20 12:00:35 lab-core-r1 %LINEPROTO-5-UPDOWN: Line protocol on Interface GigabitEthernet0/1, changed state to up",
        ]
        correlator = Correlator()
        with IncidentStore() as store:
            _ingest(lines, correlator, store)

            self.assertEqual(store.count_events(), 4)
            open_flaps = store.list_incidents(
                status=STATUS_OPEN,
                host="lab-core-r1",
                incident_type=INCIDENT_INTERFACE_FLAP,
            )
            self.assertEqual(len(open_flaps), 1)
            inc = open_flaps[0]
            self.assertEqual(inc.count, 4)
            self.assertEqual(inc.severity, "medium")
            self.assertIn("GigabitEthernet0/1", inc.summary)
            self.assertIn("lab-core-r1", inc.summary)

            resolved = store.resolve_incident(
                inc.id,
                resolved_at=datetime(2026, 11, 20, 12, 2, 0, tzinfo=timezone.utc),
            )
            self.assertIsNotNone(resolved)
            assert resolved is not None
            self.assertEqual(resolved.status, STATUS_RESOLVED)
            self.assertEqual(
                store.list_incidents(status=STATUS_OPEN, host="lab-core-r1"), []
            )
            self.assertEqual(
                len(store.list_incidents(status=STATUS_RESOLVED, host="lab-core-r1")),
                1,
            )

    def test_bgp_down_then_up_auto_resolves_in_store(self) -> None:
        down_lines = [
            "<189>Nov 20 12:10:00 lab-edge-r2 %BGP-5-ADJCHANGE: neighbor 203.0.113.10 Down BGP Notification sent",
        ]
        up_lines = [
            "<189>Nov 20 12:12:30 lab-edge-r2 %BGP-5-ADJCHANGE: neighbor 203.0.113.10 Up",
        ]
        correlator = Correlator()
        with IncidentStore() as store:
            _ingest(down_lines, correlator, store)
            opened = store.list_incidents(
                status=STATUS_OPEN,
                incident_type=INCIDENT_BGP_NEIGHBOR_DOWN,
            )
            self.assertEqual(len(opened), 1)
            self.assertEqual(opened[0].severity, "critical")
            self.assertEqual(opened[0].count, 1)

            _ingest(up_lines, correlator, store)
            self.assertEqual(store.count_incidents(status=STATUS_OPEN), 0)
            resolved = store.get_incident(opened[0].id)
            self.assertIsNotNone(resolved)
            assert resolved is not None
            self.assertEqual(resolved.status, STATUS_RESOLVED)
            self.assertEqual(resolved.count, 2)
            self.assertIn("recovered", resolved.summary.lower())

    def test_cross_vendor_brute_force_and_idempotent_replay(self) -> None:
        lines = [
            '<188>Nov 20 12:20:00 lab-core-r1 %SEC_LOGIN-4-LOGIN_FAILED: Login failed [user: netadmin] [Source: 198.51.100.42] [localport: 22]',
            'date=2026-11-20 time=12:20:10 tz="UTC" devname="lab-fw-01" type="event" level="warning" logdesc="Admin login failed" user="admin" srcip=198.51.100.42 action="login" status="failed"',
            '<188>Nov 20 12:20:20 lab-core-r1 %SEC_LOGIN-4-LOGIN_FAILED: Login failed [user: ops] [Source: 198.51.100.42] [localport: 22]',
            'date=2026-11-20 time=12:20:30 tz="UTC" devname="lab-fw-02" type="event" level="warning" logdesc="Admin login failed" user="secops" srcip=198.51.100.42 action="login" status="failed"',
            'date=2026-11-20 time=12:20:40 tz="UTC" devname="lab-fw-01" type="event" level="warning" logdesc="Admin login failed" user="root" srcip=198.51.100.42 action="login" status="failed"',
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "netops.db"
            with IncidentStore(db_path) as store:
                corr1 = Correlator()
                _ingest(lines, corr1, store)

                self.assertEqual(store.count_events(), 5)
                self.assertEqual(store.count_incidents(), 1)

                by_fw01 = store.list_incidents(host="lab-fw-01")
                by_core = store.list_incidents(host="lab-core-r1")
                by_fw02 = store.list_incidents(host="lab-fw-02")
                self.assertEqual(len(by_fw01), 1)
                self.assertEqual(by_fw01, by_core)
                self.assertEqual(by_fw01, by_fw02)

                inc = by_fw01[0]
                self.assertEqual(inc.type, INCIDENT_AUTH_BRUTE_FORCE)
                self.assertEqual(inc.severity, "high")
                self.assertEqual(inc.host, "lab-core-r1,lab-fw-01,lab-fw-02")
                self.assertEqual(inc.count, 5)
                self.assertIn("198.51.100.42", inc.summary)
                self.assertIn("cisco", inc.summary)
                self.assertIn("fortigate", inc.summary)

                # Replay the same lines through a fresh Correlator into the same store
                corr2 = Correlator()
                for incident in corr2.process_events(parse_lines(lines, default_year=2026)):
                    store.upsert_incident(incident)

                self.assertEqual(store.count_incidents(), 1)
                self.assertEqual(store.get_incident(inc.id), inc)


if __name__ == "__main__":
    unittest.main()
