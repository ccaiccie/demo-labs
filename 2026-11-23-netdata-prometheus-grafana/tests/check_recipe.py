"""Offline deterministic checks. No containers, sockets, or outside services."""
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
import io
import json
import re
import runpy
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
LAT = "netdata_statsd_lab_checkout_latency_ms_gauge_value_average"
QUEUE = "netdata_statsd_lab_checkout_queue_depth_gauge_value_average"

class RecipeTests(unittest.TestCase):
    def test_fixture_generates_exact_panel_and_scrape_config(self):
        # These are intentionally synthetic samples, not recorded proof.
        exposition = (
            f'{LAT}{{chart="statsd_lab.checkout_latency_ms_gauge"}} 25\n'
            f'{QUEUE}{{chart="statsd_lab.checkout_queue_depth_gauge"}} 2\n'
            'netdata_unrelated 7\n'
        ).encode()

        class Opener:
            def open(self, url, timeout):
                if "server=netdata-demo-inspect" not in url:
                    raise AssertionError(url)
                return io.BytesIO(exposition)

        with tempfile.TemporaryDirectory() as d:
            temp = Path(d)
            (temp / "config").mkdir()
            shutil.copy(ROOT / "configure.py", temp)
            with patch("urllib.request.build_opener", return_value=Opener()), redirect_stdout(io.StringIO()):
                runpy.run_path(str(temp / "configure.py"), run_name="__main__")
            schema = json.loads((temp / "schema.json").read_text())
            self.assertEqual((schema["latency"], schema["queue"]), (LAT, QUEUE))
            dashboard = json.loads((temp / "config/dashboard.json").read_text())
            self.assertEqual(dashboard["uid"], "netdata-checkout")
            self.assertEqual(dashboard["time"], {"from":"now-5m","to":"now"})
            self.assertEqual((dashboard["timezone"], dashboard["refresh"]), ("utc","5s"))
            self.assertEqual(
                [(x["datasource"]["uid"], x["targets"][0]["expr"], x["fieldConfig"]["defaults"]["unit"])
                 for x in dashboard["panels"]],
                [("netdata-prom", LAT, "ms"), ("netdata-prom", QUEUE, "short")],
            )
            scrape = (temp / "config/prometheus.yml").read_text()
            self.assertIn("scrape_interval: 5s", scrape)
            self.assertIn("targets: ['127.0.0.1:8199']", scrape)
            self.assertIn("server: [netdata-demo-prom]", scrape)
            self.assertIn(f"regex: '{LAT}|{QUEUE}'", scrape)
            self.assertIn("action: keep", scrape)

    def test_replay_shape_and_loopback(self):
        sent = []
        class Socket:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def sendto(self, payload, destination): sent.append((payload, destination))
        with patch("socket.socket", return_value=Socket()), patch("time.sleep"), patch.object(
            sys, "argv", ["phase.py", "baseline", "spike", "recovery"]
        ), redirect_stdout(io.StringIO()):
            runpy.run_path(str(ROOT / "phase.py"), run_name="__main__")
        self.assertEqual(len(sent), 180)
        self.assertEqual({dest for _, dest in sent}, {("127.0.0.1", 8125)})
        self.assertEqual([sent[i][0] for i in (0,60,120)], [
            b"lab.checkout_latency_ms:25|g\nlab.checkout_queue_depth:2|g",
            b"lab.checkout_latency_ms:180|g\nlab.checkout_queue_depth:32|g",
            b"lab.checkout_latency_ms:25|g\nlab.checkout_queue_depth:2|g",
        ])

    def test_bind_scope_and_digest_pins(self):
        compose = (ROOT / "compose.yaml").read_text()
        config = (ROOT / "config/netdata.conf").read_text()
        self.assertEqual(len(re.findall(r"image: docker.io/[^@]+@sha256:[a-f0-9]{64}$",compose,re.M)),3)
        self.assertNotRegex(compose,r"(?m)^\s+ports:")
        self.assertNotRegex(compose,r"(?m)^\s+privileged:")
        self.assertIn("--web.listen-address=127.0.0.1:9090",compose)
        self.assertIn("GF_SERVER_HTTP_ADDR: 127.0.0.1",compose)
        self.assertIn("bind to = 127.0.0.1:8199",config)
        self.assertIn("bind to = udp:127.0.0.1:8125",config)

if __name__ == "__main__":
    unittest.main(verbosity=2)
