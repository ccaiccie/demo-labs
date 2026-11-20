"""Unit tests for tools/replay.py and sample syslog datasets."""

from __future__ import annotations

import contextlib
import io
import ipaddress
from pathlib import Path
import re
import socket
import tempfile
import threading
import unittest

from incidentbot.correlator import Correlator
from incidentbot.models import (
    INCIDENT_AUTH_BRUTE_FORCE,
    INCIDENT_BGP_NEIGHBOR_DOWN,
    INCIDENT_CONFIG_CHANGE,
    INCIDENT_INTERFACE_FLAP,
    STATUS_OPEN,
)
from incidentbot.parser import parse_lines
from tools import replay

REPO_ROOT = Path(__file__).resolve().parent.parent
CISCO_SAMPLE = REPO_ROOT / "samples" / "cisco_edge.log"
FORTIGATE_SAMPLE = REPO_ROOT / "samples" / "fortigate.log"

RFC5737_NETWORKS = (
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
)
IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def _receive_udp_datagrams(
    sock: socket.socket, expected: int, timeout: float = 2.0
) -> tuple[list[str], threading.Thread]:
    """Start a background thread that collects UDP datagrams into a list."""
    received: list[str] = []
    sock.settimeout(timeout)

    def _worker() -> None:
        while len(received) < expected:
            try:
                data, _ = sock.recvfrom(65535)
            except TimeoutError:
                break
            received.append(data.decode("utf-8"))

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    return received, thread


class ReplayToolTests(unittest.TestCase):
    def test_iter_log_lines_skips_blank_and_comment_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "sample.log"
            log_path.write_text(
                "\n# leading comment\n   # indented comment\nline one\n  \nline two  \n",
                encoding="utf-8",
            )
            self.assertEqual(list(replay.iter_log_lines([log_path])), ["line one", "line two"])

    def test_compute_delay_and_validation(self) -> None:
        self.assertEqual(replay.compute_delay(0), 0.0)
        self.assertEqual(replay.compute_delay(float("inf")), 0.0)
        self.assertAlmostEqual(replay.compute_delay(1.0), 0.05)
        self.assertAlmostEqual(replay.compute_delay(2.0), 0.025)
        with self.assertRaises(ValueError):
            replay.compute_delay(-1.0)
        with self.assertRaises(ValueError):
            replay.compute_delay(float("nan"))

    def test_replay_udp_speed_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "events.log"
            expected_lines = [
                "<189>Nov 20 12:00:01 lab-rtr-01 %LINK-3-UPDOWN: Interface Gi0/1, changed state to down",
                "<189>Nov 20 12:00:02 lab-rtr-01 %LINK-3-UPDOWN: Interface Gi0/1, changed state to up",
                "<189>Nov 20 12:00:03 lab-rtr-01 %BGP-5-ADJCHANGE: neighbor 198.51.100.1 Down",
            ]
            log_path.write_text(
                "# header comment\n\n" + "\n".join(expected_lines) + "\n",
                encoding="utf-8",
            )

            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server:
                server.bind(("127.0.0.1", 0))
                port = server.getsockname()[1]
                received, thread = _receive_udp_datagrams(server, len(expected_lines))

                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    exit_code = replay.main(
                        [
                            "--host",
                            "127.0.0.1",
                            "--port",
                            str(port),
                            "--speed",
                            "0",
                            str(log_path),
                        ]
                    )

                thread.join(timeout=2.0)

            self.assertEqual(exit_code, 0)
            self.assertEqual(received, expected_lines)
            self.assertIn(f"127.0.0.1:{port}", stdout.getvalue())
            self.assertIn("Replayed 3 events", stdout.getvalue())

    def test_replay_udp_positive_speed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "paced.log"
            expected_lines = ["event-1", "event-2", "event-3"]
            log_path.write_text("\n".join(expected_lines) + "\n", encoding="utf-8")

            recorded_delays: list[float] = []
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server:
                server.bind(("127.0.0.1", 0))
                port = server.getsockname()[1]
                received, thread = _receive_udp_datagrams(server, len(expected_lines))

                sent = replay.replay_files(
                    [log_path],
                    host="127.0.0.1",
                    port=port,
                    speed=10.0,
                    sleep_fn=recorded_delays.append,
                )

                thread.join(timeout=2.0)

            self.assertEqual(sent, len(expected_lines))
            self.assertEqual(received, expected_lines)
            self.assertEqual(len(recorded_delays), len(expected_lines) - 1)
            for delay in recorded_delays:
                self.assertAlmostEqual(delay, 0.005)

    def test_cli_rejects_negative_speed(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as ctx:
                replay.main(["--speed", "-0.5", str(CISCO_SAMPLE)])
        self.assertNotEqual(ctx.exception.code, 0)


class SampleDatasetTests(unittest.TestCase):
    def test_samples_trigger_expected_open_incidents(self) -> None:
        lines = list(replay.iter_log_lines([CISCO_SAMPLE, FORTIGATE_SAMPLE]))
        events = parse_lines(lines, default_year=2026)
        self.assertEqual(len(events), len(lines))

        correlator = Correlator()
        correlator.process_events(events)

        open_incidents = correlator.get_open_incidents()
        open_types = {inc.type for inc in open_incidents}

        self.assertIn(INCIDENT_INTERFACE_FLAP, open_types)
        self.assertIn(INCIDENT_BGP_NEIGHBOR_DOWN, open_types)
        self.assertIn(INCIDENT_AUTH_BRUTE_FORCE, open_types)
        self.assertIn(INCIDENT_CONFIG_CHANGE, open_types)

        for inc in open_incidents:
            self.assertEqual(inc.status, STATUS_OPEN)

    def test_sample_ipv4_addresses_strictly_rfc5737(self) -> None:
        for sample_path in (CISCO_SAMPLE, FORTIGATE_SAMPLE):
            text = sample_path.read_text(encoding="utf-8")
            matches = IPV4_RE.findall(text)
            self.assertGreater(
                len(matches),
                0,
                f"Expected at least one IPv4 address in {sample_path.name}",
            )
            for raw_ip in matches:
                addr = ipaddress.ip_address(raw_ip)
                in_rfc5737 = any(addr in net for net in RFC5737_NETWORKS)
                self.assertTrue(
                    in_rfc5737,
                    f"Non-RFC5737 IPv4 address {raw_ip} found in {sample_path.name}",
                )


if __name__ == "__main__":
    unittest.main()
