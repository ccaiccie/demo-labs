# Download the official agent-desktop C library (v1.3.1, Windows x64) and verify SHA-256.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$dest = Join-Path $root "ffi"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
$name = "agent-desktop-ffi-v1.3.1-x86_64-pc-windows-msvc.zip"
$url = "https://github.com/vercel-labs/agent-desktop/releases/download/v1.3.1/$name"
$expect = "b2578949ca0b3421b8bd014d1015de4232f69d1ac13fca0026191fd471c5f878"
$zip = Join-Path $dest $name
if (-not (Test-Path $zip)) {
  Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
}
$hash = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
if ($hash -ne $expect) { throw "SHA256 mismatch: $hash" }
Write-Host "Checksum OK $hash"
Expand-Archive -Path $zip -DestinationPath (Join-Path $dest "extracted") -Force
Write-Host "Extracted to ffi\extracted"
