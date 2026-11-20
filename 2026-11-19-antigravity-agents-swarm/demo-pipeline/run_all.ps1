[CmdletBinding()]
param(
    [string]$Region = "",
    [int]$Fps = 30,
    [string]$ModelDir = "C:\Users\superuser\Downloads\NewsLessons\tts-remote",
    [switch]$SkipDockerDown,
    [string]$Python = "python"
)

$ErrorActionPreference = 'Stop'

$RepoRoot = $PSScriptRoot
$Url = "http://127.0.0.1:8099"
$HealthUrl = "$Url/health"

function Convert-ToWslPath {
    param([Parameter(Mandatory = $true)][string]$WindowsPath)
    $resolved = (Resolve-Path -Path $WindowsPath).Path
    if ($resolved -match '^([A-Za-z]):\\(.*)$') {
        $drive = $Matches[1].ToLowerInvariant()
        $rest = $Matches[2] -replace '\\', '/'
        return "/mnt/$drive/$rest"
    }
    throw "Cannot convert path to WSL path: $WindowsPath"
}

function Escape-BashSingleQuote {
    param([Parameter(Mandatory = $true)][string]$Value)
    return $Value -replace "'", "'\\''"
}

function Assert-LastExitCode {
    param([Parameter(Mandatory = $true)][string]$StepName)
    if ($LASTEXITCODE -ne 0) {
        throw "$StepName failed with exit code $LASTEXITCODE"
    }
}

function Wait-ForHealth {
    param(
        [Parameter(Mandatory = $true)][string]$Endpoint,
        [int]$TimeoutSeconds = 30
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-WebRequest -Uri $Endpoint -UseBasicParsing -TimeoutSec 2
            if ($resp.StatusCode -eq 200) {
                return
            }
        } catch {
            # Service still starting
        }
        Start-Sleep -Milliseconds 500
    }
    throw "Timed out waiting for $Endpoint to return HTTP 200 after $TimeoutSeconds seconds."
}

Push-Location $RepoRoot
try {
    New-Item -ItemType Directory -Force -Path "out" | Out-Null

    $labWslPath = Escape-BashSingleQuote (Convert-ToWslPath (Join-Path $RepoRoot "lab"))
    $dockerStarted = $false

    try {
        # Step 1: Start lab container via WSL Docker Compose (scoped strictly to lab/)
        Write-Host "[1/6] Starting NetOps Status lab container via WSL Docker..." -ForegroundColor Cyan
        & wsl -e bash -lc "cd '$labWslPath' && docker compose up -d"
        Assert-LastExitCode "WSL docker compose up"
        $dockerStarted = $true

        Write-Host "      Waiting for $HealthUrl ..." -ForegroundColor DarkGray
        Wait-ForHealth -Endpoint $HealthUrl -TimeoutSeconds 30
        Write-Host "      Lab service is ready (HTTP 200)." -ForegroundColor Green

        # Step 2: Generate narration WAVs
        Write-Host "[2/6] Generating narration audio with Kokoro ONNX..." -ForegroundColor Cyan
        & $Python tts/narrate.py --script script.json --out-dir out/tts --model-dir $ModelDir
        Assert-LastExitCode "tts/narrate.py"

        # Clean stale recordings so we never reuse an old capture
        Remove-Item -Force -ErrorAction SilentlyContinue "out/raw.mkv", "out/pw_fallback.webm"

        # Step 3: Start screen recording
        Write-Host "[3/6] Starting ffmpeg gdigrab screen recording ($Fps fps)..." -ForegroundColor Cyan
        $recordStartArgs = @(
            "record/record.py", "start",
            "--out", "out/raw.mkv",
            "--fps", "$Fps",
            "--pid-file", "out/recorder.pid",
            "--meta-file", "out/recorder.json"
        )
        if ($Region) {
            $recordStartArgs += @("--region", $Region)
        }
        & $Python @recordStartArgs
        Assert-LastExitCode "record/record.py start"

        # Step 4: Run Playwright demo driver (always stop recorder in finally)
        Write-Host "[4/6] Running Playwright demo driver..." -ForegroundColor Cyan
        try {
            & $Python driver/drive.py `
                --url $Url `
                --out out/steps.json `
                --meta-file out/recorder.json `
                --tts-manifest out/tts/manifest.json `
                --fallback-video out/pw_fallback.webm
            Assert-LastExitCode "driver/drive.py"
        } finally {
            Write-Host "      Stopping screen recording..." -ForegroundColor DarkGray
            & $Python record/record.py stop --pid-file out/recorder.pid --meta-file out/recorder.json
            if ($LASTEXITCODE -ne 0) {
                Write-Warning "record/record.py stop exited with code $LASTEXITCODE"
            }
        }

        # Fallback to Playwright 1920x1080 recording if gdigrab produced no file (e.g. error 5 on locked desktop)
        $rawOk = (Test-Path "out/raw.mkv") -and ((Get-Item "out/raw.mkv").Length -gt 0)
        if (-not $rawOk) {
            $fallbackOk = (Test-Path "out/pw_fallback.webm") -and ((Get-Item "out/pw_fallback.webm").Length -gt 0)
            if ($fallbackOk) {
                Write-Warning "gdigrab produced no usable out/raw.mkv (see out/recorder.ffmpeg.log). Falling back to Playwright's 1920x1080 recording (out/pw_fallback.webm)."
                & ffmpeg -y -i out/pw_fallback.webm -r $Fps -c:v libx264 -preset ultrafast -crf 18 -pix_fmt yuv420p out/raw.mkv
                Assert-LastExitCode "ffmpeg fallback transcode"

                $rebaseCode = @'
import json, pathlib
p = pathlib.Path('out/steps.json')
d = json.loads(p.read_text(encoding='utf-8-sig'))
v0 = d.get('video_start_epoch')
if v0 is not None:
    d['recording_start_epoch'] = v0
    for s in d.get('steps', []):
        if 'epoch' in s:
            s['t'] = round(max(0.0, float(s['epoch']) - float(v0)), 3)
    p.write_text(json.dumps(d, indent=2) + '\n', encoding='utf-8')
'@
                $rebaseCode | & $Python -
                Assert-LastExitCode "rebase steps.json"
            } else {
                throw "Screen recording failed: out/raw.mkv is missing/empty (see out/recorder.ffmpeg.log) and out/pw_fallback.webm was not produced."
            }
        }

        # Step 5: Assemble final MP4 with loudnorm and RMS spread verification
        Write-Host "[5/6] Assembling video and narration (loudnorm + RMS verification)..." -ForegroundColor Cyan
        & $Python assemble/assemble.py --video out/raw.mkv --steps out/steps.json --tts-dir out/tts --out out/demo.mp4
        Assert-LastExitCode "assemble/assemble.py"

        # Step 6: Build HTML5 playback page
        Write-Host "[6/6] Building HTML5 player..." -ForegroundColor Cyan
        & $Python player/make_html.py --video demo.mp4 --out out/player.html
        Assert-LastExitCode "player/make_html.py"

        $demoPath = Join-Path $RepoRoot "out\demo.mp4"
        $playerPath = Join-Path $RepoRoot "out\player.html"

        Write-Host ""
        Write-Host "Demo pipeline complete!" -ForegroundColor Green
        Write-Host "  Video : $demoPath (out/demo.mp4)"
        Write-Host "  Player: $playerPath (out/player.html)"
    } finally {
        if ($dockerStarted -and -not $SkipDockerDown) {
            Write-Host "Stopping NetOps Status lab container..." -ForegroundColor DarkGray
            & wsl -e bash -lc "cd '$labWslPath' && docker compose down"
            if ($LASTEXITCODE -ne 0) {
                Write-Warning "WSL docker compose down exited with code $LASTEXITCODE"
            }
        }
    }
} finally {
    Pop-Location
}
