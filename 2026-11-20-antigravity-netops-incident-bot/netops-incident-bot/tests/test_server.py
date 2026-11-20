"""Unit and integration tests for incidentbot.server."""

from __future__ import annotations

import http.client
import json
from pathlib import Path
import socket
import tempfile
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from incidentbot.models import (
    EVENT_AUTH_FAILED,
    EVENT_BGP_DOWN,
    EVENT_INTERFACE_DOWN,
    EVENT_INTERFACE_UP,
    INCIDENT_AUTH_BRUTE_FORCE,
    INCIDENT_BGP_NEIGHBOR_DOWN,
    INCIDENT_INTERFACE_FLAP,
    STATUS_OPEN,
    STATUS_RESOLVED,
)
from incidentbot.server import (
    DEFAULT_DB_PATH,
    DEFAULT_HTTP_HOST,
    DEFAULT_HTTP_PORT,
    DEFAULT_STATIC_DIR,
    DEFAULT_SYSLOG_HOST,
    DEFAULT_SYSLOG_PORT,
    IncidentBotService,
    ServerConfig,
    parse_args,
)


def _http_json(
    url: str,
    *,
    method: str = "GET",
    body: bytes | None = None,
) -> tuple[int, dict[str, object]]:
    req = Request(url, data=body, method=method)
    try:
        with urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except HTTPError as err:
        payload = json.loads(err.read().decode("utf-8"))
        return err.code, payload


def _http_raw(
    host: str,
    port: int,
    path: str,
    *,
    method: str = "GET",
) -> tuple[int, str, bytes]:
    conn = http.client.HTTPConnection(host, port, timeout=5)
    try:
        conn.request(method, path)
        resp = conn.getresponse()
        data = resp.read()
        return resp.status, resp.getheader("Content-Type", ""), data
    finally:
        conn.close()


def _send_udp(host: str, port: int, payload: str | bytes) -> None:
    raw = payload.encode("utf-8") if isinstance(payload, str) else payload
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(raw, (host, port))


def _wait_until(predicate, *, timeout: float = 3.0, interval: float = 0.02) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


class TestServerConfig(unittest.TestCase):
    """Tests for CLI and environment configuration parsing."""

    def test_defaults_when_no_env_or_args(self) -> None:
        cfg = parse_args([], environ={})
        self.assertEqual(cfg.syslog_host, DEFAULT_SYSLOG_HOST)
        self.assertEqual(cfg.syslog_port, DEFAULT_SYSLOG_PORT)
        self.assertEqual(cfg.http_host, DEFAULT_HTTP_HOST)
        self.assertEqual(cfg.http_port, DEFAULT_HTTP_PORT)
        self.assertEqual(cfg.db_path, DEFAULT_DB_PATH)
        self.assertEqual(cfg.static_dir, DEFAULT_STATIC_DIR)

    def test_env_overrides_defaults(self) -> None:
        env = {
            "INCIDENTBOT_SYSLOG_HOST": "127.0.0.1",
            "INCIDENTBOT_SYSLOG_PORT": "15515",
            "INCIDENTBOT_HTTP_HOST": "127.0.0.1",
            "INCIDENTBOT_HTTP_PORT": "18097",
            "INCIDENTBOT_DB_PATH": "custom.db",
            "INCIDENTBOT_STATIC_DIR": "/tmp/custom-web",
        }
        cfg = parse_args([], environ=env)
        self.assertEqual(cfg.syslog_host, "127.0.0.1")
        self.assertEqual(cfg.syslog_port, 15515)
        self.assertEqual(cfg.http_host, "127.0.0.1")
        self.assertEqual(cfg.http_port, 18097)
        self.assertEqual(cfg.db_path, "custom.db")
        self.assertEqual(cfg.static_dir, Path("/tmp/custom-web"))

    def test_cli_overrides_env(self) -> None:
        env = {
            "INCIDENTBOT_SYSLOG_HOST": "127.0.0.1",
            "INCIDENTBOT_SYSLOG_PORT": "15515",
            "INCIDENTBOT_HTTP_PORT": "18097",
        }
        cfg = parse_args(
            [
                "--syslog-host",
                "127.0.0.1",
                "--syslog-port",
                "0",
                "--http-host",
                "127.0.0.1",
                "--http-port",
                "0",
                "--db-path",
                ":memory:",
            ],
            environ=env,
        )
        self.assertEqual(cfg.syslog_port, 0)
        self.assertEqual(cfg.http_port, 0)
        self.assertEqual(cfg.db_path, ":memory:")

    def test_invalid_port_raises(self) -> None:
        with self.assertRaises(ValueError):
            ServerConfig(syslog_port=-1)
        with self.assertRaises(ValueError):
            ServerConfig(http_port=70000)


class TestIncidentBotService(unittest.TestCase):
    """End-to-end tests for UDP ingestion, REST API, and static file serving."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        self.static_dir = self.root / "web"
        self.static_dir.mkdir(parents=True, exist_ok=True)
        (self.static_dir / "index.html").write_text(
            "<!doctype html><html><body><h1>NetOps Lab</h1></body></html>",
            encoding="utf-8",
        )
        (self.static_dir / "app.js").write_text(
            "console.log('netops');",
            encoding="utf-8",
        )
        (self.static_dir / "style.css").write_text(
            "body { background: #111; }",
            encoding="utf-8",
        )
        (self.static_dir / "notes.txt").write_text(
            "plain text note",
            encoding="utf-8",
        )
        # File outside static_dir used to verify path-traversal protection.
        (self.root / "outside.txt").write_text(
            "must not be served",
            encoding="utf-8",
        )

        self.db_path = self.root / "test.db"
        self.service = IncidentBotService(
            syslog_host="127.0.0.1",
            syslog_port=0,
            http_host="127.0.0.1",
            http_port=0,
            db_path=self.db_path,
            static_dir=self.static_dir,
        )
        self.service.start()

    def tearDown(self) -> None:
        self.service.close()
        self._tmpdir.cleanup()

    def test_ephemeral_ports_and_health_empty(self) -> None:
        self.assertTrue(self.service.is_running)
        self.assertGreater(self.service.syslog_port, 0)
        self.assertGreater(self.service.http_port, 0)

        status, data = _http_json(f"{self.service.http_url}/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(
            data,
            {"status": "ok", "events_count": 0, "open_incidents": 0},
        )

    def test_udp_ingestion_correlation_and_rest_endpoints(self) -> None:
        # 1) Multi-line UDP payload: 3 interface flaps on lab-edge-rtr-01 Gi0/1
        #    plus an unrelated interface event on Gi0/2 in the same time window.
        flap_payload = "\n".join(
            [
                "<189>Nov 20 10:00:01 lab-edge-rtr-01 %LINK-3-UPDOWN: Interface GigabitEthernet0/1, changed state to down",
                "<189>Nov 20 10:00:10 lab-edge-rtr-01 %LINK-3-UPDOWN: Interface GigabitEthernet0/1, changed state to up",
                "<189>Nov 20 10:00:15 lab-edge-rtr-01 %LINK-3-UPDOWN: Interface GigabitEthernet0/2, changed state to down",
                "<189>Nov 20 10:00:20 lab-edge-rtr-01 %LINK-3-UPDOWN: Interface GigabitEthernet0/1, changed state to down",
                "unparseable garbage line should be ignored",
            ]
        )
        _send_udp("127.0.0.1", self.service.syslog_port, flap_payload)

        # 2) Single-line BGP neighbor down (remains open) + another peer that recovers.
        _send_udp(
            "127.0.0.1",
            self.service.syslog_port,
            "<187>Nov 20 10:01:00 lab-core-rtr-02 %BGP-5-ADJCHANGE: neighbor 198.51.100.10 Down Peer closed the session",
        )
        _send_udp(
            "127.0.0.1",
            self.service.syslog_port,
            "<187>Nov 20 10:01:05 lab-core-rtr-02 %BGP-5-ADJCHANGE: neighbor 198.51.100.20 Down Hold timer expired",
        )
        _send_udp(
            "127.0.0.1",
            self.service.syslog_port,
            "<189>Nov 20 10:01:15 lab-core-rtr-02 %BGP-5-ADJCHANGE: neighbor 198.51.100.20 Up",
        )

        # 3) FortiGate brute-force auth failures (5 events from 203.0.113.55 within 60s)
        #    plus 1 failed login from another IP in the same window.
        fg_lines = [
            f'<190>date=2026-11-20 time=10:02:0{i} devname="lab-fw-edge-01" type="event" level="warning" logdesc="Admin login failed" action="login" status="failed" user="admin" srcip=203.0.113.55'
            for i in range(1, 6)
        ]
        fg_lines.append(
            '<190>date=2026-11-20 time=10:02:03 devname="lab-fw-edge-01" type="event" level="warning" logdesc="Admin login failed" action="login" status="failed" user="ops" srcip=192.0.2.99'
        )
        _send_udp("127.0.0.1", self.service.syslog_port, "\n".join(fg_lines))

        # Expected: 4 interface + 3 bgp + 6 auth = 13 events, 4 total incidents (3 open, 1 auto-resolved).
        ok = _wait_until(
            lambda: self.service.store.count_events() == 13
            and self.service.store.count_incidents() == 4
        )
        self.assertTrue(ok, "Timed out waiting for UDP events and incidents to persist")

        # Verify /api/health
        status, health = _http_json(f"{self.service.http_url}/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(health["status"], "ok")
        self.assertEqual(health["events_count"], 13)
        self.assertEqual(health["open_incidents"], 3)

        # Verify /api/incidents (all)
        status, all_inc = _http_json(f"{self.service.http_url}/api/incidents")
        self.assertEqual(status, 200)
        self.assertEqual(len(all_inc["incidents"]), 4)
        self.assertEqual(
            all_inc["counts_by_severity"],
            {"critical": 2, "high": 1, "medium": 1, "low": 0},
        )

        # Verify /api/incidents?status=open
        status, open_inc = _http_json(
            f"{self.service.http_url}/api/incidents?status=open"
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(open_inc["incidents"]), 3)
        self.assertEqual(
            open_inc["counts_by_severity"],
            {"critical": 1, "high": 1, "medium": 1, "low": 0},
        )

        # Verify /api/incidents?status=resolved
        status, resolved_inc = _http_json(
            f"{self.service.http_url}/api/incidents?status=resolved"
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(resolved_inc["incidents"]), 1)
        self.assertEqual(resolved_inc["incidents"][0]["type"], INCIDENT_BGP_NEIGHBOR_DOWN)
        self.assertEqual(resolved_inc["incidents"][0]["status"], STATUS_RESOLVED)

        # Verify /api/incidents filtering by severity, type, and limit
        status, high_only = _http_json(
            f"{self.service.http_url}/api/incidents?severity=high&type={INCIDENT_AUTH_BRUTE_FORCE}&limit=1"
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(high_only["incidents"]), 1)
        self.assertEqual(
            high_only["counts_by_severity"],
            {"critical": 0, "high": 1, "medium": 0, "low": 0},
        )

        # Verify /api/incidents/{id} detail matching for all 3 incident types
        by_type = {inc["type"]: inc for inc in open_inc["incidents"]}
        self.assertIn(INCIDENT_INTERFACE_FLAP, by_type)
        self.assertIn(INCIDENT_BGP_NEIGHBOR_DOWN, by_type)
        self.assertIn(INCIDENT_AUTH_BRUTE_FORCE, by_type)

        # 1) Interface flap detail: only Gi0/1 events (3), not Gi0/2
        flap_id = by_type[INCIDENT_INTERFACE_FLAP]["id"]
        status, flap_detail = _http_json(
            f"{self.service.http_url}/api/incidents/{flap_id}"
        )
        self.assertEqual(status, 200)
        self.assertEqual(flap_detail["incident"]["id"], flap_id)
        self.assertEqual(len(flap_detail["events"]), 3)
        for ev in flap_detail["events"]:
            self.assertEqual(ev["host"], "lab-edge-rtr-01")
            self.assertEqual(ev["interface"], "GigabitEthernet0/1")
            self.assertIn(ev["kind"], (EVENT_INTERFACE_DOWN, EVENT_INTERFACE_UP))

        # 2) BGP detail: only peer 198.51.100.10 (1 down event)
        bgp_id = by_type[INCIDENT_BGP_NEIGHBOR_DOWN]["id"]
        status, bgp_detail = _http_json(
            f"{self.service.http_url}/api/incidents/{bgp_id}"
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(bgp_detail["events"]), 1)
        self.assertEqual(bgp_detail["events"][0]["peer"], "198.51.100.10")
        self.assertEqual(bgp_detail["events"][0]["kind"], EVENT_BGP_DOWN)

        # 3) Auth brute force detail: only src_ip 203.0.113.55 (5 events), not 192.0.2.99
        auth_id = by_type[INCIDENT_AUTH_BRUTE_FORCE]["id"]
        status, auth_detail = _http_json(
            f"{self.service.http_url}/api/incidents/{auth_id}"
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(auth_detail["events"]), 5)
        for ev in auth_detail["events"]:
            self.assertEqual(ev["src_ip"], "203.0.113.55")
            self.assertEqual(ev["kind"], EVENT_AUTH_FAILED)

        # Verify /api/events with default and explicit limit
        status, events_default = _http_json(f"{self.service.http_url}/api/events")
        self.assertEqual(status, 200)
        self.assertEqual(len(events_default["events"]), 13)

        status, events_limited = _http_json(
            f"{self.service.http_url}/api/events?limit=5"
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(events_limited["events"]), 5)

        # Verify POST /api/incidents/{id}/resolve
        status, resolved_resp = _http_json(
            f"{self.service.http_url}/api/incidents/{bgp_id}/resolve",
            method="POST",
            body=b"",
        )
        self.assertEqual(status, 200)
        self.assertEqual(resolved_resp["incident"]["id"], bgp_id)
        self.assertEqual(resolved_resp["incident"]["status"], STATUS_RESOLVED)

        # Correlator and store both reflect resolution
        corr_inc = self.service.correlator.get_incident(bgp_id)
        self.assertIsNotNone(corr_inc)
        self.assertEqual(corr_inc.status, STATUS_RESOLVED)
        store_inc = self.service.store.get_incident(bgp_id)
        self.assertIsNotNone(store_inc)
        self.assertEqual(store_inc.status, STATUS_RESOLVED)

        status, health_after = _http_json(f"{self.service.http_url}/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(health_after["open_incidents"], 2)

    def test_api_validation_and_error_responses(self) -> None:
        # Invalid status on /api/incidents
        status, payload = _http_json(
            f"{self.service.http_url}/api/incidents?status=bogus"
        )
        self.assertEqual(status, 400)
        self.assertIn("error", payload)

        # Invalid limit on /api/incidents
        status, payload = _http_json(
            f"{self.service.http_url}/api/incidents?limit=-5"
        )
        self.assertEqual(status, 400)
        self.assertIn("error", payload)

        # Invalid / negative limit on /api/events
        for bad in ("abc", "-1", ""):
            status, payload = _http_json(
                f"{self.service.http_url}/api/events?limit={bad}"
            )
            self.assertEqual(status, 400)
            self.assertIn("error", payload)

        # Missing incident detail -> 404
        status, payload = _http_json(
            f"{self.service.http_url}/api/incidents/inc-does-not-exist"
        )
        self.assertEqual(status, 404)
        self.assertEqual(payload, {"error": "Incident not found"})

        # Missing incident resolve -> 404
        status, payload = _http_json(
            f"{self.service.http_url}/api/incidents/inc-does-not-exist/resolve",
            method="POST",
            body=b"",
        )
        self.assertEqual(status, 404)
        self.assertEqual(payload, {"error": "Incident not found"})

        # Unknown API route -> 404
        status, payload = _http_json(f"{self.service.http_url}/api/unknown")
        self.assertEqual(status, 404)
        self.assertIn("error", payload)

    def test_static_files_and_path_traversal_protection(self) -> None:
        host, port = self.service.http_address

        # GET / serves index.html
        status, content_type, body = _http_raw(host, port, "/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn(b"NetOps Lab", body)

        # GET /static/app.js and GET /app.js
        for path in ("/static/app.js", "/app.js"):
            status, content_type, body = _http_raw(host, port, path)
            self.assertEqual(status, 200, msg=f"Failed for {path}")
            self.assertIn("javascript", content_type)
            self.assertEqual(body, b"console.log('netops');")

        # GET /static/style.css and GET /style.css
        for path in ("/static/style.css", "/style.css"):
            status, content_type, body = _http_raw(host, port, path)
            self.assertEqual(status, 200, msg=f"Failed for {path}")
            self.assertIn("text/css", content_type)
            self.assertEqual(body, b"body { background: #111; }")

        # Root path rejects non-.html/.js/.css files even if present in static_dir
        status, _, _ = _http_raw(host, port, "/notes.txt")
        self.assertEqual(status, 404)

        # Missing static file -> 404
        status, _, _ = _http_raw(host, port, "/static/missing.js")
        self.assertEqual(status, 404)

        # Path traversal attempts -> 404
        traversal_paths = [
            "/static/../outside.txt",
            "/static/%2e%2e/outside.txt",
            "/../outside.txt",
            "/%2e%2e/outside.txt",
            "/static/..%5coutside.txt",
            "/static/..\\outside.txt",
        ]
        for bad_path in traversal_paths:
            status, _, body = _http_raw(host, port, bad_path)
            self.assertEqual(status, 404, msg=f"Traversal was not blocked: {bad_path}")
            self.assertNotIn(b"must not be served", body)

    def test_stop_and_close_are_idempotent(self) -> None:
        self.service.stop()
        self.assertFalse(self.service.is_running)
        self.service.stop()
        self.service.close()
        self.service.close()


if __name__ == "__main__":
    unittest.main()
