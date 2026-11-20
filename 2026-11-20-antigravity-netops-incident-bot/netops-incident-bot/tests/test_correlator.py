"""Unit tests for incidentbot.correlator."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import unittest

from incidentbot.correlator import Correlator, Incident as CorrelatorIncident
from incidentbot.models import (
    EVENT_AUTH_FAILED,
    EVENT_AUTH_SUCCESS,
    EVENT_BGP_DOWN,
    EVENT_BGP_UP,
    EVENT_CONFIG_CHANGE,
    EVENT_INTERFACE_DOWN,
    EVENT_INTERFACE_UP,
    INCIDENT_AUTH_BRUTE_FORCE,
    INCIDENT_BGP_NEIGHBOR_DOWN,
    INCIDENT_CONFIG_CHANGE,
    INCIDENT_INTERFACE_FLAP,
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    STATUS_OPEN,
    STATUS_RESOLVED,
    VENDOR_CISCO,
    VENDOR_FORTIGATE,
    Event,
    Incident,
    format_human_timestamp,
)

BASE_TIME = datetime(2026, 11, 20, 12, 0, 0, tzinfo=timezone.utc)


def _ts(offset_seconds: int) -> datetime:
    return BASE_TIME + timedelta(seconds=offset_seconds)


def _make_iface_event(
    offset_seconds: int,
    *,
    kind: str = EVENT_INTERFACE_DOWN,
    host: str = "lab-core-r1",
    interface: str | None = "GigabitEthernet0/1",
    vendor: str = VENDOR_CISCO,
) -> Event:
    return Event(
        timestamp=_ts(offset_seconds),
        host=host,
        vendor=vendor,
        kind=kind,
        severity="error" if kind == EVENT_INTERFACE_DOWN else "notice",
        interface=interface,
    )


def _make_bgp_event(
    offset_seconds: int,
    *,
    kind: str = EVENT_BGP_DOWN,
    host: str = "lab-edge-r2",
    peer: str | None = "203.0.113.10",
    vendor: str = VENDOR_CISCO,
) -> Event:
    return Event(
        timestamp=_ts(offset_seconds),
        host=host,
        vendor=vendor,
        kind=kind,
        severity="warning" if kind == EVENT_BGP_DOWN else "notice",
        peer=peer,
    )


def _make_auth_event(
    offset_seconds: int,
    *,
    kind: str = EVENT_AUTH_FAILED,
    host: str = "lab-core-r1",
    vendor: str = VENDOR_CISCO,
    src_ip: str | None = "198.51.100.42",
    user: str | None = "netadmin",
) -> Event:
    return Event(
        timestamp=_ts(offset_seconds),
        host=host,
        vendor=vendor,
        kind=kind,
        severity="warning",
        src_ip=src_ip,
        user=user,
    )


def _make_config_change_event(
    offset_seconds: int,
    *,
    host: str = "lab-edge-rtr-01",
    vendor: str = VENDOR_CISCO,
    user: str | None = "labops",
    interface: str | None = "vty0",
    src_ip: str | None = "192.0.2.10",
) -> Event:
    return Event(
        timestamp=_ts(offset_seconds),
        host=host,
        vendor=vendor,
        kind=EVENT_CONFIG_CHANGE,
        severity="notice",
        interface=interface,
        user=user,
        src_ip=src_ip,
    )


class TestCorrelatorInterfaceFlap(unittest.TestCase):
    def test_two_events_do_not_open_incident(self) -> None:
        corr = Correlator()
        self.assertEqual(
            corr.process_event(_make_iface_event(0, kind=EVENT_INTERFACE_DOWN)), []
        )
        self.assertEqual(
            corr.process_event(_make_iface_event(30, kind=EVENT_INTERFACE_UP)), []
        )
        self.assertEqual(corr.get_open_incidents(), [])
        self.assertEqual(corr.get_incidents(), [])

    def test_third_event_at_exactly_120s_opens_incident(self) -> None:
        corr = Correlator()
        corr.process_event(_make_iface_event(0, kind=EVENT_INTERFACE_DOWN))
        corr.process_event(_make_iface_event(60, kind=EVENT_INTERFACE_UP))
        opened = corr.process_event(_make_iface_event(120, kind=EVENT_INTERFACE_DOWN))

        self.assertEqual(len(opened), 1)
        inc = opened[0]
        self.assertEqual(inc.type, INCIDENT_INTERFACE_FLAP)
        self.assertEqual(inc.severity, SEVERITY_MEDIUM)
        self.assertEqual(inc.host, "lab-core-r1")
        self.assertEqual(inc.key, "interface_flap:lab-core-r1:GigabitEthernet0/1")
        self.assertEqual(inc.first_seen, _ts(0))
        self.assertEqual(inc.last_seen, _ts(120))
        self.assertEqual(inc.count, 3)
        self.assertEqual(inc.status, STATUS_OPEN)

        expected_hash = hashlib.sha256(
            f"{INCIDENT_INTERFACE_FLAP}|{inc.key}|{_ts(0).isoformat()}".encode("utf-8")
        ).hexdigest()[:12]
        self.assertEqual(inc.id, f"inc-{expected_hash}")

        self.assertIn("GigabitEthernet0/1", inc.summary)
        self.assertIn("lab-core-r1", inc.summary)
        self.assertIn("3", inc.summary)
        self.assertIn("2 down", inc.summary)
        self.assertIn("1 up", inc.summary)
        self.assertIn(format_human_timestamp(_ts(0)), inc.summary)
        self.assertIn(format_human_timestamp(_ts(120)), inc.summary)

    def test_third_event_at_121s_expires_first_event_and_does_not_open(self) -> None:
        corr = Correlator()
        self.assertEqual(corr.process_event(_make_iface_event(0)), [])
        self.assertEqual(corr.process_event(_make_iface_event(60, kind=EVENT_INTERFACE_UP)), [])
        self.assertEqual(corr.process_event(_make_iface_event(121)), [])
        self.assertEqual(corr.get_open_incidents(), [])

    def test_fourth_event_updates_existing_without_duplicating(self) -> None:
        corr = Correlator()
        corr.process_event(_make_iface_event(0, kind=EVENT_INTERFACE_DOWN))
        corr.process_event(_make_iface_event(20, kind=EVENT_INTERFACE_UP))
        first_snap = corr.process_event(_make_iface_event(40, kind=EVENT_INTERFACE_DOWN))[0]

        updated = corr.process_event(_make_iface_event(55, kind=EVENT_INTERFACE_UP))
        self.assertEqual(len(updated), 1)
        inc = updated[0]
        self.assertEqual(inc.id, first_snap.id)
        self.assertEqual(inc.count, 4)
        self.assertEqual(inc.first_seen, _ts(0))
        self.assertEqual(inc.last_seen, _ts(55))
        self.assertIn("4", inc.summary)
        self.assertIn("2 down", inc.summary)
        self.assertIn("2 up", inc.summary)
        self.assertIn(format_human_timestamp(_ts(55)), inc.summary)
        self.assertEqual(len(corr.get_incidents()), 1)
        self.assertEqual(len(corr.get_open_incidents()), 1)

    def test_separate_interfaces_and_hosts_do_not_mix(self) -> None:
        corr = Correlator()
        corr.process_event(_make_iface_event(0, host="lab-core-r1", interface="GigabitEthernet0/1"))
        corr.process_event(_make_iface_event(5, host="lab-core-r1", interface="GigabitEthernet0/2"))
        corr.process_event(_make_iface_event(10, host="lab-dist-sw1", interface="GigabitEthernet0/1"))
        corr.process_event(_make_iface_event(15, host="lab-core-r1", interface="GigabitEthernet0/1"))
        corr.process_event(_make_iface_event(20, host="lab-core-r1", interface="GigabitEthernet0/2"))
        corr.process_event(_make_iface_event(25, host="lab-dist-sw1", interface="GigabitEthernet0/1"))
        self.assertEqual(corr.get_incidents(), [])

        # Missing host or interface should also be ignored
        self.assertEqual(corr.process_event(_make_iface_event(30, host="", interface="Gi0/1")), [])
        self.assertEqual(corr.process_event(_make_iface_event(30, interface=None)), [])

    def test_mark_resolved_resets_window_and_allows_new_incident(self) -> None:
        corr = Correlator()
        corr.process_event(_make_iface_event(0, kind=EVENT_INTERFACE_DOWN))
        corr.process_event(_make_iface_event(10, kind=EVENT_INTERFACE_UP))
        inc1 = corr.process_event(_make_iface_event(20, kind=EVENT_INTERFACE_DOWN))[0]

        resolved = corr.mark_resolved(inc1.id)
        self.assertIsNotNone(resolved)
        assert resolved is not None
        self.assertEqual(resolved.status, STATUS_RESOLVED)
        self.assertEqual(corr.get_open_incidents(), [])

        # Calling mark_resolved again on already-resolved returns existing snapshot
        again = corr.mark_resolved(inc1.id)
        self.assertEqual(again, resolved)
        self.assertIsNone(corr.mark_resolved("inc-unknown"))

        # Pre-resolution events were cleared; 2 new events must NOT re-trigger
        self.assertEqual(corr.process_event(_make_iface_event(25, kind=EVENT_INTERFACE_UP)), [])
        self.assertEqual(corr.process_event(_make_iface_event(30, kind=EVENT_INTERFACE_DOWN)), [])
        self.assertEqual(corr.get_open_incidents(), [])

        # 3rd new event opens a distinct new incident
        opened = corr.process_event(_make_iface_event(35, kind=EVENT_INTERFACE_UP))
        self.assertEqual(len(opened), 1)
        inc2 = opened[0]
        self.assertNotEqual(inc2.id, inc1.id)
        self.assertEqual(inc2.status, STATUS_OPEN)
        self.assertEqual(inc2.count, 3)
        self.assertEqual(inc2.first_seen, _ts(25))
        self.assertEqual(inc2.last_seen, _ts(35))
        self.assertEqual(len(corr.get_incidents()), 2)
        self.assertEqual(len(corr.get_open_incidents()), 1)


class TestCorrelatorBgpNeighborDown(unittest.TestCase):
    def test_bgp_up_without_open_incident_does_nothing(self) -> None:
        corr = Correlator()
        self.assertEqual(corr.process_event(_make_bgp_event(0, kind=EVENT_BGP_UP)), [])
        self.assertEqual(corr.get_incidents(), [])

    def test_bgp_down_duplicate_up_and_reopen(self) -> None:
        corr = Correlator()
        opened = corr.process_event(_make_bgp_event(0, kind=EVENT_BGP_DOWN))
        self.assertEqual(len(opened), 1)
        inc1 = opened[0]
        self.assertEqual(inc1.type, INCIDENT_BGP_NEIGHBOR_DOWN)
        self.assertEqual(inc1.severity, SEVERITY_CRITICAL)
        self.assertEqual(inc1.host, "lab-edge-r2")
        self.assertEqual(inc1.key, "bgp_neighbor_down:lab-edge-r2:203.0.113.10")
        self.assertEqual(inc1.count, 1)
        self.assertEqual(inc1.status, STATUS_OPEN)
        self.assertIn("203.0.113.10", inc1.summary)
        self.assertIn("lab-edge-r2", inc1.summary)

        # Duplicate bgp_down increments count and updates last_seen/summary
        dup = corr.process_event(_make_bgp_event(30, kind=EVENT_BGP_DOWN))
        self.assertEqual(len(dup), 1)
        self.assertEqual(dup[0].id, inc1.id)
        self.assertEqual(dup[0].count, 2)
        self.assertEqual(dup[0].last_seen, _ts(30))
        self.assertEqual(dup[0].status, STATUS_OPEN)
        self.assertIn("2 down", dup[0].summary)

        # bgp_up resolves incident and updates summary noting recovery
        resolved_list = corr.process_event(_make_bgp_event(90, kind=EVENT_BGP_UP))
        self.assertEqual(len(resolved_list), 1)
        resolved = resolved_list[0]
        self.assertEqual(resolved.id, inc1.id)
        self.assertEqual(resolved.status, STATUS_RESOLVED)
        self.assertEqual(resolved.count, 3)
        self.assertEqual(resolved.first_seen, _ts(0))
        self.assertEqual(resolved.last_seen, _ts(90))
        self.assertIn("recovered", resolved.summary.lower())
        self.assertIn(format_human_timestamp(_ts(90)), resolved.summary)
        self.assertEqual(corr.get_open_incidents(), [])

        # Extra bgp_up does nothing
        self.assertEqual(corr.process_event(_make_bgp_event(95, kind=EVENT_BGP_UP)), [])

        # Subsequent bgp_down opens a NEW incident with distinct id
        reopened = corr.process_event(_make_bgp_event(120, kind=EVENT_BGP_DOWN))
        self.assertEqual(len(reopened), 1)
        inc2 = reopened[0]
        self.assertNotEqual(inc2.id, inc1.id)
        self.assertEqual(inc2.status, STATUS_OPEN)
        self.assertEqual(inc2.count, 1)
        self.assertEqual(len(corr.get_incidents()), 2)

    def test_bgp_same_first_seen_after_resolution_avoids_id_collision(self) -> None:
        corr = Correlator()
        inc1 = corr.process_event(_make_bgp_event(0, kind=EVENT_BGP_DOWN))[0]
        corr.process_event(_make_bgp_event(0, kind=EVENT_BGP_UP))
        inc2 = corr.process_event(_make_bgp_event(0, kind=EVENT_BGP_DOWN))[0]

        self.assertNotEqual(inc1.id, inc2.id)
        self.assertEqual(len(corr.get_incidents()), 2)
        expected_salted = hashlib.sha256(
            f"{INCIDENT_BGP_NEIGHBOR_DOWN}|{inc1.key}|{_ts(0).isoformat()}|1".encode(
                "utf-8"
            )
        ).hexdigest()[:12]
        self.assertEqual(inc2.id, f"inc-{expected_salted}")

    def test_bgp_missing_fields_and_peer_isolation(self) -> None:
        corr = Correlator()
        self.assertEqual(corr.process_event(_make_bgp_event(0, peer=None)), [])
        self.assertEqual(corr.process_event(_make_bgp_event(0, host="")), [])

        inc_a = corr.process_event(_make_bgp_event(0, peer="203.0.113.10"))[0]
        inc_b = corr.process_event(_make_bgp_event(5, peer="203.0.113.11"))[0]
        self.assertNotEqual(inc_a.id, inc_b.id)
        self.assertEqual(len(corr.get_open_incidents()), 2)


class TestCorrelatorAuthBruteForce(unittest.TestCase):
    def test_four_failures_do_not_open_incident(self) -> None:
        corr = Correlator()
        for offset in (0, 10, 20, 30):
            self.assertEqual(corr.process_event(_make_auth_event(offset)), [])
        self.assertEqual(corr.get_open_incidents(), [])

    def test_five_failures_spanning_61s_do_not_open_incident(self) -> None:
        corr = Correlator()
        for offset in (0, 15, 30, 45, 61):
            self.assertEqual(corr.process_event(_make_auth_event(offset)), [])
        self.assertEqual(corr.get_open_incidents(), [])

    def test_cross_vendor_five_failures_within_60s_and_sixth_update(self) -> None:
        corr = Correlator()
        events = [
            _make_auth_event(0, host="lab-fw-01", vendor=VENDOR_FORTIGATE, user="admin"),
            _make_auth_event(15, host="lab-core-r1", vendor=VENDOR_CISCO, user="netadmin"),
            _make_auth_event(30, host="lab-fw-01", vendor=VENDOR_FORTIGATE, user="root"),
            _make_auth_event(45, host="lab-core-r1", vendor=VENDOR_CISCO, user="admin"),
            _make_auth_event(60, host="lab-fw-01", vendor=VENDOR_FORTIGATE, user="operator"),
        ]
        for ev in events[:-1]:
            self.assertEqual(corr.process_event(ev), [])

        opened = corr.process_event(events[-1])
        self.assertEqual(len(opened), 1)
        inc = opened[0]
        self.assertEqual(inc.type, INCIDENT_AUTH_BRUTE_FORCE)
        self.assertEqual(inc.severity, SEVERITY_HIGH)
        self.assertEqual(inc.host, "lab-core-r1,lab-fw-01")
        self.assertEqual(inc.key, "auth_brute_force:198.51.100.42")
        self.assertEqual(inc.first_seen, _ts(0))
        self.assertEqual(inc.last_seen, _ts(60))
        self.assertEqual(inc.count, 5)
        self.assertEqual(inc.status, STATUS_OPEN)

        self.assertIn("198.51.100.42", inc.summary)
        self.assertIn("5", inc.summary)
        self.assertIn("lab-core-r1", inc.summary)
        self.assertIn("lab-fw-01", inc.summary)
        self.assertIn("cisco", inc.summary)
        self.assertIn("fortigate", inc.summary)
        for user in ("admin", "netadmin", "operator", "root"):
            self.assertIn(user, inc.summary)
        self.assertIn(format_human_timestamp(_ts(0)), inc.summary)
        self.assertIn(format_human_timestamp(_ts(60)), inc.summary)

        # 6th event from another host updates open incident and host list
        sixth = _make_auth_event(
            75, host="lab-fw-02", vendor=VENDOR_FORTIGATE, user="secops"
        )
        updated = corr.process_event(sixth)
        self.assertEqual(len(updated), 1)
        inc_v2 = updated[0]
        self.assertEqual(inc_v2.id, inc.id)
        self.assertEqual(inc_v2.count, 6)
        self.assertEqual(inc_v2.host, "lab-core-r1,lab-fw-01,lab-fw-02")
        self.assertEqual(inc_v2.last_seen, _ts(75))
        self.assertIn("6", inc_v2.summary)
        self.assertIn("lab-fw-02", inc_v2.summary)
        self.assertIn("secops", inc_v2.summary)

    def test_different_src_ips_isolated_and_non_failed_ignored(self) -> None:
        corr = Correlator()
        # auth_success and missing src_ip are ignored
        self.assertEqual(
            corr.process_event(_make_auth_event(0, kind=EVENT_AUTH_SUCCESS)), []
        )
        self.assertEqual(corr.process_event(_make_auth_event(0, src_ip=None)), [])

        for i in range(4):
            corr.process_event(_make_auth_event(i * 5, src_ip="198.51.100.42", user=None))
            corr.process_event(_make_auth_event(i * 5, src_ip="192.0.2.99", user=None))
        self.assertEqual(corr.get_open_incidents(), [])

        inc_a = corr.process_event(
            _make_auth_event(25, src_ip="198.51.100.42", user=None)
        )[0]
        self.assertNotIn("targeted users", inc_a.summary)
        self.assertEqual(len(corr.get_open_incidents()), 1)

        corr.mark_resolved(inc_a.id)
        # Window reset after mark_resolved: 4 new failures do not immediately re-trigger
        for i in range(4):
            self.assertEqual(
                corr.process_event(_make_auth_event(30 + i, src_ip="198.51.100.42")), []
            )


class TestCorrelatorConfigChange(unittest.TestCase):
    def test_config_change_opens_low_severity_incident_per_host_and_aggregates(
        self,
    ) -> None:
        corr = Correlator()
        opened = corr.process_event(_make_config_change_event(0))
        self.assertEqual(len(opened), 1)
        inc1 = opened[0]
        self.assertEqual(inc1.type, INCIDENT_CONFIG_CHANGE)
        self.assertEqual(inc1.severity, SEVERITY_LOW)
        self.assertEqual(inc1.host, "lab-edge-rtr-01")
        self.assertEqual(inc1.key, "config_change:lab-edge-rtr-01")
        self.assertEqual(inc1.first_seen, _ts(0))
        self.assertEqual(inc1.last_seen, _ts(0))
        self.assertEqual(inc1.count, 1)
        self.assertEqual(inc1.status, STATUS_OPEN)
        self.assertIn("lab-edge-rtr-01", inc1.summary)
        self.assertIn("labops", inc1.summary)
        self.assertIn("vty0", inc1.summary)
        self.assertIn("192.0.2.10", inc1.summary)
        self.assertIn(format_human_timestamp(_ts(0)), inc1.summary)

        # Second config change on the same host updates the existing open incident
        updated = corr.process_event(
            _make_config_change_event(
                45,
                user="netadmin",
                interface="vty1",
                src_ip="192.0.2.11",
            )
        )
        self.assertEqual(len(updated), 1)
        inc_v2 = updated[0]
        self.assertEqual(inc_v2.id, inc1.id)
        self.assertEqual(inc_v2.count, 2)
        self.assertEqual(inc_v2.first_seen, _ts(0))
        self.assertEqual(inc_v2.last_seen, _ts(45))
        self.assertEqual(inc_v2.severity, SEVERITY_LOW)
        self.assertIn("2 events", inc_v2.summary)
        self.assertIn("labops", inc_v2.summary)
        self.assertIn("netadmin", inc_v2.summary)
        self.assertIn("vty0", inc_v2.summary)
        self.assertIn("vty1", inc_v2.summary)
        self.assertIn("192.0.2.10", inc_v2.summary)
        self.assertIn("192.0.2.11", inc_v2.summary)
        self.assertEqual(len(corr.get_open_incidents()), 1)

    def test_config_change_host_isolation_missing_host_and_reopen(self) -> None:
        corr = Correlator()
        self.assertEqual(corr.process_event(_make_config_change_event(0, host="")), [])
        self.assertEqual(corr.get_incidents(), [])

        inc_a = corr.process_event(
            _make_config_change_event(10, host="lab-edge-rtr-01")
        )[0]
        inc_b = corr.process_event(
            _make_config_change_event(
                20,
                host="lab-edge-rtr-02",
                user=None,
                interface=None,
                src_ip=None,
            )
        )[0]
        self.assertNotEqual(inc_a.id, inc_b.id)
        self.assertEqual(inc_b.key, "config_change:lab-edge-rtr-02")
        self.assertEqual(inc_b.severity, SEVERITY_LOW)
        self.assertIn("lab-edge-rtr-02", inc_b.summary)
        self.assertEqual(len(corr.get_open_incidents()), 2)

        resolved = corr.mark_resolved(inc_a.id)
        self.assertIsNotNone(resolved)
        assert resolved is not None
        self.assertEqual(resolved.status, STATUS_RESOLVED)
        self.assertEqual(len(corr.get_open_incidents()), 1)

        reopened = corr.process_event(
            _make_config_change_event(60, host="lab-edge-rtr-01")
        )[0]
        self.assertNotEqual(reopened.id, inc_a.id)
        self.assertEqual(reopened.status, STATUS_OPEN)
        self.assertEqual(reopened.count, 1)
        self.assertEqual(len(corr.get_incidents()), 3)


class TestCorrelatorCrossCutting(unittest.TestCase):
    def test_out_of_order_events_window_and_open_incident(self) -> None:
        corr = Correlator()
        # Out-of-order arrival before opening: 120s, 0s, 60s
        self.assertEqual(
            corr.process_event(_make_iface_event(120, kind=EVENT_INTERFACE_DOWN)), []
        )
        self.assertEqual(
            corr.process_event(_make_iface_event(0, kind=EVENT_INTERFACE_UP)), []
        )
        opened = corr.process_event(_make_iface_event(60, kind=EVENT_INTERFACE_DOWN))
        self.assertEqual(len(opened), 1)
        inc = opened[0]
        self.assertEqual(inc.first_seen, _ts(0))
        self.assertEqual(inc.last_seen, _ts(120))
        self.assertEqual(inc.count, 3)

        # Out-of-order arrival after opening with timestamp earlier than first_seen
        updated = corr.process_event(
            _make_iface_event(-15, kind=EVENT_INTERFACE_DOWN)
        )
        self.assertEqual(len(updated), 1)
        self.assertEqual(updated[0].id, inc.id)
        self.assertEqual(updated[0].first_seen, _ts(-15))
        self.assertEqual(updated[0].last_seen, _ts(120))
        self.assertEqual(updated[0].count, 4)
        self.assertIn(format_human_timestamp(_ts(-15)), updated[0].summary)

    def test_out_of_order_stale_event_pruned_relative_to_latest(self) -> None:
        corr = Correlator()
        corr.process_event(_make_iface_event(200, kind=EVENT_INTERFACE_DOWN))
        # Arrives late and is 150s older than latest (200s) -> pruned from 120s window
        corr.process_event(_make_iface_event(50, kind=EVENT_INTERFACE_UP))
        self.assertEqual(
            corr.process_event(_make_iface_event(190, kind=EVENT_INTERFACE_DOWN)), []
        )
        self.assertEqual(corr.get_incidents(), [])

    def test_out_of_order_bgp_down(self) -> None:
        corr = Correlator()
        inc1 = corr.process_event(_make_bgp_event(100, kind=EVENT_BGP_DOWN))[0]
        updated = corr.process_event(_make_bgp_event(80, kind=EVENT_BGP_DOWN))[0]
        self.assertEqual(updated.id, inc1.id)
        self.assertEqual(updated.first_seen, _ts(80))
        self.assertEqual(updated.last_seen, _ts(100))
        self.assertEqual(updated.count, 2)

    def test_snapshot_immutability_and_getters(self) -> None:
        corr = Correlator()
        corr.process_event(_make_iface_event(0))
        corr.process_event(_make_iface_event(10))
        snap1 = corr.process_event(_make_iface_event(20))[0]
        snap1_summary = snap1.summary

        # Later update must NOT mutate previously returned snapshot
        snap2 = corr.process_event(_make_iface_event(30))[0]
        self.assertEqual(snap1.count, 3)
        self.assertEqual(snap1.last_seen, _ts(20))
        self.assertEqual(snap1.summary, snap1_summary)
        self.assertEqual(snap2.count, 4)
        self.assertEqual(snap2.last_seen, _ts(30))

        # External mutation of returned snapshots must NOT affect Correlator state
        snap2.count = 999
        snap2.status = STATUS_RESOLVED
        fetched = corr.get_incident(snap2.id)
        self.assertIsNotNone(fetched)
        assert fetched is not None
        self.assertEqual(fetched.count, 4)
        self.assertEqual(fetched.status, STATUS_OPEN)
        fetched.count = 123

        open_list = corr.get_open_incidents()
        all_list = corr.get_incidents()
        self.assertEqual(len(open_list), 1)
        self.assertEqual(len(all_list), 1)
        self.assertEqual(open_list[0].count, 4)
        self.assertEqual(all_list[0].count, 4)
        self.assertIsNone(corr.get_incident("inc-missing"))

    def test_process_events_deduplication_and_first_seen_order(self) -> None:
        corr = Correlator()
        stream = (
            ev
            for ev in [
                _make_iface_event(0),
                _make_bgp_event(5, kind=EVENT_BGP_DOWN),  # inc_bgp_1 first seen
                _make_iface_event(10, kind=EVENT_INTERFACE_UP),
                _make_iface_event(20),  # inc_flap first seen
                _make_bgp_event(25, kind=EVENT_BGP_DOWN),  # updates inc_bgp_1
                _make_iface_event(30, kind=EVENT_INTERFACE_UP),  # updates inc_flap
                _make_bgp_event(40, kind=EVENT_BGP_UP),  # resolves inc_bgp_1
                _make_bgp_event(50, kind=EVENT_BGP_DOWN),  # inc_bgp_2 first seen
            ]
        )

        affected = corr.process_events(stream)
        self.assertEqual(len(affected), 3)
        self.assertEqual(affected[0].type, INCIDENT_BGP_NEIGHBOR_DOWN)
        self.assertEqual(affected[0].status, STATUS_RESOLVED)
        self.assertEqual(affected[0].count, 3)

        self.assertEqual(affected[1].type, INCIDENT_INTERFACE_FLAP)
        self.assertEqual(affected[1].status, STATUS_OPEN)
        self.assertEqual(affected[1].count, 4)

        self.assertEqual(affected[2].type, INCIDENT_BGP_NEIGHBOR_DOWN)
        self.assertEqual(affected[2].status, STATUS_OPEN)
        self.assertEqual(affected[2].count, 1)
        self.assertNotEqual(affected[0].id, affected[2].id)

    def test_deterministic_replay_and_reexport(self) -> None:
        self.assertIs(CorrelatorIncident, Incident)

        events = [
            _make_bgp_event(0, kind=EVENT_BGP_DOWN),
            _make_iface_event(10),
            _make_iface_event(20, kind=EVENT_INTERFACE_UP),
            _make_iface_event(30),
            _make_bgp_event(40, kind=EVENT_BGP_UP),
            _make_bgp_event(0, kind=EVENT_BGP_DOWN),
        ]
        corr_a = Correlator()
        corr_b = Correlator()

        res_a = corr_a.process_events(events)
        res_b = corr_b.process_events(events)
        self.assertEqual(res_a, res_b)
        self.assertEqual(corr_a.get_incidents(), corr_b.get_incidents())

    def test_invalid_constructor_args(self) -> None:
        with self.assertRaises(ValueError):
            Correlator(flap_threshold=0)
        with self.assertRaises(ValueError):
            Correlator(flap_window_seconds=-1)
        with self.assertRaises(ValueError):
            Correlator(brute_force_threshold=0)
        with self.assertRaises(ValueError):
            Correlator(brute_force_window_seconds=-1)


if __name__ == "__main__":
    unittest.main()
