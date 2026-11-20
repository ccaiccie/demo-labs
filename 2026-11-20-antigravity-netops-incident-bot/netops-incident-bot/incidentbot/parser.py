"""Syslog parser for Cisco IOS and FortiGate network events."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
import re

from incidentbot.models import (
    EVENT_AUTH_FAILED,
    EVENT_AUTH_SUCCESS,
    EVENT_BGP_DOWN,
    EVENT_BGP_UP,
    EVENT_CONFIG_CHANGE,
    EVENT_INTERFACE_DOWN,
    EVENT_INTERFACE_UP,
    SYSLOG_SEVERITIES,
    VENDOR_CISCO,
    VENDOR_FORTIGATE,
    Event,
    normalize_timestamp,
)

__all__ = ["Event", "parse_line", "parse_lines"]

_MONTHS: dict[str, int] = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

_FORTIGATE_SEVERITY_MAP: dict[str, str] = {
    "emerg": "emergency",
    "emergency": "emergency",
    "alert": "alert",
    "crit": "critical",
    "critical": "critical",
    "err": "error",
    "error": "error",
    "warn": "warning",
    "warning": "warning",
    "notice": "notice",
    "info": "info",
    "information": "info",
    "informational": "info",
    "debug": "debug",
    "dbg": "debug",
}

_FORTIGATE_MARKER_KEYS = frozenset({"logdesc", "devname", "devid", "logid"})

_PRI_RE = re.compile(r"^<(\d+)>")
_RFC3164_TS_RE = re.compile(
    r"^(?P<month>[A-Za-z]{3}) +(?P<day>\d{1,2}) +(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})(?=\s|$)"
)
_FIRST_TOKEN_RE = re.compile(r"^(\S+)(?:\s+(.*))?$")
_IOS_SEQ_RE = re.compile(r"^\d+:?$")
_IOS_PREFIX_TS_START_RE = re.compile(
    r"^[*.:]?(?P<month>[A-Za-z]{3}) +\d{1,2}(?: +\d{4})? +\d{2}:\d{2}:\d{2}"
    r"(?:[.:]|\s+(?:[A-Za-z]{2,5}|[+-]\d{2}:?\d{2}):?)"
)

_CISCO_MSG_RE = re.compile(r"%([A-Z0-9_]+)-([0-7])-([A-Z0-9_]+):\s*(.*)")
_IOS_TS_RE = re.compile(
    r"[*.:]?(?P<month>[A-Za-z]{3}) +(?P<day>\d{1,2})"
    r"(?: +(?P<year>\d{4}))?"
    r" +(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})"
    r"(?:\.(?P<frac>\d+))?"
    r"(?: +(?P<tz>[A-Za-z]{2,5}|[+-]\d{2}:?\d{2}))?"
    r":?"
)
_CISCO_LINK_RE = re.compile(
    r"Interface\s+(?P<iface>[^,]+?),\s*changed state to\s+(?:administratively\s+)?(?P<state>up|down)\b",
    re.IGNORECASE,
)
_CISCO_LINEPROTO_RE = re.compile(
    r"Line protocol on Interface\s+(?P<iface>[^,]+?),\s*changed state to\s+(?P<state>up|down)\b",
    re.IGNORECASE,
)
_CISCO_INTERFACE_RE_BY_FACILITY: dict[str, re.Pattern[str]] = {
    "LINK": _CISCO_LINK_RE,
    "LINEPROTO": _CISCO_LINEPROTO_RE,
}
_CISCO_BGP_RE = re.compile(
    r"(?:(?:vpn\s+)?vrf\s+\S+\s+)?neighbor\s+(?P<peer>\S+)\s+(?:(?:vpn\s+)?vrf\s+\S+\s+)?(?P<state>Up|Down)\b",
    re.IGNORECASE,
)
_CISCO_USER_RE = re.compile(r"\[\s*user\s*:\s*(?P<user>[^\]]*)\]", re.IGNORECASE)
_CISCO_SOURCE_RE = re.compile(r"\[\s*source\s*:\s*(?P<src_ip>[^\]]*)\]", re.IGNORECASE)
_CISCO_CONFIG_BY_ON_RE = re.compile(
    r"\bby\s+(?P<user>\S+)\s+on\s+(?P<line>\S+)(?:\s*\((?P<src_ip>[^)]+)\))?",
    re.IGNORECASE,
)
_CISCO_CONFIG_BY_LINE_RE = re.compile(
    r"\bby\s+(?P<line>(?:console|vty\d+|tty\d+|aux\d+))(?:\s*\((?P<src_ip>[^)]+)\))?",
    re.IGNORECASE,
)
_CISCO_CONFIG_BY_USER_RE = re.compile(
    r"\bby\s+(?P<user>\S+)(?:\s*\((?P<src_ip>[^)]+)\))?",
    re.IGNORECASE,
)

_KV_KEY_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?$")
_TZ_OFFSET_RE = re.compile(r"^([+-])(\d{2}):?(\d{2})$")
_TZ_SHORT_OFFSET_RE = re.compile(r"^([+-])(\d{1,2})$")
_SLUG_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


@dataclass(slots=True)
class _ParsedPrefix:
    pri_severity: str | None
    header_ts: datetime | None
    header_host: str | None
    payload: str


def _parse_tz(tz_str: str) -> timezone | None:
    """Parse a timezone offset or UTC/GMT designator into a timezone object."""
    normalized = tz_str.strip().upper()
    if not normalized or normalized in {"UTC", "GMT", "Z"}:
        return timezone.utc

    if normalized.startswith(("UTC", "GMT")):
        normalized = normalized[3:].strip()
        if not normalized:
            return timezone.utc

    match = _TZ_OFFSET_RE.fullmatch(normalized)
    if match:
        sign = 1 if match.group(1) == "+" else -1
        hours = int(match.group(2))
        minutes = int(match.group(3))
        if hours > 23 or minutes > 59:
            return None
        return timezone(sign * timedelta(hours=hours, minutes=minutes))

    short_match = _TZ_SHORT_OFFSET_RE.fullmatch(normalized)
    if short_match:
        sign = 1 if short_match.group(1) == "+" else -1
        hours = int(short_match.group(2))
        if hours > 23:
            return None
        return timezone(sign * timedelta(hours=hours))

    return None


def _starts_with_ios_internal_ts(text: str) -> bool:
    """Return True if text begins with a Cisco IOS internal timestamp."""
    match = _IOS_PREFIX_TS_START_RE.match(text)
    if match is None:
        return False
    return match.group("month").lower() in _MONTHS


def _is_payload_start_token(token: str, full_rest: str) -> bool:
    """Return True if the leading token begins the message payload rather than a hostname."""
    if token.startswith(("%", "*", ".", ":")):
        return True
    if "=" in token:
        return True
    if _IOS_SEQ_RE.fullmatch(token):
        return True
    if _starts_with_ios_internal_ts(full_rest):
        return True
    return False


def _parse_prefix(text: str, *, year: int) -> _ParsedPrefix | None:
    """Extract optional <PRI>, RFC 3164 timestamp, and host prefix from a syslog line."""
    pri_severity: str | None = None
    rest = text

    pri_match = _PRI_RE.match(rest)
    if pri_match is not None:
        pri = int(pri_match.group(1))
        pri_severity = SYSLOG_SEVERITIES[pri % 8]
        rest = rest[pri_match.end() :].lstrip()

    if not rest:
        return None

    header_ts: datetime | None = None
    ts_match = _RFC3164_TS_RE.match(rest)
    if ts_match is not None:
        month = _MONTHS.get(ts_match.group("month").lower())
        if month is not None:
            try:
                header_ts = datetime(
                    year,
                    month,
                    int(ts_match.group("day")),
                    int(ts_match.group("hour")),
                    int(ts_match.group("minute")),
                    int(ts_match.group("second")),
                    tzinfo=timezone.utc,
                )
            except ValueError:
                return None
            rest = rest[ts_match.end() :].lstrip()

    if not rest:
        return None

    header_host: str | None = None
    tok_match = _FIRST_TOKEN_RE.match(rest)
    if tok_match is not None:
        first_token = tok_match.group(1)
        remainder = (tok_match.group(2) or "").lstrip()
        if remainder and not _is_payload_start_token(first_token, rest):
            candidate_host = first_token.rstrip(":")
            if candidate_host.upper() in {"UTC", "GMT"} and remainder.startswith("%"):
                rest = remainder
            elif candidate_host:
                header_host = candidate_host
                rest = remainder

    return _ParsedPrefix(
        pri_severity=pri_severity,
        header_ts=header_ts,
        header_host=header_host,
        payload=rest,
    )


def _parse_ios_internal_timestamp(
    prefix_text: str, *, fallback_year: int
) -> datetime | None:
    """Attempt to parse a Cisco IOS internal timestamp preceding %FACILITY-SEV-MNEM."""
    match = _IOS_TS_RE.search(prefix_text)
    if match is None:
        return None

    month = _MONTHS.get(match.group("month").lower())
    if month is None:
        return None

    year = int(match.group("year")) if match.group("year") else fallback_year
    frac = match.group("frac")
    microsecond = int(frac[:6].ljust(6, "0")) if frac else 0

    tz_raw = match.group("tz")
    tz_info = _parse_tz(tz_raw) if tz_raw else timezone.utc
    if tz_info is None:
        tz_info = timezone.utc

    try:
        dt = datetime(
            year,
            month,
            int(match.group("day")),
            int(match.group("hour")),
            int(match.group("minute")),
            int(match.group("second")),
            microsecond,
            tzinfo=tz_info,
        )
    except ValueError:
        return None

    return normalize_timestamp(dt)


def _parse_cisco(
    prefix: _ParsedPrefix,
    *,
    raw: str,
    ref_time: datetime,
    fallback_year: int,
) -> Event | None:
    """Parse a Cisco IOS syslog payload into a normalized Event."""
    msg_match = _CISCO_MSG_RE.search(prefix.payload)
    if msg_match is None:
        return None

    facility, sev_digit, mnemonic, body = msg_match.groups()
    severity = SYSLOG_SEVERITIES.get(int(sev_digit), prefix.pri_severity or "notice")

    timestamp = prefix.header_ts
    if timestamp is None:
        ios_ts = _parse_ios_internal_timestamp(
            prefix.payload[: msg_match.start()],
            fallback_year=fallback_year,
        )
        timestamp = ios_ts if ios_ts is not None else ref_time

    host = prefix.header_host or "unknown"

    if mnemonic == "UPDOWN" and facility in _CISCO_INTERFACE_RE_BY_FACILITY:
        match = _CISCO_INTERFACE_RE_BY_FACILITY[facility].search(body)
        if match is None:
            return None
        state = match.group("state").lower()
        kind = EVENT_INTERFACE_DOWN if state == "down" else EVENT_INTERFACE_UP
        return Event(
            timestamp=timestamp,
            host=host,
            vendor=VENDOR_CISCO,
            kind=kind,
            severity=severity,
            interface=match.group("iface").strip(),
            raw=raw,
        )

    if facility == "BGP" and mnemonic == "ADJCHANGE":
        match = _CISCO_BGP_RE.search(body)
        if match is None:
            return None
        state = match.group("state").lower()
        kind = EVENT_BGP_DOWN if state == "down" else EVENT_BGP_UP
        return Event(
            timestamp=timestamp,
            host=host,
            vendor=VENDOR_CISCO,
            kind=kind,
            severity=severity,
            peer=match.group("peer"),
            raw=raw,
        )

    if facility == "SEC_LOGIN" and mnemonic == "LOGIN_FAILED":
        user_match = _CISCO_USER_RE.search(body)
        src_match = _CISCO_SOURCE_RE.search(body)
        user = user_match.group("user").strip() or None if user_match else None
        src_ip = src_match.group("src_ip").strip() or None if src_match else None
        return Event(
            timestamp=timestamp,
            host=host,
            vendor=VENDOR_CISCO,
            kind=EVENT_AUTH_FAILED,
            severity=severity,
            user=user,
            src_ip=src_ip,
            raw=raw,
        )

    if facility == "SYS" and mnemonic == "CONFIG_I":
        user = None
        line_name: str | None = None
        src_ip = None

        by_on_match = _CISCO_CONFIG_BY_ON_RE.search(body)
        if by_on_match is not None:
            user = by_on_match.group("user").strip() or None
            line_name = by_on_match.group("line").strip() or None
            raw_ip = by_on_match.group("src_ip")
            src_ip = raw_ip.strip() or None if raw_ip else None
        else:
            by_line_match = _CISCO_CONFIG_BY_LINE_RE.search(body)
            if by_line_match is not None:
                line_name = by_line_match.group("line").strip() or None
                raw_ip = by_line_match.group("src_ip")
                src_ip = raw_ip.strip() or None if raw_ip else None
            else:
                by_user_match = _CISCO_CONFIG_BY_USER_RE.search(body)
                if by_user_match is not None:
                    user = by_user_match.group("user").strip() or None
                    raw_ip = by_user_match.group("src_ip")
                    src_ip = raw_ip.strip() or None if raw_ip else None

        return Event(
            timestamp=timestamp,
            host=host,
            vendor=VENDOR_CISCO,
            kind=EVENT_CONFIG_CHANGE,
            severity=severity,
            interface=line_name,
            user=user,
            src_ip=src_ip,
            raw=raw,
        )

    return None


def _tokenize_fortigate_kv(text: str) -> dict[str, str] | None:
    """Parse strict whitespace-delimited FortiGate key=value pairs."""
    pairs: dict[str, str] = {}
    idx = 0
    length = len(text)

    while idx < length:
        while idx < length and text[idx].isspace():
            idx += 1
        if idx >= length:
            break

        eq_idx = text.find("=", idx)
        if eq_idx == -1:
            return None

        key = text[idx:eq_idx]
        if not _KV_KEY_RE.fullmatch(key):
            return None

        idx = eq_idx + 1
        if idx < length and text[idx] == '"':
            idx += 1
            chars: list[str] = []
            closed = False
            while idx < length:
                ch = text[idx]
                if ch == "\\":
                    if idx + 1 >= length:
                        return None
                    nxt = text[idx + 1]
                    if nxt in ('"', "\\"):
                        chars.append(nxt)
                    else:
                        chars.append("\\")
                        chars.append(nxt)
                    idx += 2
                elif ch == '"':
                    closed = True
                    idx += 1
                    break
                else:
                    chars.append(ch)
                    idx += 1

            if not closed:
                return None
            if idx < length and not text[idx].isspace():
                return None
            value = "".join(chars)
        else:
            start = idx
            while idx < length and not text[idx].isspace():
                idx += 1
            value = text[start:idx]

        pairs[key.lower()] = value

    return pairs


def _is_fortigate_kv(pairs: dict[str, str]) -> bool:
    """Return True if parsed key=value pairs satisfy FortiGate log criteria."""
    if len(pairs) < 2:
        return False
    if any(marker in pairs for marker in _FORTIGATE_MARKER_KEYS):
        return True
    return "action" in pairs and "status" in pairs


def _parse_fortigate_date_time(
    date_str: str, time_str: str, tz_str: str
) -> datetime | None:
    """Parse FortiGate date, time, and optional tz fields into a UTC datetime."""
    if not _DATE_RE.fullmatch(date_str) or not _TIME_RE.fullmatch(time_str):
        return None
    tz_info = _parse_tz(tz_str) if tz_str else timezone.utc
    if tz_info is None:
        tz_info = timezone.utc
    try:
        dt = datetime.combine(
            date.fromisoformat(date_str),
            time.fromisoformat(time_str),
            tzinfo=tz_info,
        )
    except ValueError:
        return None
    return normalize_timestamp(dt)


def _parse_epoch_timestamp(raw_epoch: str) -> datetime | None:
    """Parse a Unix epoch timestamp in seconds, ms, us, or ns into UTC datetime."""
    value = raw_epoch.strip()
    if not value:
        return None

    try:
        if value.isdigit() or (value[0] in "+-" and value[1:].isdigit()):
            epoch_int = int(value)
            if epoch_int < 0:
                return None
            if epoch_int >= 10**17:
                sec, rem = divmod(epoch_int, 1_000_000_000)
                microsecond = rem // 1_000
            elif epoch_int >= 10**14:
                sec, microsecond = divmod(epoch_int, 1_000_000)
            elif epoch_int >= 10**11:
                sec, rem = divmod(epoch_int, 1_000)
                microsecond = rem * 1_000
            else:
                sec = epoch_int
                microsecond = 0
            return datetime.fromtimestamp(sec, tz=timezone.utc) + timedelta(
                microseconds=microsecond
            )

        epoch_float = float(value)
        if epoch_float < 0:
            return None
        return datetime.fromtimestamp(epoch_float, tz=timezone.utc)
    except (ValueError, OverflowError, OSError):
        return None


def _normalize_fortigate_severity(
    level_raw: str, pri_severity: str | None
) -> str:
    """Normalize FortiGate log level with PRI and default fallbacks."""
    level = level_raw.strip().lower()
    if level in _FORTIGATE_SEVERITY_MAP:
        return _FORTIGATE_SEVERITY_MAP[level]
    if level.isdigit() and int(level) in SYSLOG_SEVERITIES:
        return SYSLOG_SEVERITIES[int(level)]
    return pri_severity or "notice"


def _slugify(text: str) -> str:
    """Convert a descriptive phrase into a lowercase snake_case identifier."""
    slug = _SLUG_NON_ALNUM_RE.sub("_", text.lower()).strip("_")
    return slug or "event"


def _classify_fortigate_kind(
    action: str, status: str, logdesc: str
) -> str:
    """Determine normalized Event kind from FortiGate action, status, and logdesc."""
    logdesc_lower = logdesc.lower()
    if (action == "login" and status == "failed") or (
        "login failed" in logdesc_lower and status != "success"
    ):
        return EVENT_AUTH_FAILED
    if action == "login" and status == "success":
        return EVENT_AUTH_SUCCESS
    if ("link" in logdesc_lower or "interface" in logdesc_lower) and status in (
        "down",
        "up",
    ):
        return EVENT_INTERFACE_DOWN if status == "down" else EVENT_INTERFACE_UP
    if logdesc:
        return _slugify(logdesc)
    return "event"


def _parse_fortigate(
    pairs: dict[str, str], prefix: _ParsedPrefix, *, raw: str, ref_time: datetime
) -> Event | None:
    """Convert validated FortiGate key=value pairs into a normalized Event."""
    action = pairs.get("action", "").strip().lower()
    status = pairs.get("status", "").strip().lower()

    if "type" in pairs and pairs["type"].strip().lower() != "event":
        if not (action == "login" and status == "failed"):
            return None

    date_str = pairs.get("date", "").strip()
    time_str = pairs.get("time", "").strip()
    tz_str = pairs.get("tz", "").strip()

    timestamp: datetime | None = None
    if date_str and time_str:
        timestamp = _parse_fortigate_date_time(date_str, time_str, tz_str)
    if timestamp is None:
        timestamp = prefix.header_ts
    if timestamp is None and "eventtime" in pairs:
        timestamp = _parse_epoch_timestamp(pairs["eventtime"])
    if timestamp is None:
        timestamp = ref_time

    host = (
        pairs.get("devname", "").strip()
        or prefix.header_host
        or pairs.get("devid", "").strip()
        or "unknown"
    )
    severity = _normalize_fortigate_severity(
        pairs.get("level", ""), prefix.pri_severity
    )

    user = pairs.get("user", "").strip() or None
    src_ip = (
        pairs.get("srcip", "").strip()
        or pairs.get("remip", "").strip()
        or None
    )
    interface = (
        pairs.get("interface", "").strip()
        or pairs.get("intf", "").strip()
        or None
    )
    peer = pairs.get("peer", "").strip() or None

    logdesc = pairs.get("logdesc", "").strip()
    kind = _classify_fortigate_kind(action, status, logdesc)

    return Event(
        timestamp=timestamp,
        host=host,
        vendor=VENDOR_FORTIGATE,
        kind=kind,
        severity=severity,
        interface=interface,
        peer=peer,
        user=user,
        src_ip=src_ip,
        raw=raw,
    )


def parse_line(
    line: str,
    *,
    reference_time: datetime | None = None,
    default_year: int | None = None,
) -> Event | None:
    """Parse a single Cisco IOS or FortiGate syslog line into an Event, or None."""
    raw = line.rstrip("\r\n")
    text = raw.strip()
    if not text:
        return None

    ref_time = (
        normalize_timestamp(reference_time)
        if reference_time is not None
        else datetime.now(timezone.utc)
    )
    year = default_year if default_year is not None else ref_time.year

    prefix = _parse_prefix(text, year=year)
    if prefix is None:
        return None

    pairs = _tokenize_fortigate_kv(prefix.payload)
    if pairs is not None and _is_fortigate_kv(pairs):
        return _parse_fortigate(pairs, prefix, raw=raw, ref_time=ref_time)

    return _parse_cisco(
        prefix,
        raw=raw,
        ref_time=ref_time,
        fallback_year=year,
    )


def parse_lines(
    lines: Iterable[str],
    *,
    reference_time: datetime | None = None,
    default_year: int | None = None,
) -> list[Event]:
    """Parse an iterable of syslog lines, omitting unrecognized or blank entries."""
    events: list[Event] = []
    for line in lines:
        event = parse_line(
            line, reference_time=reference_time, default_year=default_year
        )
        if event is not None:
            events.append(event)
    return events
