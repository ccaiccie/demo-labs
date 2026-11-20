"""Unit tests for incidentbot.store."""

from __future__ import annotations

import sqlite3
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from incidentbot.models import (
    EVENT_AUTH_FAILED,
    EVENT_BGP_DOWN,
    EVENT_INTERFACE_DOWN,
    EVENT_INTERFACE_UP,
    INCIDENT_AUTH_BRUTE_FORCE,
    INCIDENT_BGP_NEIGHBOR_DOWN,
    INCIDENT_INTERFACE_FLAP,
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
    SEVERITY_MEDIUM,
    STATUS_OPEN,
    STATUS_RESOLVED,
    VENDOR_CISCO,
    VENDOR_FORTIGATE,
    Event,
    Incident,
)
from incidentbot.store import IncidentStore


def _make_event(
    *,
    minute: int = 0,
    microsecond: int = 0,
    host: str = "lab-core-r1",
    vendor: str = VENDOR_CISCO,
    kind: str = EVENT_INTERFACE_DOWN,
    severity: str = "error",
    interface: str | None = "GigabitEthernet0/1",
    peer: str | None = None,
    user: str | None = None,
    src_ip: str | None = None,
    raw: str = "sample syslog line",
) -> Event:
    return Event(
        timestamp=datetime(2026, 11, 20, 12, minute, 0, microsecond, tzinfo=timezone.utc),
        host=host,
        vendor=vendor,
        kind=kind,
        severity=severity,
        interface=interface,
        peer=peer,
        user=user,
        src_ip=src_ip,
        raw=raw,
    )


def _make_incident(
    incident_id: str = "inc-001",
    *,
    incident_type: str = INCIDENT_INTERFACE_FLAP,
    severity: str = SEVERITY_HIGH,
    host: str = "lab-core-r1",
    key: str = "interface_flap:lab-core-r1:GigabitEthernet0/1",
    first_minute: int = 0,
    last_minute: int = 5,
    count: int = 3,
    status: str = STATUS_OPEN,
    summary: str = "Interface GigabitEthernet0/1 flapped on lab-core-r1",
) -> Incident:
    return Incident(
        id=incident_id,
        type=incident_type,
        severity=severity,
        host=host,
        key=key,
        first_seen=datetime(2026, 11, 20, 12, first_minute, 0, tzinfo=timezone.utc),
        last_seen=datetime(2026, 11, 20, 12, last_minute, 0, tzinfo=timezone.utc),
        count=count,
        status=status,
        summary=summary,
    )


class TestIncidentStoreLifecycleAndPersistence(unittest.TestCase):
    def test_context_manager_and_idempotent_close(self) -> None:
        store = IncidentStore()
        with store as entered:
            self.assertIs(entered, store)
            row_id = store.add_event(_make_event())
            self.assertEqual(row_id, 1)

        # Second close must remain safe and idempotent.
        store.close()

        with self.assertRaises(sqlite3.ProgrammingError):
            store.count_events()

        with self.assertRaises(sqlite3.ProgrammingError):
            with store:
                pass

    def test_file_backed_persistence_creates_parents_wal_and_reopens(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "nested" / "db" / "incidents.db"
            event = _make_event(
                host="lab-edge-r2",
                kind=EVENT_BGP_DOWN,
                interface=None,
                peer="203.0.113.10",
                raw="BGP neighbor 203.0.113.10 down",
            )
            incident = _make_incident(
                "inc-bgp-1",
                incident_type=INCIDENT_BGP_NEIGHBOR_DOWN,
                severity=SEVERITY_CRITICAL,
                host="lab-edge-r2",
                key="bgp_neighbor_down:lab-edge-r2:203.0.113.10",
            )

            with IncidentStore(db_path) as store:
                self.assertTrue(db_path.exists())
                event_id = store.add_event(event)
                store.upsert_incident(incident)

            # Verify WAL journal mode persisted on the SQLite file.
            check_conn = sqlite3.connect(str(db_path))
            try:
                journal_mode = check_conn.execute("PRAGMA journal_mode").fetchone()[0]
                self.assertEqual(str(journal_mode).lower(), "wal")
            finally:
                check_conn.close()

            with IncidentStore(db_path) as reopened:
                self.assertEqual(reopened.count_events(), 1)
                self.assertEqual(reopened.get_event(event_id), event)
                self.assertEqual(reopened.count_incidents(), 1)
                self.assertEqual(reopened.get_incident("inc-bgp-1"), incident)


class TestIncidentStoreEvents(unittest.TestCase):
    def test_add_get_and_count_events(self) -> None:
        with IncidentStore() as store:
            self.assertEqual(store.count_events(), 0)
            self.assertIsNone(store.get_event(1))

            ev1 = _make_event(minute=1, host="lab-core-r1", src_ip="192.0.2.10")
            ev2 = _make_event(
                minute=2,
                host="lab-fw-01",
                vendor=VENDOR_FORTIGATE,
                kind=EVENT_AUTH_FAILED,
                severity="warning",
                interface=None,
                user="netadmin",
                src_ip="198.51.100.42",
                raw="FortiGate auth failure from 198.51.100.42",
            )

            id1 = store.add_event(ev1)
            id2 = store.add_event(ev2)

            self.assertEqual(id1, 1)
            self.assertEqual(id2, 2)
            self.assertEqual(store.count_events(), 2)
            self.assertEqual(store.get_event(id1), ev1)
            self.assertEqual(store.get_event(id2), ev2)
            self.assertIsNone(store.get_event(999))

    def test_add_events_batch_and_transaction_rollback(self) -> None:
        with IncidentStore() as store:
            self.assertEqual(store.add_events([]), [])
            self.assertEqual(store.count_events(), 0)

            batch = (
                _make_event(minute=1, raw="ev1"),
                _make_event(minute=2, raw="ev2"),
                _make_event(minute=3, raw="ev3"),
            )
            ids = store.add_events(batch)
            self.assertEqual(ids, [1, 2, 3])
            self.assertEqual(store.count_events(), 3)

            def failing_stream():
                yield _make_event(minute=4, raw="should-rollback")
                raise RuntimeError("mid-stream failure")

            with self.assertRaises(RuntimeError):
                store.add_events(failing_stream())

            # Transaction rollback must preserve the prior 3 rows only.
            self.assertEqual(store.count_events(), 3)
            self.assertIsNone(store.get_event(4))

    def test_list_events_ordering_filters_and_pagination(self) -> None:
        with IncidentStore() as store:
            e1 = _make_event(
                minute=10,
                host="lab-core-r1",
                vendor=VENDOR_CISCO,
                kind=EVENT_INTERFACE_DOWN,
                severity="error",
                raw="e1",
            )
            e2 = _make_event(
                minute=20,
                host="lab-fw-01",
                vendor=VENDOR_FORTIGATE,
                kind=EVENT_AUTH_FAILED,
                severity="warning",
                interface=None,
                user="operator1",
                src_ip="198.51.100.42",
                raw="e2",
            )
            e3 = _make_event(
                minute=20,
                host="lab-fw-01",
                vendor=VENDOR_FORTIGATE,
                kind=EVENT_AUTH_FAILED,
                severity="warning",
                interface=None,
                user="operator2",
                src_ip="198.51.100.50",
                raw="e3",
            )
            e4 = _make_event(
                minute=30,
                host="lab-edge-r2",
                vendor=VENDOR_CISCO,
                kind=EVENT_BGP_DOWN,
                severity="critical",
                interface=None,
                peer="203.0.113.10",
                src_ip="203.0.113.10",
                raw="e4",
            )
            store.add_events([e1, e2, e3, e4])

            # Ordered timestamp DESC, id DESC (e3 inserted after e2 at minute 20).
            self.assertEqual(store.list_events(), [e4, e3, e2, e1])

            # Equality filters.
            self.assertEqual(store.list_events(host="lab-fw-01"), [e3, e2])
            self.assertEqual(store.list_events(vendor=VENDOR_CISCO), [e4, e1])
            self.assertEqual(store.list_events(kind=EVENT_AUTH_FAILED), [e3, e2])
            self.assertEqual(store.list_events(severity="critical"), [e4])
            self.assertEqual(store.list_events(src_ip="198.51.100.42"), [e2])
            self.assertEqual(
                store.list_events(
                    host="lab-fw-01",
                    vendor=VENDOR_FORTIGATE,
                    kind=EVENT_AUTH_FAILED,
                    severity="warning",
                    src_ip="198.51.100.50",
                ),
                [e3],
            )

            # Time window filters (datetime and offset ISO string).
            tz_minus8 = timezone(timedelta(hours=-8))
            since_dt = datetime(2026, 11, 20, 4, 20, 0, tzinfo=tz_minus8)  # 12:20Z
            until_str = "2026-11-20T12:20:00Z"
            self.assertEqual(
                store.list_events(since=since_dt, until=until_str),
                [e3, e2],
            )
            self.assertEqual(
                store.list_events(since="2026-11-20T12:31:00Z"),
                [],
            )

            # Pagination combinations.
            self.assertEqual(store.list_events(limit=0), [])
            self.assertEqual(store.list_events(limit=2, offset=1), [e3, e2])
            self.assertEqual(store.list_events(limit=None, offset=2), [e2, e1])
            self.assertEqual(store.list_events(limit=5, offset=10), [])

            with self.assertRaises(ValueError):
                store.list_events(limit=-1)
            with self.assertRaises(ValueError):
                store.list_events(offset=-1)


class TestIncidentStoreIncidents(unittest.TestCase):
    def test_upsert_get_and_count_incidents(self) -> None:
        with IncidentStore() as store:
            self.assertEqual(store.count_incidents(), 0)
            self.assertIsNone(store.get_incident("missing"))

            inc = _make_incident("inc-100", count=2, status=STATUS_OPEN)
            inserted = store.upsert_incident(inc)
            self.assertEqual(inserted, inc)
            self.assertEqual(store.count_incidents(), 1)
            self.assertEqual(store.count_incidents(status=STATUS_OPEN), 1)
            self.assertEqual(store.count_incidents(status=STATUS_RESOLVED), 0)

            updated = _make_incident(
                "inc-100",
                severity=SEVERITY_CRITICAL,
                host="lab-core-r1,lab-dist-sw1",
                last_minute=15,
                count=5,
                status=STATUS_OPEN,
                summary="Updated summary",
            )
            stored = store.upsert_incident(updated)
            self.assertEqual(stored, updated)
            self.assertEqual(store.count_incidents(), 1)
            self.assertEqual(store.get_incident("inc-100"), updated)

    def test_list_incidents_filters_multihost_ordering_and_pagination(self) -> None:
        with IncidentStore() as store:
            i_single = _make_incident(
                "inc-b",
                incident_type=INCIDENT_AUTH_BRUTE_FORCE,
                severity=SEVERITY_MEDIUM,
                host="lab-fw-01",
                key="auth_brute_force:lab-fw-01:198.51.100.42",
                last_minute=20,
                status=STATUS_OPEN,
            )
            i_multi_suffix = _make_incident(
                "inc-a",
                incident_type=INCIDENT_BGP_NEIGHBOR_DOWN,
                severity=SEVERITY_CRITICAL,
                host="lab-core-r1,lab-fw-01",
                key="bgp:shared:203.0.113.10",
                last_minute=20,
                status=STATUS_OPEN,
            )
            i_multi_middle = _make_incident(
                "inc-c",
                incident_type=INCIDENT_INTERFACE_FLAP,
                severity=SEVERITY_HIGH,
                host="lab-core-r1,lab-fw-01,lab-edge-r2",
                key="flap:shared",
                last_minute=10,
                status=STATUS_RESOLVED,
            )
            i_collision = _make_incident(
                "inc-d",
                incident_type=INCIDENT_AUTH_BRUTE_FORCE,
                severity=SEVERITY_HIGH,
                host="lab-fw-010",
                key="auth_brute_force:lab-fw-010:192.0.2.20",
                last_minute=30,
                status=STATUS_OPEN,
            )
            i_prefix_collision = _make_incident(
                "inc-e",
                incident_type=INCIDENT_AUTH_BRUTE_FORCE,
                severity=SEVERITY_MEDIUM,
                host="x-lab-fw-01",
                key="auth_brute_force:x-lab-fw-01:192.0.2.11",
                last_minute=25,
                status=STATUS_OPEN,
            )
            i_multi_collision = _make_incident(
                "inc-f",
                incident_type=INCIDENT_INTERFACE_FLAP,
                severity=SEVERITY_HIGH,
                host="lab-core-r1,lab-fw-010",
                key="flap:collision",
                last_minute=5,
                status=STATUS_OPEN,
            )
            for inc in (
                i_single,
                i_multi_suffix,
                i_multi_middle,
                i_collision,
                i_prefix_collision,
                i_multi_collision,
            ):
                store.upsert_incident(inc)

            # Ordering: last_seen DESC, id ASC (at minute 20: inc-a before inc-b).
            self.assertEqual(
                [i.id for i in store.list_incidents()],
                ["inc-d", "inc-e", "inc-a", "inc-b", "inc-c", "inc-f"],
            )

            # Multi-host match must include lab-fw-01 members and exclude lab-fw-010 / x-lab-fw-01.
            matched_fw01 = store.list_incidents(host="lab-fw-01")
            self.assertEqual([i.id for i in matched_fw01], ["inc-a", "inc-b", "inc-c"])

            # LIKE wildcards must not be interpreted specially.
            self.assertEqual(store.list_incidents(host="lab-fw-%"), [])
            self.assertEqual(store.list_incidents(host="lab-fw-0_"), [])

            # Other filters.
            self.assertEqual(
                [i.id for i in store.list_incidents(status=STATUS_RESOLVED)],
                ["inc-c"],
            )
            self.assertEqual(
                [
                    i.id
                    for i in store.list_incidents(
                        incident_type=INCIDENT_AUTH_BRUTE_FORCE,
                        severity=SEVERITY_MEDIUM,
                    )
                ],
                ["inc-e", "inc-b"],
            )
            self.assertEqual(
                [i.id for i in store.list_incidents(key="bgp:shared:203.0.113.10")],
                ["inc-a"],
            )

            # Time bounds on last_seen.
            self.assertEqual(
                [
                    i.id
                    for i in store.list_incidents(
                        since="2026-11-20T04:20:00-08:00",
                        until=datetime(2026, 11, 20, 12, 25, 0, tzinfo=timezone.utc),
                    )
                ],
                ["inc-e", "inc-a", "inc-b"],
            )

            # Pagination.
            self.assertEqual(store.list_incidents(limit=0), [])
            self.assertEqual(
                [i.id for i in store.list_incidents(limit=2, offset=2)],
                ["inc-a", "inc-b"],
            )
            self.assertEqual(
                [i.id for i in store.list_incidents(limit=None, offset=4)],
                ["inc-c", "inc-f"],
            )

            with self.assertRaises(ValueError):
                store.list_incidents(limit=-1)
            with self.assertRaises(ValueError):
                store.list_incidents(offset=-2)

    def test_resolve_incident_lifecycle_and_idempotency(self) -> None:
        with IncidentStore() as store:
            self.assertIsNone(store.resolve_incident("nonexistent"))

            inc1 = _make_incident("inc-r1", first_minute=0, last_minute=10)
            inc2 = _make_incident("inc-r2", first_minute=0, last_minute=10)
            store.upsert_incident(inc1)
            store.upsert_incident(inc2)

            # Resolve without resolved_at keeps existing last_seen.
            resolved1 = store.resolve_incident("inc-r1")
            self.assertIsNotNone(resolved1)
            assert resolved1 is not None
            self.assertEqual(resolved1.status, STATUS_RESOLVED)
            self.assertEqual(resolved1.last_seen, inc1.last_seen)

            # Re-resolving is idempotent.
            resolved1_again = store.resolve_incident("inc-r1")
            self.assertEqual(resolved1_again, resolved1)

            # Resolve with earlier resolved_at preserves max(existing.last_seen, resolved_at).
            earlier = datetime(2026, 11, 20, 12, 5, 0, tzinfo=timezone.utc)
            resolved2_early = store.resolve_incident("inc-r2", resolved_at=earlier)
            assert resolved2_early is not None
            self.assertEqual(resolved2_early.status, STATUS_RESOLVED)
            self.assertEqual(resolved2_early.last_seen, inc2.last_seen)

            # Resolve with later resolved_at (ISO string) advances last_seen.
            later_str = "2026-11-20T04:45:00-08:00"  # 12:45:00Z
            resolved2_late = store.resolve_incident("inc-r2", resolved_at=later_str)
            assert resolved2_late is not None
            self.assertEqual(resolved2_late.status, STATUS_RESOLVED)
            self.assertEqual(
                resolved2_late.last_seen,
                datetime(2026, 11, 20, 12, 45, 0, tzinfo=timezone.utc),
            )
            self.assertEqual(store.count_incidents(status=STATUS_OPEN), 0)
            self.assertEqual(store.count_incidents(status=STATUS_RESOLVED), 2)


class TestIncidentStoreSecurityAndConcurrency(unittest.TestCase):
    def test_parameterized_queries_resist_sql_injection(self) -> None:
        payload = "lab-core-r1'; DROP TABLE events; DROP TABLE incidents; --"
        or_probe = "' OR '1'='1"

        with IncidentStore() as store:
            ev = _make_event(host=payload, kind=EVENT_INTERFACE_UP, raw=payload)
            ev_id = store.add_event(ev)
            inc = _make_incident(
                "inc-sqli",
                host=payload,
                key=payload,
                summary=payload,
            )
            store.upsert_incident(inc)

            self.assertEqual(store.count_events(), 1)
            self.assertEqual(store.count_incidents(), 1)
            self.assertEqual(store.get_event(ev_id), ev)
            self.assertEqual(store.list_events(host=or_probe), [])
            self.assertEqual(store.list_events(host=payload), [ev])
            self.assertEqual(store.list_incidents(host=or_probe), [])
            self.assertEqual(store.list_incidents(host=payload), [inc])
            self.assertIsNone(store.get_incident(or_probe))

    def test_concurrent_reads_and_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "concurrent.db"
            with IncidentStore(db_path) as store:
                errors: list[BaseException] = []

                def worker(worker_idx: int) -> None:
                    try:
                        for step in range(10):
                            store.add_event(
                                _make_event(
                                    minute=step,
                                    microsecond=worker_idx * 100 + step,
                                    host=f"lab-fw-0{worker_idx + 1}",
                                    src_ip=f"192.0.2.{worker_idx * 10 + step + 1}",
                                    raw=f"worker={worker_idx} step={step}",
                                )
                            )
                            store.upsert_incident(
                                _make_incident(
                                    f"inc-w{worker_idx}-{step}",
                                    host=f"lab-fw-0{worker_idx + 1}",
                                    last_minute=step,
                                )
                            )
                            store.list_events(limit=5)
                            store.list_incidents(limit=5)
                    except BaseException as exc:  # pragma: no cover - test failure path
                        errors.append(exc)

                threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join()

                self.assertEqual(errors, [])
                self.assertEqual(store.count_events(), 40)
                self.assertEqual(store.count_incidents(), 40)


if __name__ == "__main__":
    unittest.main()
