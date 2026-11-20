"""Unit tests for record/record.py."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

_RECORD_PY = Path(__file__).resolve().parent / "record.py"
_SPEC = importlib.util.spec_from_file_location("record_mod", _RECORD_PY)
assert _SPEC is not None and _SPEC.loader is not None
record = importlib.util.module_from_spec(_SPEC)
sys.modules["record_mod"] = record
_SPEC.loader.exec_module(record)


def _make_mock_ffmpeg(tmp_dir: Path) -> Path:
    """Create a tiny cross-platform mock ffmpeg executable that waits for 'q' on stdin."""
    script = tmp_dir / "mock_ffmpeg.py"
    script.write_text(
        textwrap.dedent(
            """\
            import sys
            from pathlib import Path

            out_path = Path(sys.argv[-1])
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(b"MKV_HEADER\\n")

            data = sys.stdin.read()
            if "q" in data:
                with out_path.open("ab") as fh:
                    fh.write(b"MKV_FINALIZED\\n")
                sys.exit(0)
            sys.exit(2)
            """
        ),
        encoding="utf-8",
    )

    if os.name == "nt":
        wrapper = tmp_dir / "mock_ffmpeg.cmd"
        wrapper.write_text(f'@"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")
        return wrapper

    wrapper = tmp_dir / "mock_ffmpeg.sh"
    wrapper.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
    wrapper.chmod(0o755)
    return wrapper


class TestRegionParsing(unittest.TestCase):
    def test_none(self) -> None:
        self.assertIsNone(record.parse_region(None))

    def test_valid_string(self) -> None:
        self.assertEqual(record.parse_region("0,0,1920,1080"), record.Region(0, 0, 1920, 1080))
        self.assertEqual(
            record.parse_region(" -1920, 100 , 1280 , 720 "),
            record.Region(-1920, 100, 1280, 720),
        )

    def test_valid_tuple_and_region(self) -> None:
        r = record.Region(10, 20, 800, 600)
        self.assertEqual(record.parse_region((10, 20, 800, 600)), r)
        self.assertEqual(record.parse_region(r), r)

    def test_invalid_regions(self) -> None:
        for bad in ("0,0,1920", "0,0,1920,1080,5", "a,b,c,d", "0,0,0,1080", "0,0,1920,-10"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    record.parse_region(bad)


class TestBuildCommand(unittest.TestCase):
    def test_full_desktop_command(self) -> None:
        cmd = record.build_ffmpeg_command(out="out/raw.mkv", fps=30)
        self.assertEqual(cmd[0], "ffmpeg")
        self.assertIn("-f", cmd)
        self.assertEqual(cmd[cmd.index("-f") + 1], "gdigrab")
        self.assertEqual(cmd[cmd.index("-framerate") + 1], "30")
        self.assertEqual(cmd[cmd.index("-i") + 1], "desktop")
        self.assertNotIn("-offset_x", cmd)
        self.assertNotIn("-offset_y", cmd)
        self.assertNotIn("-video_size", cmd)
        self.assertEqual(cmd[cmd.index("-c:v") + 1], "libx264")
        self.assertEqual(cmd[cmd.index("-preset") + 1], "ultrafast")
        self.assertEqual(cmd[cmd.index("-crf") + 1], "18")
        self.assertEqual(cmd[cmd.index("-pix_fmt") + 1], "yuv420p")
        self.assertEqual(cmd[-1], "out/raw.mkv")

    def test_region_options_precede_input(self) -> None:
        cmd = record.build_ffmpeg_command(
            out="out/region.mkv",
            fps=60,
            region="100,200,1280,720",
            ffmpeg="C:/tools/ffmpeg.exe",
        )
        self.assertEqual(cmd[0], "C:/tools/ffmpeg.exe")
        idx_input = cmd.index("-i")
        idx_ox = cmd.index("-offset_x")
        idx_oy = cmd.index("-offset_y")
        idx_vs = cmd.index("-video_size")
        self.assertLess(idx_ox, idx_input)
        self.assertLess(idx_oy, idx_input)
        self.assertLess(idx_vs, idx_input)
        self.assertEqual(cmd[idx_ox + 1], "100")
        self.assertEqual(cmd[idx_oy + 1], "200")
        self.assertEqual(cmd[idx_vs + 1], "1280x720")
        self.assertEqual(cmd[idx_input + 1], "desktop")
        self.assertEqual(cmd[-1], "out/region.mkv")

    def test_invalid_fps(self) -> None:
        with self.assertRaises(ValueError):
            record.build_ffmpeg_command(out="out/raw.mkv", fps=0)
        with self.assertRaises(ValueError):
            record.build_ffmpeg_command(out="out/raw.mkv", fps=-30)


class TestCLIHelp(unittest.TestCase):
    def test_help_outputs(self) -> None:
        script = str(Path(__file__).resolve().parent / "record.py")
        for args in (["--help"], ["start", "--help"], ["stop", "--help"]):
            with self.subTest(args=args):
                res = subprocess.run(
                    [sys.executable, script, *args],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(res.returncode, 0, msg=res.stderr)
                self.assertTrue(res.stdout.strip())


class TestRecorderLifecycle(unittest.TestCase):
    def test_context_manager_clean_stop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            mock_ffmpeg = _make_mock_ffmpeg(tmp_dir)
            out_file = tmp_dir / "raw.mkv"
            meta_file = tmp_dir / "recorder.json"
            pid_file = tmp_dir / "recorder.pid"

            with record.ScreenRecorder(
                out=out_file,
                fps=30,
                region="0,0,1920,1080",
                ffmpeg=str(mock_ffmpeg),
                pid_file=pid_file,
                meta_file=meta_file,
                startup_check_delay=0.1,
            ) as rec:
                self.assertTrue(rec.is_running())
                self.assertIsNotNone(rec.recording_start_epoch)
                self.assertTrue(pid_file.exists())
                self.assertTrue(meta_file.exists())
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                self.assertEqual(meta["status"], "recording")
                self.assertAlmostEqual(meta["recording_start_epoch"], rec.recording_start_epoch, places=3)

            self.assertFalse(rec.is_running())
            self.assertFalse(pid_file.exists())
            meta_after = json.loads(meta_file.read_text(encoding="utf-8"))
            self.assertEqual(meta_after["status"], "stopped")
            self.assertEqual(meta_after["ffmpeg_returncode"], 0)
            self.assertIn(b"MKV_FINALIZED", out_file.read_bytes())

    def test_detached_cli_start_and_stop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            mock_ffmpeg = _make_mock_ffmpeg(tmp_dir)
            script = str(Path(__file__).resolve().parent / "record.py")
            out_file = tmp_dir / "raw.mkv"
            pid_file = tmp_dir / "recorder.pid"
            meta_file = tmp_dir / "recorder.json"

            start_res = subprocess.run(
                [
                    sys.executable,
                    script,
                    "start",
                    "--out",
                    str(out_file),
                    "--fps",
                    "30",
                    "--region",
                    "0,0,1920,1080",
                    "--pid-file",
                    str(pid_file),
                    "--meta-file",
                    str(meta_file),
                    "--ffmpeg",
                    str(mock_ffmpeg),
                ],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            self.assertEqual(start_res.returncode, 0, msg=f"stdout={start_res.stdout}\nstderr={start_res.stderr}")
            self.assertTrue(pid_file.exists())
            self.assertTrue(meta_file.exists())

            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            self.assertEqual(meta["status"], "recording")
            self.assertIsInstance(meta["pid"], int)
            self.assertIsInstance(meta["ffmpeg_pid"], int)
            self.assertIsInstance(meta["recording_start_epoch"], float)
            self.assertEqual(meta["out"], str(out_file))
            self.assertTrue(meta["stop_file"])

            stop_res = subprocess.run(
                [
                    sys.executable,
                    script,
                    "stop",
                    "--pid-file",
                    str(pid_file),
                    "--meta-file",
                    str(meta_file),
                ],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            self.assertEqual(stop_res.returncode, 0, msg=f"stdout={stop_res.stdout}\nstderr={stop_res.stderr}")
            self.assertFalse(pid_file.exists())
            self.assertFalse(Path(meta["stop_file"]).exists())

            meta_after = json.loads(meta_file.read_text(encoding="utf-8"))
            self.assertEqual(meta_after["status"], "stopped")
            self.assertEqual(meta_after["recording_start_epoch"], meta["recording_start_epoch"])
            self.assertEqual(meta_after["ffmpeg_returncode"], 0)
            self.assertIn(b"MKV_FINALIZED", out_file.read_bytes())


if __name__ == "__main__":
    unittest.main()
