"""Event-to-incident correlator for the NetOps incident bot."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from datetime import datetime, timedelta
import hashlib
import threading

from incidentbot.models import (
    EVENT_AUTH_FAILED,
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
    Event,
    Incident,
    format_human_timestamp,
)

__all__ = ["Correlator", "Incident"]


def _append_sorted_event(events: list[Event], event: Event) -> None:
    """Append an event while preserving ascending timestamp order."""
    events.append(event)
    events.sort(key=lambda item: item.timestamp)


def _join_hosts(events: Iterable[Event]) -> str:
    """Return a comma-separated sorted list of unique non-empty hostnames."""
    return ",".join(sorted({ev.host for ev in events if ev.host}))


def _build_interface_flap_summary(events: list[Event]) -> str:
    """Build a deterministic plain-text summary for an interface flap incident."""
    host = events[0].host
    interface = events[0].interface or ""
    down_count = sum(1 for ev in events if ev.kind == EVENT_INTERFACE_DOWN)
    up_count = sum(1 for ev in events if ev.kind == EVENT_INTERFACE_UP)
    total = len(events)
    unit = "time" if total == 1 else "times"
    start_str = format_human_timestamp(events[0].timestamp)
    end_str = format_human_timestamp(events[-1].timestamp)
    return (
        f"Interface {interface} on {host} flapped {total} {unit} "
        f"({down_count} down, {up_count} up) between {start_str} and {end_str}."
    )


def _build_bgp_neighbor_down_summary(events: list[Event]) -> str:
    """Build a deterministic plain-text summary for a BGP neighbor incident."""
    host = events[0].host
    peer = events[0].peer or ""
    down_count = sum(1 for ev in events if ev.kind == EVENT_BGP_DOWN)
    up_count = sum(1 for ev in events if ev.kind == EVENT_BGP_UP)
    start_str = format_human_timestamp(events[0].timestamp)
    end_str = format_human_timestamp(events[-1].timestamp)

    if up_count > 0:
        recovery_ts = max(ev.timestamp for ev in events if ev.kind == EVENT_BGP_UP)
        recovery_str = format_human_timestamp(recovery_ts)
        return (
            f"BGP neighbor {peer} on {host} went down ({down_count} down, {up_count} up, "
            f"{len(events)} total events) and recovered at {recovery_str} "
            f"(span {start_str} to {end_str})."
        )

    if len(events) == 1:
        return (
            f"BGP neighbor {peer} on {host} went down at {start_str} "
            f"(1 down event)."
        )

    return (
        f"BGP neighbor {peer} on {host} went down ({down_count} down events "
        f"between {start_str} and {end_str})."
    )


def _build_auth_brute_force_summary(events: list[Event]) -> str:
    """Build a deterministic plain-text summary for an auth brute-force incident."""
    src_ip = events[0].src_ip or ""
    hosts = sorted({ev.host for ev in events if ev.host})
    vendors = sorted({ev.vendor for ev in events if ev.vendor})
    users = sorted({ev.user for ev in events if ev.user})

    hosts_str = ", ".join(hosts) if hosts else "unknown"
    vendors_str = ", ".join(vendors) if vendors else "unknown"
    users_part = f"; targeted users: {', '.join(users)}" if users else ""
    start_str = format_human_timestamp(events[0].timestamp)
    end_str = format_human_timestamp(events[-1].timestamp)
    total = len(events)
    unit = "attempt" if total == 1 else "attempts"

    return (
        f"Brute-force auth failures from {src_ip}: {total} failed {unit} "
        f"on hosts [{hosts_str}] via vendors [{vendors_str}]{users_part} "
        f"between {start_str} and {end_str}."
    )


def _build_config_change_summary(events: list[Event]) -> str:
    """Build a deterministic plain-text summary for a config change incident."""
    host = events[0].host
    users = sorted({ev.user for ev in events if ev.user})
    lines = sorted({ev.interface for ev in events if ev.interface})
    src_ips = sorted({ev.src_ip for ev in events if ev.src_ip})
    start_str = format_human_timestamp(events[0].timestamp)
    end_str = format_human_timestamp(events[-1].timestamp)
    total = len(events)

    details: list[str] = []
    if users:
        details.append(f"by {', '.join(users)}")
    if lines:
        details.append(f"on {', '.join(lines)}")
    if src_ips:
        details.append(f"({', '.join(src_ips)})")
    detail_str = f" {' '.join(details)}" if details else ""

    if total == 1:
        return f"Configuration changed on {host}{detail_str} at {start_str}."
    return (
        f"Configuration changed on {host} ({total} events){detail_str} "
        f"between {start_str} and {end_str}."
    )


def _build_summary(inc_type: str, events: list[Event]) -> str:
    """Dispatch summary construction strictly from an incident's events."""
    if inc_type == INCIDENT_INTERFACE_FLAP:
        return _build_interface_flap_summary(events)
    if inc_type == INCIDENT_BGP_NEIGHBOR_DOWN:
        return _build_bgp_neighbor_down_summary(events)
    if inc_type == INCIDENT_AUTH_BRUTE_FORCE:
        return _build_auth_brute_force_summary(events)
    if inc_type == INCIDENT_CONFIG_CHANGE:
        return _build_config_change_summary(events)
    raise ValueError(f"Unsupported incident type: {inc_type!r}")


class Correlator:
    """Correlates normalized syslog events into actionable NetOps incidents."""

    def __init__(
        self,
        *,
        flap_threshold: int = 3,
        flap_window_seconds: int = 120,
        brute_force_threshold: int = 5,
        brute_force_window_seconds: int = 60,
    ) -> None:
        if flap_threshold < 1:
            raise ValueError(f"flap_threshold must be >= 1, got {flap_threshold}")
        if flap_window_seconds < 0:
            raise ValueError(
                f"flap_window_seconds must be >= 0, got {flap_window_seconds}"
            )
        if brute_force_threshold < 1:
            raise ValueError(
                f"brute_force_threshold must be >= 1, got {brute_force_threshold}"
            )
        if brute_force_window_seconds < 0:
            raise ValueError(
                f"brute_force_window_seconds must be >= 0, got {brute_force_window_seconds}"
            )

        self._flap_threshold = flap_threshold
        self._flap_window_seconds = flap_window_seconds
        self._brute_force_threshold = brute_force_threshold
        self._brute_force_window_seconds = brute_force_window_seconds

        self._lock = threading.RLock()
        self._incidents: dict[str, Incident] = {}
        self._open_by_key: dict[str, Incident] = {}
        self._windows: dict[str, list[Event]] = {}
        self._incident_events: dict[str, list[Event]] = {}

    def process_event(self, event: Event) -> list[Incident]:
        """Process a single event and return copies of affected incidents."""
        with self._lock:
            return self._process_event_locked(event)

    def process_events(self, events: Iterable[Event]) -> list[Incident]:
        """Process events in order and return the latest snapshot per affected incident."""
        with self._lock:
            affected: dict[str, Incident] = {}
            for event in events:
                for inc in self._process_event_locked(event):
                    affected[inc.id] = inc
            return list(affected.values())

    def get_open_incidents(self) -> list[Incident]:
        """Return shallow copies of all currently open incidents."""
        with self._lock:
            return [replace(inc) for inc in self._open_by_key.values()]

    def get_incidents(self) -> list[Incident]:
        """Return shallow copies of all incidents (open and resolved)."""
        with self._lock:
            return [replace(inc) for inc in self._incidents.values()]

    def get_incident(self, incident_id: str) -> Incident | None:
        """Return a shallow copy of an incident by ID, or None if not found."""
        with self._lock:
            inc = self._incidents.get(incident_id)
            return replace(inc) if inc is not None else None

    def mark_resolved(self, incident_id: str) -> Incident | None:
        """Resolve an open incident and clear its sliding window."""
        with self._lock:
            inc = self._incidents.get(incident_id)
            if inc is None:
                return None
            if inc.status == STATUS_RESOLVED:
                return replace(inc)

            inc.status = STATUS_RESOLVED
            self._open_by_key.pop(inc.key, None)
            self._windows.pop(inc.key, None)
            return replace(inc)

    def _process_event_locked(self, event: Event) -> list[Incident]:
        if event.kind in (EVENT_INTERFACE_DOWN, EVENT_INTERFACE_UP):
            if not event.host or not event.interface:
                return []
            key = f"interface_flap:{event.host}:{event.interface}"
            return self._process_window_rule(
                event,
                inc_type=INCIDENT_INTERFACE_FLAP,
                severity=SEVERITY_MEDIUM,
                key=key,
                threshold=self._flap_threshold,
                window_seconds=self._flap_window_seconds,
            )

        if event.kind in (EVENT_BGP_DOWN, EVENT_BGP_UP):
            return self._process_bgp_event(event)

        if event.kind == EVENT_AUTH_FAILED:
            if not event.src_ip:
                return []
            key = f"auth_brute_force:{event.src_ip}"
            return self._process_window_rule(
                event,
                inc_type=INCIDENT_AUTH_BRUTE_FORCE,
                severity=SEVERITY_HIGH,
                key=key,
                threshold=self._brute_force_threshold,
                window_seconds=self._brute_force_window_seconds,
            )

        if event.kind == EVENT_CONFIG_CHANGE:
            return self._process_config_change_event(event)

        return []

    def _process_window_rule(
        self,
        event: Event,
        *,
        inc_type: str,
        severity: str,
        key: str,
        threshold: int,
        window_seconds: int,
    ) -> list[Incident]:
        existing = self._open_by_key.get(key)
        if existing is not None:
            self._update_open_incident(existing, event)
            return [replace(existing)]

        window = self._windows.setdefault(key, [])
        _append_sorted_event(window, event)
        latest = window[-1].timestamp
        max_age = timedelta(seconds=window_seconds)
        window[:] = [ev for ev in window if (latest - ev.timestamp) <= max_age]

        if len(window) < threshold:
            return []

        inc_events = list(window)
        self._windows.pop(key, None)
        host = (
            _join_hosts(inc_events)
            if inc_type == INCIDENT_AUTH_BRUTE_FORCE
            else event.host
        )
        inc = self._open_incident(
            inc_type=inc_type,
            severity=severity,
            host=host,
            key=key,
            inc_events=inc_events,
        )
        return [replace(inc)]

    def _process_bgp_event(self, event: Event) -> list[Incident]:
        if not event.host or not event.peer:
            return []

        key = f"bgp_neighbor_down:{event.host}:{event.peer}"
        existing = self._open_by_key.get(key)

        if event.kind == EVENT_BGP_DOWN:
            if existing is None:
                inc = self._open_incident(
                    inc_type=INCIDENT_BGP_NEIGHBOR_DOWN,
                    severity=SEVERITY_CRITICAL,
                    host=event.host,
                    key=key,
                    inc_events=[event],
                )
                return [replace(inc)]

            self._update_open_incident(existing, event)
            return [replace(existing)]

        if event.kind == EVENT_BGP_UP:
            if existing is None:
                return []
            self._update_open_incident(existing, event, status=STATUS_RESOLVED)
            self._open_by_key.pop(key, None)
            return [replace(existing)]

        return []

    def _process_config_change_event(self, event: Event) -> list[Incident]:
        if not event.host:
            return []

        key = f"config_change:{event.host}"
        existing = self._open_by_key.get(key)
        if existing is None:
            inc = self._open_incident(
                inc_type=INCIDENT_CONFIG_CHANGE,
                severity=SEVERITY_LOW,
                host=event.host,
                key=key,
                inc_events=[event],
            )
            return [replace(inc)]

        self._update_open_incident(existing, event)
        return [replace(existing)]

    def _open_incident(
        self,
        *,
        inc_type: str,
        severity: str,
        host: str,
        key: str,
        inc_events: list[Event],
    ) -> Incident:
        first_seen = inc_events[0].timestamp
        last_seen = inc_events[-1].timestamp
        inc_id = self._generate_incident_id(inc_type, key, first_seen)
        inc = Incident(
            id=inc_id,
            type=inc_type,
            severity=severity,
            host=host,
            key=key,
            first_seen=first_seen,
            last_seen=last_seen,
            count=len(inc_events),
            status=STATUS_OPEN,
            summary=_build_summary(inc_type, inc_events),
        )
        self._incidents[inc_id] = inc
        self._open_by_key[key] = inc
        self._incident_events[inc_id] = inc_events
        return inc

    def _update_open_incident(
        self,
        inc: Incident,
        event: Event,
        *,
        status: str | None = None,
    ) -> Incident:
        inc_events = self._incident_events[inc.id]
        _append_sorted_event(inc_events, event)
        inc.first_seen = min(inc.first_seen, event.timestamp)
        inc.last_seen = max(inc.last_seen, event.timestamp)
        inc.count += 1
        if inc.type == INCIDENT_AUTH_BRUTE_FORCE:
            inc.host = _join_hosts(inc_events)
        if status is not None:
            inc.status = status
        inc.summary = _build_summary(inc.type, inc_events)
        return inc

    def _generate_incident_id(
        self, inc_type: str, key: str, first_seen: datetime
    ) -> str:
        base = f"{inc_type}|{key}|{first_seen.isoformat()}"
        candidate = f"inc-{hashlib.sha256(base.encode('utf-8')).hexdigest()[:12]}"
        if candidate not in self._incidents:
            return candidate

        counter = 1
        while True:
            salted = f"{base}|{counter}"
            candidate = (
                f"inc-{hashlib.sha256(salted.encode('utf-8')).hexdigest()[:12]}"
            )
            if candidate not in self._incidents:
                return candidate
            counter += 1
