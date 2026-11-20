"""Offline, allowlisted Cisco IOSv interface-description plan. No transport/deploy code."""
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def description(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9 ._:/-]{0,80}", value):
        raise ValueError("Description must be 0..80 safe ASCII characters")
    return value


def command(value):
    return " description " + value if value else " no description"


def plan(observed_bytes, desired_bytes, source_bytes):
    observed, desired = json.loads(observed_bytes), json.loads(desired_bytes)
    obs_keys = {"schema", "synthetic", "environment", "device", "platform",
                "interface", "description", "source_sha256"}
    desired_keys = {"schema", "environment", "device", "platform", "interface",
                    "description", "baseline_sha256"}
    if set(observed) != obs_keys or set(desired) != desired_keys:
        raise ValueError("Unknown or missing fields")
    device = observed.get("device")
    platforms = {"lab-r1": "iosv", "lab-sw1": "iosvl2"}
    if device not in platforms:
        raise ValueError("Device outside allowlist")
    for key, expected in {"schema": 1, "environment": "lab", "device": device,
                          "platform": platforms[device], "interface": "GigabitEthernet0/2"}.items():
        if type(observed[key]) is not type(expected) or observed[key] != expected:
            raise ValueError("Observed scope is outside the demo allowlist")
        if type(desired[key]) is not type(expected) or desired[key] != expected:
            raise ValueError("Desired scope is outside the demo allowlist")
    if observed["synthetic"] is not True:
        raise ValueError("This starter accepts synthetic fixtures only")
    if desired["baseline_sha256"] != sha(observed_bytes):
        raise ValueError("Stale or changed observed baseline; review required")
    if observed["source_sha256"] != sha(source_bytes):
        raise ValueError("Observed source hash mismatch")
    before, after = description(observed["description"]), description(desired["description"])
    # Exact fixture-format check: do not pretend to parse arbitrary device configs.
    expected_source = (
        f"! SYNTHETIC SANITIZED {'Cisco IOSv' if device == 'lab-r1' else 'Cisco IOSv-L2'} EXCERPT; not collected from a device\n"
        f"hostname {device}\n!\ninterface GigabitEthernet0/2\n" + command(before) + "\n!\n"
    ).encode()
    if source_bytes != expected_source:
        raise ValueError("Source excerpt does not match normalized fixture")
    changed = before != after

    def cli(value):
        if not changed:
            return "! No change required\n"
        return "configure terminal\ninterface GigabitEthernet0/2\n" + command(value) + "\nexit\nend\n"

    report = {"mode": "offline-review-only", "device": device, "interface": "GigabitEthernet0/2",
              "changed": changed, "before": before, "after": after,
              "baseline_sha256": sha(observed_bytes),
              "intent_sha256": sha(desired_bytes),
              "warning": "No device contacted. No change authorized or executed."}
    return cli(after), cli(before), report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate only; write nothing")
    parser.add_argument("--change", action="store_true", help="Render reviewed proposal instead of no-op adopted intent")
    args = parser.parse_args()
    for device in ("lab-r1", "lab-sw1"):
        change, rollback, report = plan(
            (ROOT / f"observed/{device}.json").read_bytes(),
            (ROOT / ("changes" if args.change else "desired") / f"{device}.json").read_bytes(),
            (ROOT / f"observed/{device}.cfg").read_bytes())
        if not args.check:
            output = ROOT / "build" / ("proposal" if args.change else "adoption") / device
            output.mkdir(parents=True, exist_ok=True)
            (output / "change.cli").write_text(change)
            (output / "rollback.cli").write_text(rollback)
            (output / "review.json").write_text(json.dumps(report, indent=2) + "\n")
        print(f"Validated offline plan: {device} description only; changed={report['changed']}; no deployment")


if __name__ == "__main__":
    main()
