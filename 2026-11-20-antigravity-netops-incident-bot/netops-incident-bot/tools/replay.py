#!/usr/bin/env python3
"""UDP syslog log-file replayer for the NetOps incident bot."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Iterable, Iterator, Sequence
import math
from pathlib import Path
import socket
import sys
import time

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5515
DEFAULT_SPEED = 1.0
DEFAULT_BASE_DELAY = 0.05

__all__ = [
    "DEFAULT_BASE_DELAY",
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "DEFAULT_SPEED",
    "build_parser",
    "compute_delay",
    "iter_log_lines",
    "main",
    "replay_files",
]


def compute_delay(speed: float, *, base_delay: float = DEFAULT_BASE_DELAY) -> float:
    """Return the inter-line delay in seconds for the given replay speed."""
    if math.isnan(speed) or speed < 0:
        raise ValueError(f"speed must be a non-negative number, got {speed!r}")
    if math.isnan(base_delay) or base_delay < 0:
        raise ValueError(f"base_delay must be a non-negative number, got {base_delay!r}")
    if speed == 0 or math.isinf(speed) or base_delay == 0:
        return 0.0
    return base_delay / speed


def iter_log_lines(paths: Iterable[str | Path]) -> Iterator[str]:
    """Yield non-empty, non-comment lines from one or more log files."""
    for raw_path in paths:
        path = Path(raw_path)
        with path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                yield line


def replay_files(
    paths: Iterable[str | Path],
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    speed: float = DEFAULT_SPEED,
    base_delay: float = DEFAULT_BASE_DELAY,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> int:
    """Send non-empty, non-comment log lines over UDP and return the count sent."""
    if not (1 <= port <= 65535):
        raise ValueError(f"port must be between 1 and 65535, got {port!r}")
    delay = compute_delay(speed, base_delay=base_delay)

    sent = 0
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        for line in iter_log_lines(paths):
            if sent > 0 and delay > 0:
                sleep_fn(delay)
            sock.sendto(line.encode("utf-8"), (host, port))
            sent += 1
    return sent


def _non_negative_float(raw: str) -> float:
    try:
        value = float(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid float value: {raw!r}") from exc
    if math.isnan(value) or value < 0:
        raise argparse.ArgumentTypeError(f"speed must be >= 0, got {raw!r}")
    return value


def _valid_port(raw: str) -> int:
    try:
        port = int(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid port value: {raw!r}") from exc
    if not (1 <= port <= 65535):
        raise argparse.ArgumentTypeError(
            f"port must be between 1 and 65535, got {port}"
        )
    return port


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser for the syslog replayer."""
    parser = argparse.ArgumentParser(
        description="Replay syslog sample log files to the NetOps incident bot over UDP."
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="One or more syslog files to replay.",
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"Destination UDP host (default: {DEFAULT_HOST}).",
    )
    parser.add_argument(
        "--port",
        type=_valid_port,
        default=DEFAULT_PORT,
        help=f"Destination UDP port (default: {DEFAULT_PORT}).",
    )
    parser.add_argument(
        "--speed",
        type=_non_negative_float,
        default=DEFAULT_SPEED,
        help=(
            "Replay speed multiplier; delay is 0.05/speed seconds between lines, "
            f"0 means no delay (default: {DEFAULT_SPEED})."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for replaying syslog files."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        sent = replay_files(
            args.files,
            host=args.host,
            port=args.port,
            speed=args.speed,
        )
    except OSError as exc:
        print(f"Error replaying logs: {exc}", file=sys.stderr)
        return 1

    unit = "event" if sent == 1 else "events"
    print(f"Replayed {sent} {unit} from {len(args.files)} file(s) to {args.host}:{args.port}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
