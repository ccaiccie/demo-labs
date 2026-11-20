"""SQLite persistence layer for NetOps events and correlated incidents."""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterable
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any

from incidentbot.models import (
    STATUS_RESOLVED,
    Event,
    Incident,
    format_timestamp,
    normalize_timestamp,
)

__all__ = ["IncidentStore"]

_SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        host TEXT NOT NULL,
        vendor TEXT NOT NULL,
        kind TEXT NOT NULL,
        severity TEXT NOT NULL,
        interface TEXT,
        peer TEXT,
        user TEXT,
        src_ip TEXT,
        raw TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_events_timestamp_id ON events (timestamp DESC, id DESC)",
    "CREATE INDEX IF NOT EXISTS idx_events_host ON events (host)",
    "CREATE INDEX IF NOT EXISTS idx_events_vendor ON events (vendor)",
    "CREATE INDEX IF NOT EXISTS idx_events_kind ON events (kind)",
    "CREATE INDEX IF NOT EXISTS idx_events_severity ON events (severity)",
    "CREATE INDEX IF NOT EXISTS idx_events_src_ip ON events (src_ip)",
    """
    CREATE TABLE IF NOT EXISTS incidents (
        id TEXT PRIMARY KEY,
        type TEXT NOT NULL,
        severity TEXT NOT NULL,
        host TEXT NOT NULL,
        key TEXT NOT NULL,
        first_seen TEXT NOT NULL,
        last_seen TEXT NOT NULL,
        count INTEGER NOT NULL,
        status TEXT NOT NULL,
        summary TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_incidents_last_seen_id ON incidents (last_seen DESC, id ASC)",
    "CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents (status)",
    "CREATE INDEX IF NOT EXISTS idx_incidents_type ON incidents (type)",
    "CREATE INDEX IF NOT EXISTS idx_incidents_severity ON incidents (severity)",
    "CREATE INDEX IF NOT EXISTS idx_incidents_host ON incidents (host)",
    "CREATE INDEX IF NOT EXISTS idx_incidents_key ON incidents (key)",
)

_EVENT_COLUMNS = (
    "timestamp, host, vendor, kind, severity, interface, peer, user, src_ip, raw"
)
_EVENT_INSERT_SQL = (
    f"INSERT INTO events ({_EVENT_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)

_INCIDENT_COLUMNS = (
    "id, type, severity, host, key, first_seen, last_seen, count, status, summary"
)
_INCIDENT_UPSERT_SQL = f"""
INSERT INTO incidents ({_INCIDENT_COLUMNS})
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(id) DO UPDATE SET
    type = excluded.type,
    severity = excluded.severity,
    host = excluded.host,
    key = excluded.key,
    first_seen = excluded.first_seen,
    last_seen = excluded.last_seen,
    count = excluded.count,
    status = excluded.status,
    summary = excluded.summary
"""


def _event_params(event: Event) -> tuple[Any, ...]:
    return (
        format_timestamp(event.timestamp),
        event.host,
        event.vendor,
        event.kind,
        event.severity,
        event.interface,
        event.peer,
        event.user,
        event.src_ip,
        event.raw,
    )


def _row_to_event(row: sqlite3.Row) -> Event:
    return Event(
        timestamp=row["timestamp"],
        host=row["host"],
        vendor=row["vendor"],
        kind=row["kind"],
        severity=row["severity"],
        interface=row["interface"],
        peer=row["peer"],
        user=row["user"],
        src_ip=row["src_ip"],
        raw=row["raw"],
    )


def _incident_params(incident: Incident) -> tuple[Any, ...]:
    return (
        incident.id,
        incident.type,
        incident.severity,
        incident.host,
        incident.key,
        format_timestamp(incident.first_seen),
        format_timestamp(incident.last_seen),
        incident.count,
        incident.status,
        incident.summary,
    )


def _row_to_incident(row: sqlite3.Row) -> Incident:
    return Incident(
        id=row["id"],
        type=row["type"],
        severity=row["severity"],
        host=row["host"],
        key=row["key"],
        first_seen=row["first_seen"],
        last_seen=row["last_seen"],
        count=row["count"],
        status=row["status"],
        summary=row["summary"],
    )


def _insert_event(cursor: sqlite3.Cursor, event: Event) -> int:
    cursor.execute(_EVENT_INSERT_SQL, _event_params(event))
    if cursor.lastrowid is None:
        raise RuntimeError("SQLite did not return a row id for inserted event")
    return int(cursor.lastrowid)


def _append_eq_filters(
    clauses: list[str],
    params: list[Any],
    filters: Iterable[tuple[str, Any]],
) -> None:
    for column, value in filters:
        if value is not None:
            clauses.append(f"{column} = ?")
            params.append(value)


def _append_time_bounds(
    clauses: list[str],
    params: list[Any],
    column: str,
    since: datetime | str | None,
    until: datetime | str | None,
) -> None:
    if since is not None:
        clauses.append(f"{column} >= ?")
        params.append(format_timestamp(normalize_timestamp(since)))
    if until is not None:
        clauses.append(f"{column} <= ?")
        params.append(format_timestamp(normalize_timestamp(until)))


def _build_pagination_clause(limit: int | None, offset: int) -> tuple[str, list[Any]]:
    if limit is not None and limit < 0:
        raise ValueError(f"limit must be non-negative, got {limit}")
    if offset < 0:
        raise ValueError(f"offset must be non-negative, got {offset}")

    if limit is not None:
        return " LIMIT ? OFFSET ?", [limit, offset]
    if offset > 0:
        # SQLite syntax requires an explicit LIMIT before OFFSET.
        return " LIMIT -1 OFFSET ?", [offset]
    return "", []


class IncidentStore:
    """Thread-safe SQLite store for normalized events and correlated incidents."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        """Open (or create) the SQLite store and ensure schema/indexes exist."""
        db_target = str(db_path)
        if db_target != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self._db_path = db_target
        self._lock = threading.RLock()
        self._closed = False
        self._conn = sqlite3.connect(db_target, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        try:
            with self._lock:
                if db_target != ":memory:":
                    self._conn.execute("PRAGMA journal_mode=WAL")
                with self._conn:
                    for statement in _SCHEMA_STATEMENTS:
                        self._conn.execute(statement)
        except Exception:
            self.close()
            raise

    def __enter__(self) -> IncidentStore:
        with self._lock:
            self._ensure_open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Close the SQLite connection safely and idempotently."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._conn.close()

    def _ensure_open(self) -> None:
        if self._closed:
            raise sqlite3.ProgrammingError("Cannot operate on a closed IncidentStore")

    def add_event(self, event: Event) -> int:
        """Persist a single event and return its assigned database row id."""
        with self._lock:
            self._ensure_open()
            with self._conn, closing(self._conn.cursor()) as cursor:
                return _insert_event(cursor, event)

    def add_events(self, events: Iterable[Event]) -> list[int]:
        """Persist an iterable of events in a single transaction and return row ids."""
        with self._lock:
            self._ensure_open()
            row_ids: list[int] = []
            with self._conn, closing(self._conn.cursor()) as cursor:
                for event in events:
                    row_ids.append(_insert_event(cursor, event))
            return row_ids

    def get_event(self, event_id: int) -> Event | None:
        """Return the event with ``event_id``, or None if it does not exist."""
        with self._lock:
            self._ensure_open()
            row = self._conn.execute(
                f"SELECT {_EVENT_COLUMNS} FROM events WHERE id = ?",
                (event_id,),
            ).fetchone()
        return _row_to_event(row) if row is not None else None

    def list_events(
        self,
        *,
        host: str | None = None,
        vendor: str | None = None,
        kind: str | None = None,
        severity: str | None = None,
        src_ip: str | None = None,
        since: datetime | str | None = None,
        until: datetime | str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Event]:
        """List stored events matching optional filters, newest first."""
        pagination_sql, pagination_params = _build_pagination_clause(limit, offset)
        clauses: list[str] = []
        params: list[Any] = []
        _append_eq_filters(
            clauses,
            params,
            (
                ("host", host),
                ("vendor", vendor),
                ("kind", kind),
                ("severity", severity),
                ("src_ip", src_ip),
            ),
        )
        _append_time_bounds(clauses, params, "timestamp", since, until)

        where_sql = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = (
            f"SELECT {_EVENT_COLUMNS} FROM events"
            f"{where_sql} ORDER BY timestamp DESC, id DESC{pagination_sql}"
        )
        params.extend(pagination_params)

        with self._lock:
            self._ensure_open()
            rows = self._conn.execute(sql, params).fetchall()
        return [_row_to_event(row) for row in rows]

    def count_events(self) -> int:
        """Return total count of persisted events."""
        with self._lock:
            self._ensure_open()
            row = self._conn.execute("SELECT COUNT(*) FROM events").fetchone()
        return int(row[0]) if row is not None else 0

    def upsert_incident(self, incident: Incident) -> Incident:
        """Insert or update an incident by id and return the stored record."""
        with self._lock:
            self._ensure_open()
            with self._conn:
                self._conn.execute(_INCIDENT_UPSERT_SQL, _incident_params(incident))
            stored = self.get_incident(incident.id)
        if stored is None:  # pragma: no cover - defensive guard
            raise RuntimeError(f"Failed to retrieve upserted incident {incident.id!r}")
        return stored

    def get_incident(self, incident_id: str) -> Incident | None:
        """Return the incident with ``incident_id``, or None if not found."""
        with self._lock:
            self._ensure_open()
            row = self._conn.execute(
                f"SELECT {_INCIDENT_COLUMNS} FROM incidents WHERE id = ?",
                (incident_id,),
            ).fetchone()
        return _row_to_incident(row) if row is not None else None

    def list_incidents(
        self,
        *,
        status: str | None = None,
        incident_type: str | None = None,
        severity: str | None = None,
        host: str | None = None,
        key: str | None = None,
        since: datetime | str | None = None,
        until: datetime | str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Incident]:
        """List stored incidents matching optional filters, ordered by last_seen DESC."""
        pagination_sql, pagination_params = _build_pagination_clause(limit, offset)
        clauses: list[str] = []
        params: list[Any] = []
        _append_eq_filters(
            clauses,
            params,
            (
                ("status", status),
                ("type", incident_type),
                ("severity", severity),
                ("key", key),
            ),
        )
        if host is not None:
            clauses.append(
                "(host = ? OR instr(',' || host || ',', ',' || ? || ',') > 0)"
            )
            params.extend((host, host))
        _append_time_bounds(clauses, params, "last_seen", since, until)

        where_sql = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = (
            f"SELECT {_INCIDENT_COLUMNS} FROM incidents"
            f"{where_sql} ORDER BY last_seen DESC, id ASC{pagination_sql}"
        )
        params.extend(pagination_params)

        with self._lock:
            self._ensure_open()
            rows = self._conn.execute(sql, params).fetchall()
        return [_row_to_incident(row) for row in rows]

    def resolve_incident(
        self,
        incident_id: str,
        *,
        resolved_at: datetime | str | None = None,
    ) -> Incident | None:
        """Resolve an incident, optionally advancing last_seen to resolved_at."""
        resolved_dt = (
            normalize_timestamp(resolved_at) if resolved_at is not None else None
        )
        with self._lock:
            self._ensure_open()
            existing = self.get_incident(incident_id)
            if existing is None:
                return None

            new_last_seen = (
                max(existing.last_seen, resolved_dt)
                if resolved_dt is not None
                else existing.last_seen
            )
            if existing.status != STATUS_RESOLVED or new_last_seen != existing.last_seen:
                with self._conn:
                    self._conn.execute(
                        "UPDATE incidents SET status = ?, last_seen = ? WHERE id = ?",
                        (STATUS_RESOLVED, format_timestamp(new_last_seen), incident_id),
                    )
            return self.get_incident(incident_id)

    def count_incidents(self, *, status: str | None = None) -> int:
        """Return count of stored incidents, optionally filtered by status."""
        sql = "SELECT COUNT(*) FROM incidents"
        params: tuple[Any, ...] = ()
        if status is not None:
            sql += " WHERE status = ?"
            params = (status,)
        with self._lock:
            self._ensure_open()
            row = self._conn.execute(sql, params).fetchone()
        return int(row[0]) if row is not None else 0
