# Narrated Demo-Video Pipeline

End-to-end automated pipeline for recording a narrated software demo on Windows: spins up a containerized web app in WSL Docker, generates neural TTS narration with pronunciation rules, captures a 1080p screen recording while driving the browser with Playwright, assembles and loudness-normalizes the final MP4 with per-minute speech RMS verification, and outputs a self-contained HTML5 player.

## Architecture

| Component | Path | Responsibility |
| --- | --- | --- |
| **1. Lab App** | `lab/` | Containerized Flask **NetOps Status** dashboard (`127.0.0.1:8099`) with a device status table, `#run-health-check` action, `/api/health-check`, and `/health` readiness endpoint. |
| **2. Browser Driver** | `driver/drive.py` | Headed Playwright Chromium automation (`1920x1080`) that walks through the demo steps (`intro`, `inspect_table`, `run_health_check`, `results`) and logs timestamps to `out/steps.json`. |
| **3. Screen Recorder** | `record/record.py` | Reusable Windows `ffmpeg` (`gdigrab`) recorder supporting start/stop CLI subcommands, configurable FPS/region, clean MKV finalization, and `recording_start_epoch` metadata. |
| **4. TTS Narration** | `tts/narrate.py` | Kokoro ONNX (`kokoro_onnx`, voice `am_michael`) narrator that converts `script.json` into per-step WAV clips with pronunciation rules (`IP` -> `eye pee`, present-tense `read` -> `reed`). |
| **5. Video Assembler** | `assemble/assemble.py` | Aligns narration WAVs to step timestamps over `out/raw.mkv`, applies `ffmpeg` `loudnorm`, muxes `out/demo.mp4`, and verifies per-minute speech RMS spread is `<= 1.5 dB`. |
| **6. HTML5 Player** | `player/make_html.py` | Generates a self-contained dark-mode `out/player.html` with `1x`, `1.5x`, and `2x` playback speed controls and keyboard shortcuts. |
| **Orchestrator** | `run_all.ps1` + `script.json` | Single-command Windows PowerShell runner chaining all 6 stages end to end. |

## Prerequisites

- **Windows 10/11** with PowerShell and **WSL2 + Docker Compose** (`wsl -e bash -lc 'docker compose version'`).
- **Python 3.10+** on Windows with pip.
- **ffmpeg** available on `PATH` (for `gdigrab` screen capture, `loudnorm`, and muxing).
- **Kokoro ONNX model & voices** directory (default: `C:\Users\superuser\Downloads\NewsLessons\tts-remote`, containing the `.onnx` model and voices `.bin`/`.json`).

Install Python dependencies and Playwright Chromium:

```powershell
pip install -r requirements.txt
playwright install chromium
```

## Quickstart

Run the full pipeline from the repository root:

```powershell
./run_all.ps1
```

Outputs:
- `out/demo.mp4` — assembled, loudness-normalized narrated demo video
- `out/player.html` — self-contained HTML5 player (`1x` / `1.5x` / `2x` speed controls)

### `run_all.ps1` Parameters

| Parameter | Default | Description |
| --- | --- | --- |
| `-Region` | `""` (full desktop) | Optional capture region `X,Y,W,H` (e.g. `0,0,1920,1080`). |
| `-Fps` | `30` | Screen recording frame rate. |
| `-ModelDir` | `C:\Users\superuser\Downloads\NewsLessons\tts-remote` | Path to Kokoro ONNX model & voices directory. |
| `-SkipDockerDown` | `$false` | Keep the `lab/` container running after the pipeline finishes. |
| `-Python` | `python` | Python executable path (e.g. `.venv\Scripts\python.exe`). |

Example with a custom 1080p capture region and keeping the lab container up:

```powershell
./run_all.ps1 -Region 0,0,1920,1080 -Fps 30 -SkipDockerDown
```

## Individual Component CLI Usage

### 1. Lab Container (`lab/`)
```powershell
wsl -e bash -lc 'cd /mnt/c/Users/superuser/ag-lab/demo-pipeline/lab && docker compose up -d'
# Health check: http://127.0.0.1:8099/health
# Tear down:
wsl -e bash -lc 'cd /mnt/c/Users/superuser/ag-lab/demo-pipeline/lab && docker compose down'
```

### 2. TTS Narration (`tts/narrate.py`)
```powershell
python tts/narrate.py --script script.json --out-dir out/tts --model-dir C:\Users\superuser\Downloads\NewsLessons\tts-remote
# Preview pronunciation rules without loading ONNX:
python tts/narrate.py --script script.json --dry-run
```

### 3. Screen Recorder (`record/record.py`)
```powershell
python record/record.py start --out out/raw.mkv --fps 30 --pid-file out/recorder.pid --meta-file out/recorder.json
# Optional region: --region 0,0,1920,1080
python record/record.py stop --pid-file out/recorder.pid --meta-file out/recorder.json
```

### 4. Playwright Driver (`driver/drive.py`)
```powershell
python driver/drive.py --url http://127.0.0.1:8099 --out out/steps.json --meta-file out/recorder.json
```

### 5. Video Assembler (`assemble/assemble.py`)
```powershell
python assemble/assemble.py --video out/raw.mkv --steps out/steps.json --tts-dir out/tts --out out/demo.mp4
```

### 6. HTML5 Player (`player/make_html.py`)
```powershell
python player/make_html.py --video demo.mp4 --out out/player.html --title "NetOps Status Demo"
```

## Reusing This Pipeline for Another Demo

1. **Swap the target app**: Replace `lab/` (or point `driver/drive.py --url` at any running web app).
2. **Define your demo steps**: Update `driver/drive.py` with your Playwright actions and log each step ID + timestamp to `out/steps.json`.
3. **Write your narration**: Edit `script.json` so each entry's `id` matches a step ID emitted by `driver/drive.py`. Adjust `voice` or `speed` globally or per line.
4. **Run**: Execute `./run_all.ps1` (or run individual components) to produce a freshly recorded, loudness-normalized MP4 and HTML5 player.
