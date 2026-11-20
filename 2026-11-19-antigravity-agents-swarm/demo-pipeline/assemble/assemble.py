#!/usr/bin/env python3
"""Assemble narration WAVs onto recorded video, apply loudnorm, and verify speech RMS spread.

Places each step's narration WAV at its timestamp from steps.json, prevents
narration overlaps by shifting later clips with a warning, applies two-pass
ffmpeg loudnorm (with single-pass fallback), muxes to MP4, and verifies that
the per-minute active-speech RMS spread is within --max-rms-spread dB.
"""

from __future__ import annotations

import argparse
import array
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import numpy as np  # type: ignore
except ImportError:  # pragma: no cover - stdlib fallback
    np = None  # type: ignore


SAMPLE_RATE = 48000
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit signed PCM
OVERLAP_GAP_SEC = 0.15
TAIL_PAD_SEC = 0.5
FRAME_MS = 30.0
SPEECH_THRESHOLD_DBFS = -45.0


@dataclass
class PlacedClip:
    step_id: str
    requested_t: float
    actual_t: float
    duration_sec: float
    wav_path: Path
    shifted: bool


@dataclass
class MinuteBucketResult:
    minute_index: int
    start_sec: float
    end_sec: float
    active_speech_sec: float
    rms_dbfs: float | None


@dataclass
class RmsVerificationResult:
    buckets: list[MinuteBucketResult]
    active_bucket_count: int
    spread_db: float
    max_rms_spread: float
    passed: bool


def _run_cmd(cmd: list[str], capture_output: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE if capture_output else None,
        stderr=subprocess.PIPE if capture_output else None,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _find_ffprobe(ffmpeg_bin: str) -> str | None:
    ffmpeg_path = Path(ffmpeg_bin)
    if ffmpeg_path.parent != Path("."):
        for name in ("ffprobe.exe", "ffprobe"):
            candidate = ffmpeg_path.parent / name
            if candidate.is_file():
                return str(candidate)
    return shutil.which("ffprobe")


def probe_video_duration(video_path: Path, ffmpeg_bin: str) -> float:
    """Return video duration in seconds using ffprobe or ffmpeg stderr fallback."""
    ffprobe = _find_ffprobe(ffmpeg_bin)
    if ffprobe:
        proc = _run_cmd(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ]
        )
        if proc.returncode == 0 and proc.stdout.strip():
            try:
                val = float(proc.stdout.strip())
                if math.isfinite(val) and val > 0:
                    return val
            except ValueError:
                pass

    proc = _run_cmd([ffmpeg_bin, "-hide_banner", "-i", str(video_path)])
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", proc.stderr or "")
    if match:
        hours, minutes, seconds = int(match.group(1)), int(match.group(2)), float(match.group(3))
        return hours * 3600.0 + minutes * 60.0 + seconds

    raise RuntimeError(f"Could not determine duration of video: {video_path}")


def load_steps(steps_path: Path) -> list[dict[str, Any]]:
    with steps_path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict) and isinstance(data.get("steps"), list):
        steps = data["steps"]
    elif isinstance(data, list):
        steps = data
    else:
        raise ValueError(f"Invalid steps.json schema in {steps_path}: expected object with 'steps' list")

    normalized: list[dict[str, Any]] = []
    for idx, item in enumerate(steps):
        if not isinstance(item, dict) or "id" not in item or "t" not in item:
            raise ValueError(f"Step #{idx} in {steps_path} must contain 'id' and 't'")
        t_val = float(item["t"])
        if t_val < 0:
            print(f"[assemble] WARNING: step '{item['id']}' has negative t={t_val:.3f}s; clamping to 0.000s")
            t_val = 0.0
        normalized.append({"id": str(item["id"]), "t": t_val, "raw": item})

    normalized.sort(key=lambda s: s["t"])
    return normalized


def decode_audio_to_pcm16(audio_path: Path, ffmpeg_bin: str, sample_rate: int = SAMPLE_RATE) -> bytes:
    """Decode any audio/video file to mono 16-bit signed little-endian PCM bytes."""
    proc = subprocess.run(
        [
            ffmpeg_bin,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(audio_path),
            "-vn",
            "-ac",
            str(CHANNELS),
            "-ar",
            str(sample_rate),
            "-f",
            "s16le",
            "-acodec",
            "pcm_s16le",
            "-",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"ffmpeg failed decoding {audio_path}: {err}")
    return proc.stdout


def extract_mono_wav(media_path: Path, out_wav: Path, ffmpeg_bin: str, sample_rate: int = SAMPLE_RATE) -> None:
    """Extract the audio track from media_path to a mono 16-bit PCM WAV file."""
    proc = _run_cmd(
        [
            ffmpeg_bin,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(media_path),
            "-vn",
            "-ac",
            str(CHANNELS),
            "-ar",
            str(sample_rate),
            "-c:a",
            "pcm_s16le",
            str(out_wav),
        ]
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed extracting audio from {media_path}: {proc.stderr.strip()}")


def build_narration_timeline(
    steps: list[dict[str, Any]],
    tts_dir: Path,
    video_duration: float,
    out_wav: Path,
    ffmpeg_bin: str,
    sample_rate: int = SAMPLE_RATE,
) -> tuple[list[PlacedClip], float]:
    """Assemble step WAVs onto a single mono PCM16 timeline WAV without overlaps."""
    decoded_clips: list[tuple[PlacedClip, bytes]] = []
    prev_end_sec = 0.0

    for step in steps:
        step_id = step["id"]
        req_t = step["t"]
        wav_path = tts_dir / f"{step_id}.wav"
        if not wav_path.is_file():
            print(f"[assemble] WARNING: missing TTS clip for step '{step_id}': {wav_path} (skipping)")
            continue

        pcm_bytes = decode_audio_to_pcm16(wav_path, ffmpeg_bin=ffmpeg_bin, sample_rate=sample_rate)
        num_samples = len(pcm_bytes) // SAMPLE_WIDTH
        if num_samples == 0:
            print(f"[assemble] WARNING: empty TTS clip for step '{step_id}': {wav_path} (skipping)")
            continue

        dur_sec = num_samples / float(sample_rate)
        actual_t = req_t
        shifted = False
        if decoded_clips and actual_t < prev_end_sec:
            actual_t = round(prev_end_sec + OVERLAP_GAP_SEC, 3)
            shifted = True
            print(
                f"[assemble] WARNING: step '{step_id}' at t={req_t:.3f}s overlaps previous clip "
                f"(ends {prev_end_sec:.3f}s); shifting to {actual_t:.3f}s"
            )

        clip = PlacedClip(
            step_id=step_id,
            requested_t=req_t,
            actual_t=actual_t,
            duration_sec=dur_sec,
            wav_path=wav_path,
            shifted=shifted,
        )
        decoded_clips.append((clip, pcm_bytes))
        prev_end_sec = actual_t + dur_sec

    if not decoded_clips:
        raise RuntimeError(f"No narration WAV files matched steps in {tts_dir}")

    audio_end_sec = prev_end_sec + TAIL_PAD_SEC if prev_end_sec > video_duration else video_duration
    total_duration_sec = max(video_duration, audio_end_sec)
    total_samples = int(math.ceil(total_duration_sec * sample_rate))
    timeline = bytearray(total_samples * SAMPLE_WIDTH)

    for clip, pcm_bytes in decoded_clips:
        start_sample = int(round(clip.actual_t * sample_rate))
        start_byte = start_sample * SAMPLE_WIDTH
        end_byte = start_byte + len(pcm_bytes)
        if end_byte > len(timeline):
            timeline.extend(b"\x00" * (end_byte - len(timeline)))
        timeline[start_byte:end_byte] = pcm_bytes

    final_duration_sec = (len(timeline) // SAMPLE_WIDTH) / float(sample_rate)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_wav), "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(sample_rate)
        wf.writeframes(timeline)

    return [c for c, _ in decoded_clips], final_duration_sec


def measure_loudnorm_pass1(timeline_wav: Path, target_i: float, ffmpeg_bin: str) -> dict[str, float] | None:
    """Run loudnorm pass 1 and parse measured loudness statistics from ffmpeg stderr."""
    loudnorm_filter = f"loudnorm=I={target_i}:TP=-1.5:LRA=11:print_format=json"
    proc = _run_cmd(
        [
            ffmpeg_bin,
            "-hide_banner",
            "-i",
            str(timeline_wav),
            "-af",
            loudnorm_filter,
            "-f",
            "null",
            "-",
        ]
    )
    if proc.returncode != 0:
        return None

    # Find the last JSON object emitted by loudnorm in stderr.
    matches = re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", proc.stderr or "", flags=re.DOTALL)
    if not matches:
        return None

    try:
        raw = json.loads(matches[-1])
        stats = {
            "input_i": float(raw["input_i"]),
            "input_tp": float(raw["input_tp"]),
            "input_lra": float(raw["input_lra"]),
            "input_thresh": float(raw["input_thresh"]),
            "target_offset": float(raw["target_offset"]),
        }
    except (ValueError, KeyError, TypeError):
        return None

    if not all(math.isfinite(v) for v in stats.values()):
        return None
    return stats


def mux_video_and_audio(
    video_path: Path,
    timeline_wav: Path,
    out_mp4: Path,
    video_duration: float,
    audio_duration: float,
    target_i: float,
    ffmpeg_bin: str,
) -> str:
    """Apply two-pass (or single-pass fallback) loudnorm and mux with video to MP4."""
    stats = measure_loudnorm_pass1(timeline_wav, target_i=target_i, ffmpeg_bin=ffmpeg_bin)
    if stats is not None:
        loudnorm_mode = "two-pass"
        af = (
            f"loudnorm=I={target_i}:TP=-1.5:LRA=11:"
            f"measured_I={stats['input_i']}:measured_TP={stats['input_tp']}:"
            f"measured_LRA={stats['input_lra']}:measured_thresh={stats['input_thresh']}:"
            f"offset={stats['target_offset']}:linear=true:print_format=summary,"
            f"aresample={SAMPLE_RATE}"
        )
    else:
        loudnorm_mode = "single-pass fallback"
        print("[assemble] WARNING: loudnorm pass 1 stats unavailable; falling back to single-pass loudnorm")
        af = f"loudnorm=I={target_i}:TP=-1.5:LRA=11,aresample={SAMPLE_RATE}"

    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg_bin,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video_path),
        "-i",
        str(timeline_wav),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
    ]

    pad_sec = audio_duration - video_duration
    if pad_sec > 0.05:
        cmd.extend(["-vf", f"tpad=stop_mode=clone:stop_duration={pad_sec:.3f}"])

    cmd.extend(
        [
            "-af",
            af,
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(out_mp4),
        ]
    )

    proc = _run_cmd(cmd)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg mux/loudnorm failed: {proc.stderr.strip()}")
    return loudnorm_mode


def read_mono_pcm16_wav(wav_path: Path) -> tuple[Any, int]:
    """Read a mono 16-bit PCM WAV file and return (float samples in [-1, 1], sample_rate)."""
    with wave.open(str(wav_path), "rb") as wf:
        if wf.getnchannels() != 1 or wf.getsampwidth() != 2:
            raise ValueError(f"Expected mono 16-bit PCM WAV, got {wf.getnchannels()}ch {wf.getsampwidth()*8}bit")
        sr = wf.getframerate()
        raw = wf.readframes(wf.getnframes())

    if np is not None:
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768.0
        return samples, sr

    arr = array.array("h")
    arr.frombytes(raw)
    if sys.byteorder != "little":
        arr.byteswap()
    return [x / 32768.0 for x in arr], sr


def compute_per_minute_speech_rms(
    samples: Any,
    sample_rate: int,
    max_rms_spread: float = 1.5,
    bucket_sec: float = 60.0,
    frame_ms: float = FRAME_MS,
    threshold_dbfs: float = SPEECH_THRESHOLD_DBFS,
) -> RmsVerificationResult:
    """Partition mono float samples [-1, 1] into 60s buckets and measure active speech RMS spread."""
    total_samples = len(samples)
    if total_samples == 0:
        return RmsVerificationResult(
            buckets=[],
            active_bucket_count=0,
            spread_db=float("inf"),
            max_rms_spread=max_rms_spread,
            passed=False,
        )

    bucket_samples = max(1, int(round(bucket_sec * sample_rate)))
    frame_samples = max(1, int(round(sample_rate * frame_ms / 1000.0)))
    threshold_ms = 10.0 ** (threshold_dbfs / 10.0)
    num_buckets = int(math.ceil(total_samples / float(bucket_samples)))

    buckets: list[MinuteBucketResult] = []
    active_rms_values: list[float] = []

    use_numpy = np is not None and isinstance(samples, np.ndarray)

    for b_idx in range(num_buckets):
        start_idx = b_idx * bucket_samples
        end_idx = min(total_samples, (b_idx + 1) * bucket_samples)
        chunk = samples[start_idx:end_idx]
        n_frames = len(chunk) // frame_samples

        if n_frames == 0:
            buckets.append(
                MinuteBucketResult(
                    minute_index=b_idx,
                    start_sec=start_idx / float(sample_rate),
                    end_sec=end_idx / float(sample_rate),
                    active_speech_sec=0.0,
                    rms_dbfs=None,
                )
            )
            continue

        if use_numpy:
            framed = chunk[: n_frames * frame_samples].reshape(n_frames, frame_samples)
            frame_ms_vals = np.mean(framed * framed, axis=1)
            active_mask = frame_ms_vals >= threshold_ms
            active_count = int(np.sum(active_mask))
            if active_count > 0:
                speech_ms = float(np.mean(frame_ms_vals[active_mask]))
                rms_dbfs: float | None = 10.0 * math.log10(max(speech_ms, 1e-12))
            else:
                rms_dbfs = None
        else:
            active_ms_sum = 0.0
            active_count = 0
            for f_idx in range(n_frames):
                f_start = f_idx * frame_samples
                f_end = f_start + frame_samples
                frame_slice = chunk[f_start:f_end]
                ms = sum(x * x for x in frame_slice) / float(frame_samples)
                if ms >= threshold_ms:
                    active_ms_sum += ms
                    active_count += 1
            if active_count > 0:
                rms_dbfs = 10.0 * math.log10(max(active_ms_sum / active_count, 1e-12))
            else:
                rms_dbfs = None

        active_sec = active_count * (frame_samples / float(sample_rate))
        if rms_dbfs is not None:
            active_rms_values.append(rms_dbfs)

        buckets.append(
            MinuteBucketResult(
                minute_index=b_idx,
                start_sec=start_idx / float(sample_rate),
                end_sec=end_idx / float(sample_rate),
                active_speech_sec=active_sec,
                rms_dbfs=rms_dbfs,
            )
        )

    active_bucket_count = len(active_rms_values)
    if active_bucket_count == 0:
        spread_db = float("inf")
        passed = False
    elif active_bucket_count == 1:
        spread_db = 0.0
        passed = spread_db <= max_rms_spread
    else:
        spread_db = max(active_rms_values) - min(active_rms_values)
        passed = spread_db <= max_rms_spread

    return RmsVerificationResult(
        buckets=buckets,
        active_bucket_count=active_bucket_count,
        spread_db=spread_db,
        max_rms_spread=max_rms_spread,
        passed=passed,
    )


def print_rms_report(result: RmsVerificationResult) -> None:
    print("\nPer-Minute Speech RMS Report")
    print("=" * 58)
    print(f"{'Minute':<10} {'Window (s)':<16} {'Active (s)':>11} {'Speech RMS':>14}")
    print("-" * 58)
    for b in result.buckets:
        window_str = f"[{b.start_sec:5.1f}, {b.end_sec:5.1f})"
        rms_str = f"{b.rms_dbfs:8.2f} dBFS" if b.rms_dbfs is not None else "    (silence)"
        print(f"min {b.minute_index:<6} {window_str:<16} {b.active_speech_sec:10.2f}s {rms_str:>14}")
    print("-" * 58)
    if result.active_bucket_count == 0:
        print("Speech RMS spread : N/A (no active speech detected)")
        print("Verification      : FAIL")
    else:
        note = " (single active minute)" if result.active_bucket_count == 1 else ""
        status = "PASS" if result.passed else "FAIL"
        print(
            f"Speech RMS spread : {result.spread_db:.2f} dB "
            f"(limit <= {result.max_rms_spread:.2f} dB){note}"
        )
        print(f"Verification      : {status}")
    print("=" * 58)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Assemble narration WAVs onto recorded video with ffmpeg loudnorm and verify per-minute speech RMS spread."
    )
    parser.add_argument("--video", default="out/raw.mkv", help="Input recorded video path (default: out/raw.mkv)")
    parser.add_argument("--steps", default="out/steps.json", help="Input steps JSON path (default: out/steps.json)")
    parser.add_argument("--tts-dir", default="out/tts", help="Directory containing <step_id>.wav clips (default: out/tts)")
    parser.add_argument("--out", default="out/demo.mp4", help="Output MP4 path (default: out/demo.mp4)")
    parser.add_argument(
        "--max-rms-spread",
        type=float,
        default=1.5,
        help="Maximum allowed per-minute speech RMS spread in dB (default: 1.5)",
    )
    parser.add_argument(
        "--target-i",
        type=float,
        default=-16.0,
        help="Target integrated loudness in LUFS for ffmpeg loudnorm (default: -16.0)",
    )
    parser.add_argument("--ffmpeg", default="ffmpeg", help="Path to ffmpeg executable (default: ffmpeg)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    video_path = Path(args.video)
    steps_path = Path(args.steps)
    tts_dir = Path(args.tts_dir)
    out_mp4 = Path(args.out)

    if not video_path.is_file():
        print(f"[assemble] ERROR: video file not found: {video_path}", file=sys.stderr)
        return 1
    if not steps_path.is_file():
        print(f"[assemble] ERROR: steps file not found: {steps_path}", file=sys.stderr)
        return 1
    if not tts_dir.is_dir():
        print(f"[assemble] ERROR: TTS directory not found: {tts_dir}", file=sys.stderr)
        return 1

    steps = load_steps(steps_path)
    video_duration = probe_video_duration(video_path, ffmpeg_bin=args.ffmpeg)
    print(f"[assemble] Video: {video_path} ({video_duration:.2f}s), steps: {len(steps)}")

    with tempfile.TemporaryDirectory(prefix="assemble_") as tmp:
        tmp_dir = Path(tmp)
        timeline_wav = tmp_dir / "timeline.wav"
        extracted_wav = tmp_dir / "final_audio.wav"

        placed_clips, audio_duration = build_narration_timeline(
            steps=steps,
            tts_dir=tts_dir,
            video_duration=video_duration,
            out_wav=timeline_wav,
            ffmpeg_bin=args.ffmpeg,
        )
        print(f"[assemble] Placed {len(placed_clips)} narration clips (timeline duration: {audio_duration:.2f}s)")
        for clip in placed_clips:
            shift_note = f" (shifted from {clip.requested_t:.2f}s)" if clip.shifted else ""
            print(
                f"  - {clip.step_id}: start={clip.actual_t:.2f}s, "
                f"dur={clip.duration_sec:.2f}s, end={clip.actual_t + clip.duration_sec:.2f}s{shift_note}"
            )

        loudnorm_mode = mux_video_and_audio(
            video_path=video_path,
            timeline_wav=timeline_wav,
            out_mp4=out_mp4,
            video_duration=video_duration,
            audio_duration=audio_duration,
            target_i=args.target_i,
            ffmpeg_bin=args.ffmpeg,
        )
        print(f"[assemble] Muxed {out_mp4} (loudnorm: {loudnorm_mode}, target I={args.target_i:.1f} LUFS)")

        extract_mono_wav(out_mp4, extracted_wav, ffmpeg_bin=args.ffmpeg)
        samples, sr = read_mono_pcm16_wav(extracted_wav)
        result = compute_per_minute_speech_rms(
            samples,
            sample_rate=sr,
            max_rms_spread=args.max_rms_spread,
        )
        print_rms_report(result)

    return 0 if result.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
