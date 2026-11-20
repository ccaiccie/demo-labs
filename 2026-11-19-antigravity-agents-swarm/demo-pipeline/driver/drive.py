#!/usr/bin/env python3
"""Playwright driver for the NetOps Status demo pipeline.

Drives the NetOps Status web app in headed Chromium at 1920x1080 and writes
timestamped demo steps to a JSON file for downstream narration/video assembly.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import Locator, Page, sync_playwright

DEFAULT_URL = "http://127.0.0.1:8099"
DEFAULT_OUT = "out/steps.json"
DEFAULT_TIMEOUT_MS = 15_000
TTS_PADDING_SEC = 0.8
VIEWPORT = {"width": 1920, "height": 1080}


def load_tts_durations(manifest_path: str | Path | None) -> dict[str, float]:
    """Load per-step clip durations (in seconds) from a TTS manifest JSON."""
    if manifest_path is None:
        return {}

    path = Path(manifest_path)
    if not path.is_file():
        print(
            f"[driver] Warning: TTS manifest {path} does not exist; using default step holds.",
            file=sys.stderr,
        )
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(
            f"[driver] Warning: failed to read TTS manifest {path} ({exc}); "
            "using default step holds.",
            file=sys.stderr,
        )
        return {}

    durations: dict[str, float] = {}
    items: list[Any] | None = None
    if isinstance(data, dict) and isinstance(data.get("clips"), list):
        items = data["clips"]
    elif isinstance(data, list):
        items = data

    if items is not None:
        for item in items:
            if isinstance(item, dict) and "id" in item and item.get("duration_sec") is not None:
                try:
                    durations[str(item["id"])] = float(item["duration_sec"])
                except (ValueError, TypeError):
                    continue
    elif isinstance(data, dict):
        for key, val in data.items():
            if isinstance(val, dict) and val.get("duration_sec") is not None:
                try:
                    durations[str(key)] = float(val["duration_sec"])
                except (ValueError, TypeError):
                    continue
            elif isinstance(val, (int, float)):
                durations[str(key)] = float(val)

    return durations


def compute_step_hold(
    step_id: str,
    default_hold: float,
    clip_durations: dict[str, float],
    padding_sec: float = TTS_PADDING_SEC,
) -> float:
    """Return how long to hold a step so its narration clip finishes cleanly."""
    clip_dur = clip_durations.get(step_id)
    if clip_dur is not None and clip_dur > 0:
        return max(default_hold, clip_dur + padding_sec)
    return default_hold


def resolve_start_epoch(
    start_epoch: float | None,
    meta_file: str | Path | None,
    fallback_epoch: float,
) -> float:
    """Determine recording_start_epoch from CLI args, meta file, or fallback.

    Precedence:
      1. Explicit --start-epoch float value.
      2. recording_start_epoch field in --meta-file JSON (if provided and valid).
      3. Script start epoch (fallback_epoch).
    """
    if start_epoch is not None:
        return round(float(start_epoch), 3)

    if meta_file is not None:
        meta_path = Path(meta_file)
        if meta_path.is_file():
            try:
                data = json.loads(meta_path.read_text(encoding="utf-8"))
                if "recording_start_epoch" in data and data["recording_start_epoch"] is not None:
                    return round(float(data["recording_start_epoch"]), 3)
                print(
                    f"[driver] Warning: 'recording_start_epoch' not found in {meta_path}; "
                    "using script start epoch.",
                    file=sys.stderr,
                )
            except (OSError, ValueError, TypeError) as exc:
                print(
                    f"[driver] Warning: failed to read {meta_path} ({exc}); "
                    "using script start epoch.",
                    file=sys.stderr,
                )
        else:
            print(
                f"[driver] Warning: meta file {meta_path} does not exist; "
                "using script start epoch.",
                file=sys.stderr,
            )

    return round(float(fallback_epoch), 3)


def _locate_health_check_button(page: Page, timeout_ms: int) -> Locator:
    """Return the Run health check button locator, preferring #run-health-check."""
    primary = page.locator("#run-health-check")
    fallback = page.get_by_role("button", name="Run health check")
    primary.or_(fallback).first.wait_for(state="visible", timeout=timeout_ms)
    if primary.count() > 0:
        return primary.first
    return fallback.first


def _sleep_remaining(step_started_at: float, target_seconds: float) -> None:
    """Sleep the remaining time so a step lasts at least target_seconds."""
    remaining = target_seconds - (time.time() - step_started_at)
    if remaining > 0:
        time.sleep(remaining)


def run_demo(
    url: str = DEFAULT_URL,
    out_path: str | Path = DEFAULT_OUT,
    start_epoch: float | None = None,
    meta_file: str | Path | None = None,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    fallback_video: str | Path | None = None,
    tts_manifest: str | Path | None = None,
) -> dict[str, Any]:
    """Run the NetOps Status Playwright demo and write steps.json."""
    script_start = time.time()
    recording_start_epoch = resolve_start_epoch(start_epoch, meta_file, script_start)
    clip_durations = load_tts_durations(tts_manifest)
    steps: list[dict[str, Any]] = []

    fallback_path = Path(fallback_video) if fallback_video is not None else None
    video_tmp_dir: Path | None = None
    video_start_epoch: float | None = None
    recorded_video = None

    if fallback_path is not None:
        fallback_path.parent.mkdir(parents=True, exist_ok=True)
        video_tmp_dir = Path(
            tempfile.mkdtemp(prefix=".pw_video_", dir=str(fallback_path.parent))
        )

    def log_step(step_id: str, description: str) -> float:
        epoch = round(time.time(), 3)
        t = round(epoch - recording_start_epoch, 3)
        entry = {
            "id": step_id,
            "t": t,
            "epoch": epoch,
            "description": description,
        }
        steps.append(entry)
        print(f"[driver] step={step_id} t={t:.3f}s — {description}", flush=True)
        return epoch

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,
                args=[
                    f"--window-size={VIEWPORT['width']},{VIEWPORT['height']}",
                    "--window-position=0,0",
                ],
            )
            context = None
            try:
                context_kwargs: dict[str, Any] = {"viewport": VIEWPORT}
                if video_tmp_dir is not None:
                    context_kwargs["record_video_dir"] = str(video_tmp_dir)
                    context_kwargs["record_video_size"] = VIEWPORT
                context = browser.new_context(**context_kwargs)
                page = context.new_page()
                if fallback_path is not None:
                    video_start_epoch = round(time.time(), 3)
                    recorded_video = page.video

                # Step 1: intro — open dashboard, wait for networkidle + table + button
                page.goto(url, wait_until="networkidle", timeout=timeout_ms)
                table = page.locator("table").first
                table.wait_for(state="visible", timeout=timeout_ms)
                health_btn = _locate_health_check_button(page, timeout_ms)

                step_t0 = log_step(
                    "intro",
                    "Opened the NetOps Status dashboard showing the device inventory table and controls.",
                )
                _sleep_remaining(step_t0, compute_step_hold("intro", 4.5, clip_durations))

                # Step 2: inspect_table — smoothly scroll/hover over the device table
                step_t0 = log_step(
                    "inspect_table",
                    "Inspecting the network device status table, hostnames, IP addresses, and latency.",
                )
                table.evaluate("el => el.scrollIntoView({ behavior: 'smooth', block: 'center' })")
                rows = table.locator("tbody tr")
                if rows.count() == 0:
                    rows = table.locator("tr")
                row_count = min(rows.count(), 6)
                for idx in range(row_count):
                    row = rows.nth(idx)
                    row.scroll_into_view_if_needed(timeout=timeout_ms)
                    row.hover(timeout=timeout_ms)
                    time.sleep(0.45)
                _sleep_remaining(
                    step_t0, compute_step_hold("inspect_table", 4.5, clip_durations)
                )

                # Step 3: run_health_check — click button and wait for #health-results
                health_btn.scroll_into_view_if_needed(timeout=timeout_ms)
                health_btn.hover(timeout=timeout_ms)
                time.sleep(0.25)
                health_btn.click(timeout=timeout_ms)
                step_t0 = log_step(
                    "run_health_check",
                    "Triggered the live health check across all monitored network devices.",
                )

                results_el = page.locator("#health-results")
                results_el.wait_for(state="visible", timeout=timeout_ms)
                page.wait_for_function(
                    """() => {
                        const el = document.querySelector('#health-results');
                        if (!el) return false;
                        const style = window.getComputedStyle(el);
                        if (style.display === 'none' || style.visibility === 'hidden') return false;
                        const text = (el.innerText || el.textContent || '').trim();
                        return text.length > 0 && !/^(loading|running)/i.test(text);
                    }""",
                    timeout=timeout_ms,
                )
                _sleep_remaining(
                    step_t0, compute_step_hold("run_health_check", 4.5, clip_durations)
                )

                # Step 4: results — scroll/focus #health-results so results are clearly visible
                results_el.evaluate(
                    "el => el.scrollIntoView({ behavior: 'smooth', block: 'center' })"
                )
                results_el.hover(timeout=timeout_ms)
                step_t0 = log_step(
                    "results",
                    "Reviewing the completed health check summary and per-device diagnostics.",
                )
                _sleep_remaining(step_t0, compute_step_hold("results", 5.0, clip_durations))
            finally:
                if context is not None:
                    context.close()
                if fallback_path is not None and recorded_video is not None:
                    raw_video_path = Path(recorded_video.path())
                    if raw_video_path.is_file():
                        fallback_path.parent.mkdir(parents=True, exist_ok=True)
                        if fallback_path.exists():
                            fallback_path.unlink()
                        shutil.move(str(raw_video_path), str(fallback_path))
                        print(f"[driver] Saved fallback video to {fallback_path}", flush=True)
                browser.close()
    finally:
        if video_tmp_dir is not None and video_tmp_dir.exists():
            shutil.rmtree(video_tmp_dir, ignore_errors=True)

    payload: dict[str, Any] = {
        "recording_start_epoch": recording_start_epoch,
        "url": url,
        "steps": steps,
    }
    if video_start_epoch is not None:
        payload["video_start_epoch"] = video_start_epoch

    destination = Path(out_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"[driver] Wrote {len(steps)} steps to {destination}", flush=True)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Drive the NetOps Status web app with Playwright and record step timestamps."
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help=f"Target NetOps Status URL (default: {DEFAULT_URL})",
    )
    parser.add_argument(
        "--out",
        default=DEFAULT_OUT,
        help=f"Output path for steps JSON (default: {DEFAULT_OUT})",
    )
    parser.add_argument(
        "--start-epoch",
        type=float,
        default=None,
        help=(
            "Optional recording start epoch (float seconds). "
            "If omitted, falls back to --meta-file or script start time."
        ),
    )
    parser.add_argument(
        "--meta-file",
        default=None,
        help=(
            "Optional path to recorder metadata JSON (e.g. out/recorder.json) "
            "containing recording_start_epoch."
        ),
    )
    parser.add_argument(
        "--fallback-video",
        default=None,
        help=(
            "Optional output path (e.g. out/pw_fallback.webm) to record a 1920x1080 "
            "Playwright fallback video and write video_start_epoch into steps.json."
        ),
    )
    parser.add_argument(
        "--tts-manifest",
        default=None,
        help=(
            "Optional path to TTS manifest JSON (e.g. out/tts/manifest.json); "
            "each step holds at least max(default_hold, clip_duration_sec + 0.8)s."
        ),
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=DEFAULT_TIMEOUT_MS,
        help=f"Playwright wait timeout in milliseconds (default: {DEFAULT_TIMEOUT_MS})",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    run_demo(
        url=args.url,
        out_path=args.out,
        start_epoch=args.start_epoch,
        meta_file=args.meta_file,
        timeout_ms=args.timeout_ms,
        fallback_video=args.fallback_video,
        tts_manifest=args.tts_manifest,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
