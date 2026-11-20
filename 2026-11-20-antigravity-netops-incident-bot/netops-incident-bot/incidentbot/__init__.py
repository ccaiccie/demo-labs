"""Core engine for the NetOps incident bot."""

from __future__ import annotations

from incidentbot.correlator import Correlator
from incidentbot.models import (
    INCIDENT_AUTH_BRUTE_FORCE,
    INCIDENT_BGP_NEIGHBOR_DOWN,
    INCIDENT_CONFIG_CHANGE,
    INCIDENT_INTERFACE_FLAP,
    STATUS_OPEN,
    STATUS_RESOLVED,
    VENDOR_CISCO,
    VENDOR_FORTIGATE,
    Event,
    Incident,
)
from incidentbot.parser import parse_line, parse_lines
from incidentbot.store import IncidentStore

__all__ = [
    "Correlator",
    "Event",
    "INCIDENT_AUTH_BRUTE_FORCE",
    "INCIDENT_BGP_NEIGHBOR_DOWN",
    "INCIDENT_CONFIG_CHANGE",
    "INCIDENT_INTERFACE_FLAP",
    "Incident",
    "IncidentStore",
    "STATUS_OPEN",
    "STATUS_RESOLVED",
    "VENDOR_CISCO",
    "VENDOR_FORTIGATE",
    "parse_line",
    "parse_lines",
]
