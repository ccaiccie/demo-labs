"""UDP syslog listener, correlation pipeline, and HTTP REST/UI server."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import mimetypes
import os
from pathlib import Path
import signal
import socketserver
import threading
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from incidentbot.correlator import Correlator
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
    VALID_STATUSES,
    Event,
    Incident,
)
from incidentbot.parser import parse_line
from incidentbot.store import IncidentStore

__all__ = [
    "IncidentBotService",
    "ServerConfig",
    "main",
    "parse_args",
]

logger = logging.getLogger(__name__)

DEFAULT_SYSLOG_HOST = "0.0.0.0"
DEFAULT_SYSLOG_PORT = 5515
DEFAULT_HTTP_HOST = "0.0.0.0"
DEFAULT_HTTP_PORT = 8097
DEFAULT_DB_PATH = "incidentbot.db"
DEFAULT_STATIC_DIR = Path(__file__).resolve().parent / "web"

DEFAULT_EVENTS_LIMIT = 50
_ROOT_STATIC_EXTENSIONS = frozenset({".html", ".js", ".css"})
_CONTENT_TYPES: dict[str, str] = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".txt": "text/plain; charset=utf-8",
}


@dataclass(slots=True)
class ServerConfig:
    """Runtime configuration for the NetOps incident bot service."""

    syslog_host: str = DEFAULT_SYSLOG_HOST
    syslog_port: int = DEFAULT_SYSLOG_PORT
    http_host: str = DEFAULT_HTTP_HOST
    http_port: int = DEFAULT_HTTP_PORT
    db_path: str | Path = DEFAULT_DB_PATH
    static_dir: Path = DEFAULT_STATIC_DIR

    def __post_init__(self) -> None:
        if not (0 <= self.syslog_port <= 65535):
            raise ValueError(
                f"syslog_port must be between 0 and 65535, got {self.syslog_port}"
            )
        if not (0 <= self.http_port <= 65535):
            raise ValueError(
                f"http_port must be between 0 and 65535, got {self.http_port}"
            )
        self.static_dir = Path(self.static_dir)


def _env_int(env: Mapping[str, str], name: str, default: int) -> int:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw.strip())
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer") from exc


def parse_args(
    argv: Sequence[str] | None = None,
    environ: Mapping[str, str] | None = None,
) -> ServerConfig:
    """Parse CLI arguments with environment variable and default fallbacks."""
    env = os.environ if environ is None else environ

    default_syslog_host = env.get("INCIDENTBOT_SYSLOG_HOST") or DEFAULT_SYSLOG_HOST
    default_syslog_port = _env_int(env, "INCIDENTBOT_SYSLOG_PORT", DEFAULT_SYSLOG_PORT)
    default_http_host = env.get("INCIDENTBOT_HTTP_HOST") or DEFAULT_HTTP_HOST
    default_http_port = _env_int(env, "INCIDENTBOT_HTTP_PORT", DEFAULT_HTTP_PORT)
    default_db_path = env.get("INCIDENTBOT_DB_PATH") or DEFAULT_DB_PATH
    default_static_dir = Path(
        env.get("INCIDENTBOT_STATIC_DIR") or str(DEFAULT_STATIC_DIR)
    )

    parser = argparse.ArgumentParser(
        prog="python -m incidentbot.server",
        description="NetOps Incident Bot UDP syslog listener and HTTP API server.",
    )
    parser.add_argument(
        "--syslog-host",
        default=default_syslog_host,
        help="UDP syslog bind host (env: INCIDENTBOT_SYSLOG_HOST)",
    )
    parser.add_argument(
        "--syslog-port",
        type=int,
        default=default_syslog_port,
        help="UDP syslog bind port (env: INCIDENTBOT_SYSLOG_PORT)",
    )
    parser.add_argument(
        "--http-host",
        default=default_http_host,
        help="HTTP API bind host (env: INCIDENTBOT_HTTP_HOST)",
    )
    parser.add_argument(
        "--http-port",
        type=int,
        default=default_http_port,
        help="HTTP API bind port (env: INCIDENTBOT_HTTP_PORT)",
    )
    parser.add_argument(
        "--db-path",
        default=default_db_path,
        help="SQLite database path (env: INCIDENTBOT_DB_PATH)",
    )
    parser.add_argument(
        "--static-dir",
        type=Path,
        default=default_static_dir,
        help="Directory for static web dashboard assets (env: INCIDENTBOT_STATIC_DIR)",
    )

    args = parser.parse_args(argv)
    return ServerConfig(
        syslog_host=args.syslog_host,
        syslog_port=args.syslog_port,
        http_host=args.http_host,
        http_port=args.http_port,
        db_path=args.db_path,
        static_dir=args.static_dir,
    )


def _parse_non_negative_int(raw: str, name: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"Query parameter '{name}' must be a non-negative integer") from exc
    if value < 0:
        raise ValueError(f"Query parameter '{name}' must be a non-negative integer")
    return value


def _content_type_for_path(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in _CONTENT_TYPES:
        return _CONTENT_TYPES[suffix]
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed or "application/octet-stream"


def _resolve_static_file(
    static_dir: Path,
    relative_path: str,
    *,
    allowed_extensions: frozenset[str] | None = None,
) -> Path | None:
    """Resolve a static file safely inside static_dir, preventing path traversal."""
    if not relative_path or "\x00" in relative_path or "\\" in relative_path:
        return None
    if relative_path.startswith("/"):
        return None

    parts = relative_path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return None

    base = static_dir.resolve()
    if not base.is_dir():
        return None

    try:
        candidate = (base / relative_path).resolve()
    except OSError:
        return None

    if not candidate.is_relative_to(base):
        return None
    if allowed_extensions is not None and candidate.suffix.lower() not in allowed_extensions:
        return None
    if not candidate.is_file():
        return None
    return candidate


def _counts_by_severity(incidents: Sequence[Incident]) -> dict[str, int]:
    counts: dict[str, int] = {
        SEVERITY_CRITICAL: 0,
        SEVERITY_HIGH: 0,
        SEVERITY_MEDIUM: 0,
        SEVERITY_LOW: 0,
    }
    for inc in incidents:
        counts[inc.severity] = counts.get(inc.severity, 0) + 1
    return counts


class _SyslogUDPHandler(socketserver.BaseRequestHandler):
    """Handles incoming UDP syslog datagrams."""

    server: _SyslogUDPServer

    def handle(self) -> None:
        data = self.request[0]
        if not isinstance(data, (bytes, bytearray)):
            return
        try:
            self.server.service.ingest_payload(bytes(data))
        except Exception:
            logger.exception("Failed to process UDP syslog datagram")


class _SyslogUDPServer(socketserver.ThreadingUDPServer):
    """Threaded UDP server bound to an IncidentBotService."""

    allow_reuse_address = True
    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        service: IncidentBotService,
    ) -> None:
        self.service = service
        super().__init__(server_address, _SyslogUDPHandler)


class _IncidentHTTPServer(ThreadingHTTPServer):
    """Threaded HTTP server bound to an IncidentBotService."""

    allow_reuse_address = True
    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        service: IncidentBotService,
    ) -> None:
        self.service = service
        super().__init__(server_address, _IncidentHTTPRequestHandler)


class _IncidentHTTPRequestHandler(BaseHTTPRequestHandler):
    """REST API and static dashboard HTTP request handler."""

    server: _IncidentHTTPServer
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:
        logger.debug("HTTP %s - " + format, self.address_string(), *args)

    def _send_bytes(
        self,
        status: int,
        body: bytes,
        content_type: str,
        *,
        cache_control: str | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if cache_control is not None:
            self.send_header("Cache-Control", cache_control)
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, payload: Mapping[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self._send_bytes(
            status,
            body,
            "application/json; charset=utf-8",
            cache_control="no-store",
        )

    def _send_error_json(self, status: int, message: str) -> None:
        self._send_json(status, {"error": message})

    def _drain_request_body(self) -> None:
        raw_len = self.headers.get("Content-Length")
        if not raw_len:
            return
        try:
            length = int(raw_len)
        except ValueError:
            return
        if length > 0:
            self.rfile.read(length)

    def _serve_static(
        self,
        relative_path: str,
        *,
        allowed_extensions: frozenset[str] | None = None,
    ) -> None:
        file_path = _resolve_static_file(
            self.server.service.static_dir,
            relative_path,
            allowed_extensions=allowed_extensions,
        )
        if file_path is None:
            self._send_error_json(HTTPStatus.NOT_FOUND, "Not found")
            return
        try:
            body = file_path.read_bytes()
        except OSError:
            self._send_error_json(HTTPStatus.NOT_FOUND, "Not found")
            return
        self._send_bytes(HTTPStatus.OK, body, _content_type_for_path(file_path))

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)
        raw_path = parsed.path
        query = parse_qs(parsed.query, keep_blank_values=True)

        if raw_path == "/api/health":
            self._handle_health()
            return

        if raw_path == "/api/incidents":
            self._handle_list_incidents(query)
            return

        if raw_path.startswith("/api/incidents/"):
            rest = raw_path[len("/api/incidents/") :]
            if "/" in rest or not rest:
                self._send_error_json(HTTPStatus.NOT_FOUND, "Not found")
                return
            incident_id = unquote(rest)
            self._handle_get_incident(incident_id)
            return

        if raw_path == "/api/events":
            self._handle_list_events(query)
            return

        if raw_path == "/api" or raw_path.startswith("/api/"):
            self._send_error_json(HTTPStatus.NOT_FOUND, "Not found")
            return

        # Reject encoded or literal traversal markers in raw path before routing static files.
        decoded_path = unquote(raw_path)
        if ".." in raw_path or ".." in decoded_path or "\\" in raw_path or "\\" in decoded_path:
            self._send_error_json(HTTPStatus.NOT_FOUND, "Not found")
            return

        if decoded_path == "/":
            self._serve_static("index.html")
            return

        if decoded_path.startswith("/static/"):
            rel_name = decoded_path[len("/static/") :]
            self._serve_static(rel_name)
            return

        if decoded_path.startswith("/"):
            rel_name = decoded_path[1:]
            self._serve_static(rel_name, allowed_extensions=_ROOT_STATIC_EXTENSIONS)
            return

        self._send_error_json(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:  # noqa: N802
        self._drain_request_body()
        parsed = urlsplit(self.path)
        raw_path = parsed.path

        if raw_path.startswith("/api/incidents/") and raw_path.endswith("/resolve"):
            inner = raw_path[len("/api/incidents/") : -len("/resolve")]
            if not inner or "/" in inner:
                self._send_error_json(HTTPStatus.NOT_FOUND, "Not found")
                return
            incident_id = unquote(inner)
            self._handle_resolve_incident(incident_id)
            return

        self._send_error_json(HTTPStatus.NOT_FOUND, "Not found")

    def _handle_health(self) -> None:
        store = self.server.service.store
        self._send_json(
            HTTPStatus.OK,
            {
                "status": "ok",
                "events_count": store.count_events(),
                "open_incidents": store.count_incidents(status=STATUS_OPEN),
            },
        )

    def _handle_list_incidents(self, query: dict[str, list[str]]) -> None:
        status: str | None = None
        if "status" in query:
            raw_status = query["status"][0].strip()
            if raw_status:
                if raw_status not in VALID_STATUSES:
                    self._send_error_json(
                        HTTPStatus.BAD_REQUEST,
                        f"Invalid status {raw_status!r}; expected one of {sorted(VALID_STATUSES)}",
                    )
                    return
                status = raw_status

        severity: str | None = None
        if "severity" in query:
            raw_sev = query["severity"][0].strip()
            if raw_sev:
                severity = raw_sev

        inc_type: str | None = None
        if "type" in query:
            raw_type = query["type"][0].strip()
            if raw_type:
                inc_type = raw_type

        limit: int | None = None
        if "limit" in query:
            raw_limit = query["limit"][0].strip()
            if raw_limit:
                try:
                    limit = _parse_non_negative_int(raw_limit, "limit")
                except ValueError as exc:
                    self._send_error_json(HTTPStatus.BAD_REQUEST, str(exc))
                    return

        incidents = self.server.service.store.list_incidents(
            status=status,
            severity=severity,
            incident_type=inc_type,
            limit=limit,
        )
        self._send_json(
            HTTPStatus.OK,
            {
                "incidents": [inc.to_dict() for inc in incidents],
                "counts_by_severity": _counts_by_severity(incidents),
            },
        )

    def _handle_get_incident(self, incident_id: str) -> None:
        service = self.server.service
        inc = service.store.get_incident(incident_id)
        if inc is None:
            self._send_error_json(HTTPStatus.NOT_FOUND, "Incident not found")
            return

        events = service.get_incident_events(inc)
        self._send_json(
            HTTPStatus.OK,
            {
                "incident": inc.to_dict(),
                "events": [ev.to_dict() for ev in events],
            },
        )

    def _handle_list_events(self, query: dict[str, list[str]]) -> None:
        limit = DEFAULT_EVENTS_LIMIT
        if "limit" in query:
            raw_limit = query["limit"][0].strip()
            try:
                limit = _parse_non_negative_int(raw_limit, "limit")
            except ValueError as exc:
                self._send_error_json(HTTPStatus.BAD_REQUEST, str(exc))
                return

        events = self.server.service.store.list_events(limit=limit)
        self._send_json(
            HTTPStatus.OK,
            {"events": [ev.to_dict() for ev in events]},
        )

    def _handle_resolve_incident(self, incident_id: str) -> None:
        resolved = self.server.service.resolve_incident(incident_id)
        if resolved is None:
            self._send_error_json(HTTPStatus.NOT_FOUND, "Incident not found")
            return
        self._send_json(HTTPStatus.OK, {"incident": resolved.to_dict()})


class IncidentBotService:
    """Coordinated UDP syslog ingestion, correlation, persistence, and HTTP API service."""

    def __init__(
        self,
        config: ServerConfig | None = None,
        *,
        syslog_host: str | None = None,
        syslog_port: int | None = None,
        http_host: str | None = None,
        http_port: int | None = None,
        db_path: str | Path | None = None,
        static_dir: str | Path | None = None,
        store: IncidentStore | None = None,
        correlator: Correlator | None = None,
    ) -> None:
        base = config if config is not None else ServerConfig()
        self.config = ServerConfig(
            syslog_host=base.syslog_host if syslog_host is None else syslog_host,
            syslog_port=base.syslog_port if syslog_port is None else syslog_port,
            http_host=base.http_host if http_host is None else http_host,
            http_port=base.http_port if http_port is None else http_port,
            db_path=base.db_path if db_path is None else db_path,
            static_dir=base.static_dir if static_dir is None else Path(static_dir),
        )
        self._owns_store = store is None
        self.store = store if store is not None else IncidentStore(self.config.db_path)
        self.correlator = correlator if correlator is not None else Correlator()
        self._ingest_lock = threading.RLock()
        self._lifecycle_lock = threading.RLock()

        self._udp_server: _SyslogUDPServer | None = None
        self._http_server: _IncidentHTTPServer | None = None
        self._udp_thread: threading.Thread | None = None
        self._http_thread: threading.Thread | None = None
        self._closed = False

    @property
    def static_dir(self) -> Path:
        return self.config.static_dir

    @property
    def is_running(self) -> bool:
        return self._udp_server is not None and self._http_server is not None

    @property
    def syslog_address(self) -> tuple[str, int]:
        if self._udp_server is None:
            return (self.config.syslog_host, self.config.syslog_port)
        host, port = self._udp_server.server_address[:2]
        return (str(host), int(port))

    @property
    def syslog_port(self) -> int:
        return self.syslog_address[1]

    @property
    def http_address(self) -> tuple[str, int]:
        if self._http_server is None:
            return (self.config.http_host, self.config.http_port)
        host, port = self._http_server.server_address[:2]
        return (str(host), int(port))

    @property
    def http_port(self) -> int:
        return self.http_address[1]

    @property
    def http_url(self) -> str:
        host, port = self.http_address
        return f"http://{host}:{port}"

    def __enter__(self) -> IncidentBotService:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        self.close()

    def start(self) -> None:
        """Bind UDP and HTTP listeners and start background serving threads."""
        with self._lifecycle_lock:
            if self._closed:
                raise RuntimeError("Cannot start a closed IncidentBotService")
            if self.is_running:
                return

            udp_server: _SyslogUDPServer | None = None
            http_server: _IncidentHTTPServer | None = None
            try:
                udp_server = _SyslogUDPServer(
                    (self.config.syslog_host, self.config.syslog_port),
                    self,
                )
                http_server = _IncidentHTTPServer(
                    (self.config.http_host, self.config.http_port),
                    self,
                )
            except Exception:
                if http_server is not None:
                    http_server.server_close()
                if udp_server is not None:
                    udp_server.server_close()
                raise

            self._udp_server = udp_server
            self._http_server = http_server

            self._udp_thread = threading.Thread(
                target=udp_server.serve_forever,
                kwargs={"poll_interval": 0.1},
                name="incidentbot-syslog-udp",
                daemon=True,
            )
            self._http_thread = threading.Thread(
                target=http_server.serve_forever,
                kwargs={"poll_interval": 0.1},
                name="incidentbot-http",
                daemon=True,
            )
            self._udp_thread.start()
            self._http_thread.start()

            logger.info(
                "IncidentBotService listening on UDP %s:%d and HTTP %s:%d",
                *self.syslog_address,
                *self.http_address,
            )

    def stop(self) -> None:
        """Stop the UDP and HTTP listeners cleanly (idempotent)."""
        with self._lifecycle_lock:
            udp_server = self._udp_server
            http_server = self._http_server
            udp_thread = self._udp_thread
            http_thread = self._http_thread

            self._udp_server = None
            self._http_server = None
            self._udp_thread = None
            self._http_thread = None

        if http_server is not None:
            http_server.shutdown()
            http_server.server_close()
        if udp_server is not None:
            udp_server.shutdown()
            udp_server.server_close()

        if http_thread is not None and http_thread.is_alive():
            http_thread.join(timeout=5.0)
        if udp_thread is not None and udp_thread.is_alive():
            udp_thread.join(timeout=5.0)

    def close(self) -> None:
        """Stop listeners and close the underlying store (idempotent)."""
        self.stop()
        with self._lifecycle_lock:
            if self._closed:
                return
            self._closed = True
            if self._owns_store:
                self.store.close()

    def ingest_line(self, line: str) -> Event | None:
        """Parse, store, and correlate a single syslog line."""
        event = parse_line(line)
        if event is None:
            return None

        with self._ingest_lock:
            self.store.add_event(event)
            affected = self.correlator.process_event(event)
            for inc in affected:
                self.store.upsert_incident(inc)
        return event

    def ingest_payload(self, payload: bytes | str) -> list[Event]:
        """Decode and ingest a single-line or multi-line UDP syslog payload."""
        text = (
            payload.decode("utf-8", errors="replace")
            if isinstance(payload, (bytes, bytearray))
            else payload
        )
        ingested: list[Event] = []
        for line in text.splitlines():
            if not line.strip():
                continue
            event = self.ingest_line(line)
            if event is not None:
                ingested.append(event)
        return ingested

    def resolve_incident(self, incident_id: str) -> Incident | None:
        """Resolve an incident in both the in-memory correlator and SQLite store."""
        with self._ingest_lock:
            self.correlator.mark_resolved(incident_id)
            return self.store.resolve_incident(incident_id)

    def get_incident_events(self, incident: Incident) -> list[Event]:
        """Return persisted events matching an incident's type, key, and time span."""
        if incident.type == INCIDENT_INTERFACE_FLAP:
            parts = incident.key.split(":", 2)
            if len(parts) != 3:
                return []
            _, host, iface = parts
            candidates = self.store.list_events(
                host=host,
                since=incident.first_seen,
                until=incident.last_seen,
            )
            return [
                ev
                for ev in candidates
                if ev.interface == iface
                and ev.kind in (EVENT_INTERFACE_DOWN, EVENT_INTERFACE_UP)
            ]

        if incident.type == INCIDENT_BGP_NEIGHBOR_DOWN:
            parts = incident.key.split(":", 2)
            if len(parts) != 3:
                return []
            _, host, peer = parts
            candidates = self.store.list_events(
                host=host,
                since=incident.first_seen,
                until=incident.last_seen,
            )
            return [
                ev
                for ev in candidates
                if ev.peer == peer and ev.kind in (EVENT_BGP_DOWN, EVENT_BGP_UP)
            ]

        if incident.type == INCIDENT_AUTH_BRUTE_FORCE:
            parts = incident.key.split(":", 1)
            if len(parts) != 2:
                return []
            _, src_ip = parts
            return self.store.list_events(
                src_ip=src_ip,
                kind=EVENT_AUTH_FAILED,
                since=incident.first_seen,
                until=incident.last_seen,
            )

        if incident.type == INCIDENT_CONFIG_CHANGE:
            parts = incident.key.split(":", 1)
            if len(parts) != 2:
                return []
            _, host = parts
            return self.store.list_events(
                host=host,
                kind=EVENT_CONFIG_CHANGE,
                since=incident.first_seen,
                until=incident.last_seen,
            )

        return []


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for `python -m incidentbot.server`."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = parse_args(argv)
    stop_event = threading.Event()

    def _handle_signal(signum: int, _frame: object) -> None:
        logger.info("Received signal %d; shutting down...", signum)
        stop_event.set()

    previous_handlers: dict[int, Any] = {}
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            previous_handlers[sig] = signal.getsignal(sig)
            signal.signal(sig, _handle_signal)
        except (ValueError, OSError):
            pass

    service = IncidentBotService(config)
    try:
        service.start()
        while not stop_event.wait(timeout=0.5):
            pass
    except KeyboardInterrupt:
        logger.info("Interrupted; shutting down...")
    finally:
        service.close()
        for sig, prev in previous_handlers.items():
            try:
                signal.signal(sig, prev)
            except (ValueError, OSError):
                pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
