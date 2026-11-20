---
name: make-demo
description: >-
  Builds the demo video by running `.\run_all.ps1 -SkipDockerDown` and verifies
  the Per-Minute Speech RMS report and spoken-text pronunciation in
  `out/tts/manifest.json`. Use this skill when the user asks to build, render,
  or regenerate the demo video.
---

# Make Demo

Run the demo-video pipeline and validate the resulting audio loudness and TTS pronunciation.

## Steps

1. **Run the pipeline**:
   Execute from the repository root:
   ```powershell
   .\run_all.ps1 -SkipDockerDown
   ```

2. **Check the Per-Minute Speech RMS report**:
   - Inspect the Per-Minute Speech RMS report emitted by the pipeline.
   - Verify that per-minute speech RMS stays within `1.5 dB` across the video.
   - If any minute exceeds the `1.5 dB` tolerance, flag the offending segment(s).

3. **Check pronunciation in `out/tts/manifest.json`**:
   - Open `out/tts/manifest.json` and review the spoken text entries.
   - Confirm `IP` is spelled as `eye pee` and present-tense `read` is spelled as `reed`.
   - Confirm narration uses the Kokoro `am_michael` voice.
   - Report any pronunciation or voice mismatches found.
