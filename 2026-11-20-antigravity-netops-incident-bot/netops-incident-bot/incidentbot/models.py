"""Shared data models, constants, and timestamp helpers for the NetOps incident bot."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

VENDOR_CISCO = "cisco"
VENDOR_FORTIGATE = "fortigate"

EVENT_INTERFACE_DOWN = "interface_down"
EVENT_INTERFACE_UP = "interface_up"
EVENT_BGP_DOWN = "bgp_down"
EVENT_BGP_UP = "bgp_up"
EVENT_AUTH_FAILED = "auth_failed"
EVENT_AUTH_SUCCESS = "auth_success"
EVENT_CONFIG_CHANGE = "config_change"

INCIDENT_INTERFACE_FLAP = "INTERFACE_FLAP"
INCIDENT_BGP_NEIGHBOR_DOWN = "BGP_NEIGHBOR_DOWN"
INCIDENT_AUTH_BRUTE_FORCE = "AUTH_BRUTE_FORCE"
INCIDENT_CONFIG_CHANGE = "CONFIG_CHANGE"

STATUS_OPEN = "open"
STATUS_RESOLVED = "resolved"
VALID_STATUSES = frozenset({STATUS_OPEN, STATUS_RESOLVED})

SEVERITY_CRITICAL = "critical"
SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"
SEVERITY_LOW = "low"

SYSLOG_SEVERITIES: dict[int, str] = {
    0: "emergency",
    1: "alert",
    2: "critical",
    3: "error",
    4: "warning",
    5: "notice",
    6: "info",
    7: "debug",
}


def normalize_timestamp(value: datetime | str) -> datetime:
    """Normalize a datetime or ISO-8601 string into an aware UTC datetime."""
    if isinstance(value, str):
        dt = datetime.fromisoformat(value)
    elif isinstance(value, datetime):
        dt = value
    else:
        raise TypeError(f"Expected datetime or str, got {type(value).__name__}")

    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def format_timestamp(dt: datetime) -> str:
    """Format a datetime as a fixed-width UTC ISO-8601 string with microseconds."""
    return normalize_timestamp(dt).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def format_human_timestamp(dt: datetime) -> str:
    """Format a datetime as a human-readable UTC ISO-8601 string without microseconds."""
    return normalize_timestamp(dt).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(slots=True)
class Event:
    """Normalized network event parsed from vendor syslog lines."""

    timestamp: datetime
    host: str
    vendor: str
    kind: str
    severity: str
    interface: str | None = None
    peer: str | None = None
    user: str | None = None
    src_ip: str | None = None
    raw: str = ""

    def __post_init__(self) -> None:
        self.timestamp = normalize_timestamp(self.timestamp)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the event to a JSON-compatible dictionary."""
        return {
            "timestamp": format_timestamp(self.timestamp),
            "host": self.host,
            "vendor": self.vendor,
            "kind": self.kind,
            "severity": self.severity,
            "interface": self.interface,
            "peer": self.peer,
            "user": self.user,
            "src_ip": self.src_ip,
            "raw": self.raw,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Event:
        """Deserialize an Event from a dictionary."""
        return cls(
            timestamp=data["timestamp"],
            host=str(data["host"]),
            vendor=str(data["vendor"]),
            kind=str(data["kind"]),
            severity=str(data["severity"]),
            interface=data.get("interface"),
            peer=data.get("peer"),
            user=data.get("user"),
            src_ip=data.get("src_ip"),
            raw=str(data.get("raw", "")),
        )


@dataclass(slots=True)
class Incident:
    """Correlated NetOps incident derived from one or more events."""

    id: str
    type: str
    severity: str
    host: str
    key: str
    first_seen: datetime
    last_seen: datetime
    count: int
    status: str
    summary: str

    def __post_init__(self) -> None:
        self.first_seen = normalize_timestamp(self.first_seen)
        self.last_seen = normalize_timestamp(self.last_seen)
        if self.status not in VALID_STATUSES:
            raise ValueError(
                f"Invalid incident status {self.status!r}; expected one of {sorted(VALID_STATUSES)}"
            )
        if self.count < 0:
            raise ValueError(f"Incident count must be non-negative, got {self.count}")

    def to_dict(self) -> dict[str, Any]:
        """Serialize the incident to a JSON-compatible dictionary."""
        return {
            "id": self.id,
            "type": self.type,
            "severity": self.severity,
            "host": self.host,
            "key": self.key,
            "first_seen": format_timestamp(self.first_seen),
            "last_seen": format_timestamp(self.last_seen),
            "count": self.count,
            "status": self.status,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Incident:
        """Deserialize an Incident from a dictionary."""
        return cls(
            id=str(data["id"]),
            type=str(data["type"]),
            severity=str(data["severity"]),
            host=str(data["host"]),
            key=str(data["key"]),
            first_seen=data["first_seen"],
            last_seen=data["last_seen"],
            count=int(data["count"]),
            status=str(data["status"]),
            summary=str(data["summary"]),
        )
