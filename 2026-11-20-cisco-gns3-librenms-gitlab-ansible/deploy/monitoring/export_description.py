#!/usr/bin/env python3
"""Export one lab description from private Cisco IOS 'show interfaces description' text.

Offline input only; stdout contains only an exact allowlisted value and fixed
identifiers. Never calls a device, reads Oxidized history, or writes to Git.
"""
import argparse
import json
import re
import sys

PORT = re.compile(
    r"^(?:GigabitEthernet|Gi)0/2[ \t]+"
    r"(?:up|down|admin down)[ \t]+(?:up|down)(?:[ \t]+(.*?))?[ \t]*$"
)
DESCRIPTIONS = {
    "lab-r1": ("PRACTICE-LINK", "PRACTICE-LINK reviewed demo"),
    "lab-sw1": ("PRACTICE-SWITCH", "PRACTICE-SWITCH reviewed demo"),
}


def export(device: str, text: str) -> dict[str, str | int]:
    if device not in DESCRIPTIONS:
        raise ValueError("device outside the restricted lab")
    port_rows = [row for row in text.splitlines()
                 if re.match(r"^(?:GigabitEthernet|Gi)0/2(?:[ \t]|$)", row)]
    if len(port_rows) != 1:
        raise ValueError("expected exactly one selected practice-port row")
    match = PORT.fullmatch(port_rows[0])
    if not match or match[1] not in DESCRIPTIONS[device]:
        raise ValueError("no usable allowlisted description on this practice port")
    return {"schema": 1, "device": device, "interface": "GigabitEthernet0/2",
            "description": match[1]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("device", choices=DESCRIPTIONS)
    args = parser.parse_args()
    source = sys.stdin.read(131_073)
    if len(source) > 131_072:
        raise SystemExit("input exceeds 128 KiB")
    try:
        print(json.dumps(export(args.device, source), indent=2))
    except ValueError as exc:
        raise SystemExit(str(exc)) from None


if __name__ == "__main__":
    main()
