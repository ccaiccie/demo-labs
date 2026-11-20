import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from render import plan, sha  # noqa: E402


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.ob = (ROOT / "observed/lab-r1.json").read_bytes()
        self.src = (ROOT / "observed/lab-r1.cfg").read_bytes()
        self.want = json.loads((ROOT / "changes/lab-r1.json").read_bytes())

    def run_plan(self, wanted=None):
        return plan(self.ob, json.dumps(wanted or self.want).encode(), self.src)

    def test_change_and_exact_rollback(self):
        change, rollback, report = self.run_plan()
        self.assertIn(" description PRACTICE-LINK reviewed demo\n", change)
        self.assertIn(" description PRACTICE-LINK\n", rollback)
        self.assertEqual(change.splitlines()[0:2], ["configure terminal", "interface GigabitEthernet0/2"])
        self.assertTrue(report["changed"])
        self.assertNotIn("write", change)
        self.assertEqual(report["baseline_sha256"], sha(self.ob))

    def test_noop(self):
        self.want["description"] = "PRACTICE-LINK"
        change, rollback, report = self.run_plan()
        self.assertFalse(report["changed"])
        self.assertEqual(change, rollback)
        self.assertNotIn("configure terminal", change)

    def test_remove_description(self):
        self.want["description"] = ""
        self.assertIn(" no description\n", self.run_plan()[0])

    def test_injection_and_oversized_input(self):
        for bad in ["demo\nshutdown", "x;reload", "x\rshutdown", "x"*81, None]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                want = copy.deepcopy(self.want)
                want["description"] = bad
                self.run_plan(want)

    def test_scope_rejected(self):
        for key, bad in [("environment", "production"), ("device", "../../r2"),
                         ("interface", "GigabitEthernet0/0"), ("platform", "ios"), ("schema", True)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                want = copy.deepcopy(self.want)
                want[key] = bad
                self.run_plan(want)

    def test_unknown_key_rejected(self):
        self.want["commands"] = ["shutdown"]
        with self.assertRaises(ValueError):
            self.run_plan()

    def test_stale_baseline_rejected(self):
        self.want["baseline_sha256"] = "0"*64
        with self.assertRaises(ValueError):
            self.run_plan()

    def test_altered_source_rejected(self):
        self.src += b"router bgp 65000\n"
        with self.assertRaises(ValueError):
            self.run_plan()

    def test_normalized_evidence_must_match_source(self):
        observed = json.loads(self.ob)
        observed["description"] = "OTHER"
        self.ob = json.dumps(observed).encode()
        self.want["baseline_sha256"] = sha(self.ob)
        with self.assertRaises(ValueError):
            self.run_plan()

    def test_real_observation_rejected(self):
        observed = json.loads(self.ob)
        observed["synthetic"] = False
        self.ob = json.dumps(observed).encode()
        self.want["baseline_sha256"] = sha(self.ob)
        with self.assertRaises(ValueError):
            self.run_plan()

    def test_router_and_switch_adoption_and_proposals(self):
        for device in ("lab-r1", "lab-sw1"):
            observed = (ROOT / f"observed/{device}.json").read_bytes()
            source = (ROOT / f"observed/{device}.cfg").read_bytes()
            with self.subTest(device=device):
                baseline = (ROOT / f"desired/{device}.json").read_bytes()
                self.assertFalse(plan(observed, baseline, source)[2]["changed"])
                proposal = (ROOT / f"changes/{device}.json").read_bytes()
                change, rollback, report = plan(observed, proposal, source)
                self.assertTrue(report["changed"])
                self.assertIn(report["before"], rollback)
                self.assertIn(report["after"], change)

    def test_deterministic(self):
        self.assertEqual(self.run_plan(), self.run_plan())


if __name__ == "__main__":
    unittest.main()
