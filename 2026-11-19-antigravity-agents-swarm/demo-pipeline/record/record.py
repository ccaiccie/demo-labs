"""Reusable Windows screen recorder wrapper around ffmpeg gdigrab.

Provides:
- ``ScreenRecorder``: in-process controller (``start()``, ``stop()``, context manager).
- CLI subcommands:
    python record/record.py start --out out/raw.mkv --fps 30 [--region X,Y,W,H]
                                  [--pid-file out/recorder.pid]
                                  [--meta-file out/recorder.json]
                                  [--ffmpeg ffmpeg]
    python record/record.py stop  [--pid-file out/recorder.pid]
                                  [--meta-file out/recorder.json]

Clean shutdown across separate CLI invocations on Windows:
``start`` spawns a detached helper process (``python record/record.py _run ...``)
that owns the ``ffmpeg`` subprocess with ``stdin=PIPE`` and polls a stop-sentinel
file (default: ``<pid-file>.stop``). When ``stop`` creates the sentinel file, the
helper writes ``b"q\\n"`` to ffmpeg's stdin so ffmpeg flushes and finalizes the
MKV container cleanly instead of being killed via TerminateProcess.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, IO, NamedTuple

DEFAULT_OUT = "out/raw.mkv"
DEFAULT_FPS = 30
DEFAULT_PID_FILE = "out/recorder.pid"
DEFAULT_META_FILE = "out/recorder.json"
DEFAULT_FFMPEG = "ffmpeg"
DEFAULT_STOP_TIMEOUT = 15.0
DEFAULT_STARTUP_TIMEOUT = 10.0


class Region(NamedTuple):
    """Screen capture region (x, y, width, height) in pixels."""

    x: int
    y: int
    width: int
    height: int

    def as_list(self) -> list[int]:
        return [self.x, self.y, self.width, self.height]

    def as_arg(self) -> str:
        return f"{self.x},{self.y},{self.width},{self.height}"


def parse_region(value: str | Region | tuple[int, int, int, int] | None) -> Region | None:
    """Parse a capture region from ``'X,Y,W,H'`` or a 4-int tuple.

    ``x`` and ``y`` may be negative (multi-monitor setups); ``width`` and
    ``height`` must be strictly positive integers.
    """
    if value is None:
        return None
    if isinstance(value, Region):
        region = value
    elif isinstance(value, tuple):
        if len(value) != 4:
            raise ValueError(f"Region tuple must have 4 integers (X,Y,W,H), got {value!r}")
        if not all(isinstance(v, int) and not isinstance(v, bool) for v in value):
            raise ValueError(f"Region values must be integers, got {value!r}")
        region = Region(*value)
    elif isinstance(value, str):
        parts = [p.strip() for p in value.split(",")]
        if len(parts) != 4:
            raise ValueError(
                f"Invalid region {value!r}: expected 'X,Y,W,H' (4 comma-separated integers)"
            )
        try:
            x, y, w, h = (int(p) for p in parts)
        except ValueError as exc:
            raise ValueError(
                f"Invalid region {value!r}: all four values must be integers"
            ) from exc
        region = Region(x, y, w, h)
    else:
        raise ValueError(f"Unsupported region type: {type(value).__name__}")

    if region.width <= 0 or region.height <= 0:
        raise ValueError(
            f"Invalid region {region}: width and height must be positive integers"
        )
    return region


def _format_fps(fps: int | float) -> str:
    if isinstance(fps, bool) or not isinstance(fps, (int, float)) or fps <= 0:
        raise ValueError(f"fps must be a positive number, got {fps!r}")
    if isinstance(fps, float) and fps.is_integer():
        return str(int(fps))
    return str(fps)


def build_ffmpeg_command(
    out: str | Path,
    fps: int | float = DEFAULT_FPS,
    region: str | Region | tuple[int, int, int, int] | None = None,
    ffmpeg: str = DEFAULT_FFMPEG,
    crf: int = 18,
    preset: str = "ultrafast",
) -> list[str]:
    """Build the ffmpeg command line for Windows ``gdigrab`` MKV capture."""
    fps_str = _format_fps(fps)
    parsed_region = parse_region(region)

    cmd: list[str] = [
        str(ffmpeg),
        "-y",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-f",
        "gdigrab",
        "-framerate",
        fps_str,
    ]

    if parsed_region is not None:
        cmd.extend(
            [
                "-offset_x",
                str(parsed_region.x),
                "-offset_y",
                str(parsed_region.y),
                "-video_size",
                f"{parsed_region.width}x{parsed_region.height}",
            ]
        )

    cmd.extend(
        [
            "-i",
            "desktop",
            "-c:v",
            "libx264",
            "-preset",
            str(preset),
            "-crf",
            str(crf),
            "-pix_fmt",
            "yuv420p",
            str(out),
        ]
    )
    return cmd


def default_stop_file(pid_file: str | Path) -> Path:
    """Derive the stop-sentinel file path from a pid file path."""
    p = Path(pid_file)
    return p.with_suffix(".stop")


def default_log_file(meta_file: str | Path | None, out: str | Path) -> Path:
    """Derive a default ffmpeg stderr log path."""
    if meta_file is not None:
        return Path(meta_file).with_suffix(".ffmpeg.log")
    return Path(out).with_suffix(".ffmpeg.log")


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    os.replace(tmp_path, path)


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    _atomic_write_text(path, json.dumps(data, indent=2) + "\n")


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def is_pid_alive(pid: int) -> bool:
    """Return True if a process with the given PID is currently running."""
    if pid <= 0:
        return False
    if os.name == "nt":
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        ERROR_ACCESS_DENIED = 5
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not handle:
            return kernel32.GetLastError() == ERROR_ACCESS_DENIED
        try:
            exit_code = ctypes.c_ulong()
            if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)) == 0:
                return False
            return exit_code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def _terminate_pid(pid: int) -> None:
    """Best-effort forced termination of a PID (fallback only)."""
    if pid <= 0 or not is_pid_alive(pid):
        return
    if os.name == "nt":
        PROCESS_TERMINATE = 0x0001
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_TERMINATE, False, int(pid))
        if handle:
            try:
                kernel32.TerminateProcess(handle, 1)
            finally:
                kernel32.CloseHandle(handle)
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass


def _read_tail(path: Path, max_chars: int = 1000) -> str:
    try:
        content = path.read_text(encoding="utf-8", errors="replace").strip()
        if len(content) > max_chars:
            return "..." + content[-max_chars:]
        return content
    except OSError:
        return ""


class ScreenRecorder:
    """In-process screen recorder wrapping ffmpeg ``gdigrab``.

    Supports direct ``start()`` / ``stop()`` calls and use as a context manager::

        with ScreenRecorder(out="out/raw.mkv", fps=30) as rec:
            ...
    """

    def __init__(
        self,
        out: str | Path = DEFAULT_OUT,
        fps: int | float = DEFAULT_FPS,
        region: str | Region | tuple[int, int, int, int] | None = None,
        ffmpeg: str = DEFAULT_FFMPEG,
        pid_file: str | Path | None = None,
        meta_file: str | Path | None = None,
        stop_file: str | Path | None = None,
        log_file: str | Path | None = None,
        crf: int = 18,
        preset: str = "ultrafast",
        startup_check_delay: float = 0.2,
    ) -> None:
        self.out = Path(out)
        self.fps = fps
        self.region = parse_region(region)
        self.ffmpeg = str(ffmpeg)
        self.pid_file = Path(pid_file) if pid_file is not None else None
        self.meta_file = Path(meta_file) if meta_file is not None else None
        self.stop_file = (
            Path(stop_file)
            if stop_file is not None
            else (default_stop_file(self.pid_file) if self.pid_file is not None else None)
        )
        self.log_file = (
            Path(log_file)
            if log_file is not None
            else default_log_file(self.meta_file, self.out)
        )
        self.crf = crf
        self.preset = preset
        self.startup_check_delay = startup_check_delay

        self._proc: subprocess.Popen[bytes] | None = None
        self._log_handle: IO[bytes] | None = None
        self.recording_start_epoch: float | None = None
        self.recording_stop_epoch: float | None = None
        self.metadata: dict[str, Any] = {}

    def build_command(self) -> list[str]:
        """Return the ffmpeg argument list for this recorder."""
        return build_ffmpeg_command(
            out=self.out,
            fps=self.fps,
            region=self.region,
            ffmpeg=self.ffmpeg,
            crf=self.crf,
            preset=self.preset,
        )

    def is_running(self) -> bool:
        """Return True if the managed ffmpeg subprocess is still running."""
        return self._proc is not None and self._proc.poll() is None

    def start(self) -> dict[str, Any]:
        """Start ffmpeg recording and write metadata/pid files if configured."""
        if self.is_running():
            raise RuntimeError("ScreenRecorder is already running")

        self.out.parent.mkdir(parents=True, exist_ok=True)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        cmd = self.build_command()
        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        self._log_handle = self.log_file.open("wb")
        try:
            self.recording_start_epoch = time.time()
            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=self._log_handle,
                creationflags=creationflags,
            )
        except Exception:
            self._close_log()
            self._proc = None
            raise

        if self.startup_check_delay > 0:
            time.sleep(self.startup_check_delay)

        rc = self._proc.poll()
        if rc is not None:
            self._close_log()
            tail = _read_tail(self.log_file)
            self._proc = None
            detail = f": {tail}" if tail else ""
            raise RuntimeError(f"ffmpeg exited immediately with code {rc}{detail}")

        self.metadata = {
            "pid": os.getpid(),
            "ffmpeg_pid": self._proc.pid,
            "recording_start_epoch": self.recording_start_epoch,
            "out": str(self.out),
            "fps": self.fps,
            "region": self.region.as_list() if self.region is not None else None,
            "pid_file": str(self.pid_file) if self.pid_file is not None else None,
            "stop_file": str(self.stop_file) if self.stop_file is not None else None,
            "log_file": str(self.log_file),
            "command": cmd,
            "status": "recording",
        }

        if self.meta_file is not None:
            _atomic_write_json(self.meta_file, self.metadata)
        if self.pid_file is not None:
            _atomic_write_text(self.pid_file, f"{os.getpid()}\n")

        return dict(self.metadata)

    def stop(self, timeout: float = DEFAULT_STOP_TIMEOUT) -> int | None:
        """Stop ffmpeg cleanly by sending ``q\\n`` to stdin so MKV is finalized."""
        proc = self._proc
        returncode: int | None = None

        if proc is not None:
            if proc.poll() is None:
                if proc.stdin is not None:
                    try:
                        proc.stdin.write(b"q\n")
                        proc.stdin.flush()
                    except OSError:
                        pass
                    try:
                        proc.stdin.close()
                    except OSError:
                        pass

                try:
                    returncode = proc.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    proc.terminate()
                    try:
                        returncode = proc.wait(timeout=5.0)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        returncode = proc.wait(timeout=5.0)
            else:
                returncode = proc.returncode
                if proc.stdin is not None:
                    try:
                        proc.stdin.close()
                    except OSError:
                        pass

            self._proc = None

        self._close_log()
        self.recording_stop_epoch = time.time()

        if self.metadata:
            self.metadata["status"] = "stopped"
            self.metadata["recording_stop_epoch"] = self.recording_stop_epoch
            self.metadata["ffmpeg_returncode"] = returncode
            if self.meta_file is not None:
                _atomic_write_json(self.meta_file, self.metadata)

        if self.stop_file is not None:
            self.stop_file.unlink(missing_ok=True)
        if self.pid_file is not None:
            self.pid_file.unlink(missing_ok=True)

        return returncode

    def _close_log(self) -> None:
        if self._log_handle is not None:
            try:
                self._log_handle.close()
            except OSError:
                pass
            self._log_handle = None

    def __enter__(self) -> ScreenRecorder:
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.stop()


def _run_daemon(args: argparse.Namespace) -> int:
    """Internal helper loop: owns ffmpeg and watches the stop-sentinel file."""
    stop_file = Path(args.stop_file)
    pid_file = Path(args.pid_file)
    meta_file = Path(args.meta_file)

    stop_requested = False

    def _handle_signal(_signum: int, _frame: Any) -> None:
        nonlocal stop_requested
        stop_requested = True

    signal.signal(signal.SIGINT, _handle_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_signal)

    recorder = ScreenRecorder(
        out=args.out,
        fps=args.fps,
        region=args.region,
        ffmpeg=args.ffmpeg,
        pid_file=pid_file,
        meta_file=meta_file,
        stop_file=stop_file,
    )

    try:
        recorder.start()
    except Exception as exc:
        _atomic_write_json(
            meta_file,
            {
                "pid": os.getpid(),
                "status": "error",
                "error": str(exc),
                "out": str(args.out),
                "stop_file": str(stop_file),
            },
        )
        return 1

    try:
        while recorder.is_running() and not stop_requested and not stop_file.exists():
            time.sleep(0.05)
    finally:
        recorder.stop(timeout=args.stop_timeout)

    return 0


def _cmd_start(args: argparse.Namespace) -> int:
    """CLI handler for ``record.py start``."""
    # Validate inputs upfront before spawning the detached helper.
    _format_fps(args.fps)
    region = parse_region(args.region)

    if shutil.which(args.ffmpeg) is None and not Path(args.ffmpeg).is_file():
        print(f"Error: ffmpeg executable not found: {args.ffmpeg}", file=sys.stderr)
        return 1

    out_path = Path(args.out)
    pid_file = Path(args.pid_file)
    meta_file = Path(args.meta_file)
    stop_file = Path(args.stop_file) if args.stop_file else default_stop_file(pid_file)

    # Guard against clobbering an already-running recording.
    if pid_file.exists():
        try:
            existing_pid = int(pid_file.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            existing_pid = -1
        if existing_pid > 0 and is_pid_alive(existing_pid):
            print(
                f"Error: recorder appears to already be running (pid {existing_pid}, {pid_file})",
                file=sys.stderr,
            )
            return 1
        pid_file.unlink(missing_ok=True)

    # Clear any stale sentinel/meta files from prior runs.
    stop_file.unlink(missing_ok=True)
    meta_file.unlink(missing_ok=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    meta_file.parent.mkdir(parents=True, exist_ok=True)

    helper_cmd: list[str] = [
        sys.executable,
        str(Path(__file__).resolve()),
        "_run",
        "--out",
        str(out_path),
        "--fps",
        _format_fps(args.fps),
        "--pid-file",
        str(pid_file),
        "--meta-file",
        str(meta_file),
        "--stop-file",
        str(stop_file),
        "--ffmpeg",
        str(args.ffmpeg),
        "--stop-timeout",
        str(args.stop_timeout),
    ]
    if region is not None:
        helper_cmd.extend(["--region", region.as_arg()])

    popen_kwargs: dict[str, Any] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = (
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
    else:
        popen_kwargs["start_new_session"] = True

    helper = subprocess.Popen(helper_cmd, **popen_kwargs)

    deadline = time.monotonic() + args.startup_timeout
    while time.monotonic() < deadline:
        meta = _read_json(meta_file)
        if meta is not None:
            if meta.get("status") == "error":
                print(
                    f"Error: recorder failed to start: {meta.get('error', 'unknown error')}",
                    file=sys.stderr,
                )
                return 1
            if meta.get("status") == "recording" and pid_file.exists():
                print(
                    f"Recording started: out={meta['out']} pid={meta['pid']} "
                    f"ffmpeg_pid={meta['ffmpeg_pid']} "
                    f"recording_start_epoch={meta['recording_start_epoch']:.3f}"
                )
                return 0
        if helper.poll() is not None:
            meta = _read_json(meta_file)
            err = meta.get("error") if meta else f"helper exited with code {helper.returncode}"
            print(f"Error: recorder helper failed to start: {err}", file=sys.stderr)
            return 1
        time.sleep(0.05)

    print(
        f"Error: timed out after {args.startup_timeout}s waiting for recorder to start",
        file=sys.stderr,
    )
    _terminate_pid(helper.pid)
    return 1


def _cmd_stop(args: argparse.Namespace) -> int:
    """CLI handler for ``record.py stop``."""
    pid_file = Path(args.pid_file)
    meta_file = Path(args.meta_file)

    meta = _read_json(meta_file)
    pid: int | None = None
    ffmpeg_pid: int | None = None
    stop_file: Path = default_stop_file(pid_file)
    out_path: Path | None = None

    if meta is not None:
        if isinstance(meta.get("pid"), int):
            pid = meta["pid"]
        if isinstance(meta.get("ffmpeg_pid"), int):
            ffmpeg_pid = meta["ffmpeg_pid"]
        if meta.get("stop_file"):
            stop_file = Path(meta["stop_file"])
        if meta.get("out"):
            out_path = Path(meta["out"])

    if pid_file.exists():
        try:
            pid = int(pid_file.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            pass

    if pid is None and meta is None:
        print(
            f"Error: no active recorder found (missing {pid_file} and {meta_file})",
            file=sys.stderr,
        )
        return 1

    if pid is not None and not is_pid_alive(pid):
        pid_file.unlink(missing_ok=True)
        stop_file.unlink(missing_ok=True)
        if meta is not None and meta.get("status") == "stopped":
            print(f"Recorder already stopped: out={meta.get('out')}")
            return 0
        print(f"Recorder process {pid} is not running; cleaned up stale pid file.")
        return 0

    # Signal the helper daemon to send 'q\n' to ffmpeg's stdin.
    stop_file.parent.mkdir(parents=True, exist_ok=True)
    stop_file.write_text(f"{time.time()}\n", encoding="utf-8")

    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        helper_alive = pid is not None and is_pid_alive(pid)
        ff_alive = ffmpeg_pid is not None and is_pid_alive(ffmpeg_pid)
        if not helper_alive and not ff_alive and not pid_file.exists():
            break
        time.sleep(0.05)

    # Fallback forced cleanup if graceful shutdown timed out.
    timed_out = False
    if pid is not None and is_pid_alive(pid):
        timed_out = True
        _terminate_pid(pid)
    if ffmpeg_pid is not None and is_pid_alive(ffmpeg_pid):
        timed_out = True
        _terminate_pid(ffmpeg_pid)

    pid_file.unlink(missing_ok=True)
    stop_file.unlink(missing_ok=True)

    size_info = ""
    if out_path is not None and out_path.exists():
        size_info = f" size={out_path.stat().st_size} bytes"

    if timed_out:
        print(
            f"Warning: recorder did not stop within {args.timeout}s and was terminated"
            f" (out={out_path}{size_info})",
            file=sys.stderr,
        )
        return 1

    print(f"Recording stopped cleanly: out={out_path}{size_info}")
    return 0


def _parse_fps_arg(value: str) -> int | float:
    try:
        f = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid fps {value!r}: expected a number") from exc
    if f <= 0:
        raise argparse.ArgumentTypeError(f"Invalid fps {value!r}: must be > 0")
    return int(f) if f.is_integer() else f


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="record.py",
        description="Windows ffmpeg gdigrab screen recorder with clean start/stop.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="{start,stop}")

    start_p = subparsers.add_parser(
        "start",
        help="Start screen recording in a detached background helper.",
    )
    start_p.add_argument("--out", default=DEFAULT_OUT, help=f"Output MKV path (default: {DEFAULT_OUT})")
    start_p.add_argument("--fps", type=_parse_fps_arg, default=DEFAULT_FPS, help=f"Capture FPS (default: {DEFAULT_FPS})")
    start_p.add_argument(
        "--region",
        default=None,
        help="Optional capture region as X,Y,W,H (e.g. 0,0,1920,1080)",
    )
    start_p.add_argument(
        "--pid-file",
        default=DEFAULT_PID_FILE,
        help=f"PID file path (default: {DEFAULT_PID_FILE})",
    )
    start_p.add_argument(
        "--meta-file",
        default=DEFAULT_META_FILE,
        help=f"Metadata JSON path (default: {DEFAULT_META_FILE})",
    )
    start_p.add_argument(
        "--stop-file",
        default=None,
        help="Optional stop-sentinel file path (default: <pid-file>.stop)",
    )
    start_p.add_argument(
        "--ffmpeg",
        default=DEFAULT_FFMPEG,
        help=f"Path to ffmpeg executable (default: {DEFAULT_FFMPEG})",
    )
    start_p.add_argument(
        "--startup-timeout",
        type=float,
        default=DEFAULT_STARTUP_TIMEOUT,
        help=f"Seconds to wait for ffmpeg startup (default: {DEFAULT_STARTUP_TIMEOUT})",
    )
    start_p.add_argument(
        "--stop-timeout",
        type=float,
        default=DEFAULT_STOP_TIMEOUT,
        help=f"Graceful shutdown timeout for ffmpeg in seconds (default: {DEFAULT_STOP_TIMEOUT})",
    )
    start_p.set_defaults(func=_cmd_start)

    stop_p = subparsers.add_parser(
        "stop",
        help="Stop an active recording cleanly so the MKV file is finalized.",
    )
    stop_p.add_argument(
        "--pid-file",
        default=DEFAULT_PID_FILE,
        help=f"PID file path (default: {DEFAULT_PID_FILE})",
    )
    stop_p.add_argument(
        "--meta-file",
        default=DEFAULT_META_FILE,
        help=f"Metadata JSON path (default: {DEFAULT_META_FILE})",
    )
    stop_p.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_STOP_TIMEOUT,
        help=f"Seconds to wait for clean MKV finalization (default: {DEFAULT_STOP_TIMEOUT})",
    )
    stop_p.set_defaults(func=_cmd_stop)

    # Internal detached helper subcommand (omitted from top-level help listing).
    run_p = subparsers.add_parser("_run")
    run_p.add_argument("--out", required=True)
    run_p.add_argument("--fps", type=_parse_fps_arg, default=DEFAULT_FPS)
    run_p.add_argument("--region", default=None)
    run_p.add_argument("--pid-file", required=True)
    run_p.add_argument("--meta-file", required=True)
    run_p.add_argument("--stop-file", required=True)
    run_p.add_argument("--ffmpeg", default=DEFAULT_FFMPEG)
    run_p.add_argument("--stop-timeout", type=float, default=DEFAULT_STOP_TIMEOUT)
    run_p.set_defaults(func=_run_daemon)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
