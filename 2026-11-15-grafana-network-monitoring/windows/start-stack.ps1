$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Stack = $Root
if (Test-Path (Join-Path $Root '..\..\stack')) {
  # When copied next to NewsLessons stack folder, prefer that
}
# Prefer the NewsLessons stack directory if present
$NewsStack = 'C:\Users\superuser\Downloads\NewsLessons\2026-11-15-grafana-network-monitoring\stack'
if (Test-Path $NewsStack) { $Stack = $NewsStack }

$LogDir = Join-Path $Stack 'logs'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Start-Logged($Name, $File, $ArgList, $WorkDir, $EnvMap) {
  $out = Join-Path $LogDir "$Name.out.log"
  $err = Join-Path $LogDir "$Name.err.log"
  $procArgs = @{
    FilePath = $File
    WorkingDirectory = $WorkDir
    RedirectStandardOutput = $out
    RedirectStandardError = $err
    WindowStyle = 'Hidden'
    PassThru = $true
  }
  if ($ArgList) { $procArgs.ArgumentList = $ArgList }
  $p = Start-Process @procArgs
  Set-Content -Path (Join-Path $LogDir "$Name.pid") -Value $p.Id
  Write-Output "started $Name pid=$($p.Id)"
}

# Environment for Grafana OSS
$env:GF_SECURITY_ADMIN_USER = 'admin'
$env:GF_SECURITY_ADMIN_PASSWORD = 'labpass'
$env:GF_USERS_ALLOW_SIGN_UP = 'false'
$env:GF_AUTH_ANONYMOUS_ENABLED = 'false'
$env:GF_ANALYTICS_REPORTING_ENABLED = 'false'
$env:GF_CHECK_FOR_UPDATES = 'false'
$env:GF_SNAPSHOTS_EXTERNAL_ENABLED = 'false'
$env:GF_SERVER_HTTP_ADDR = '127.0.0.1'
$env:GF_SERVER_HTTP_PORT = '3000'

$promDir = Get-ChildItem $Stack -Directory -Filter 'prometheus-*' | Select-Object -First 1
$bbDir = Get-ChildItem $Stack -Directory -Filter 'blackbox_exporter-*' | Select-Object -First 1
$gfDir = Get-ChildItem $Stack -Directory -Filter 'grafana-*' | Select-Object -First 1
$winExp = Get-Item (Join-Path $Stack 'windows_exporter-0.32.1-amd64.exe')

# Copy configs into process dirs so --config.file can be a local path
Copy-Item (Join-Path $Root 'prometheus.yml') (Join-Path $promDir.FullName 'prometheus.yml') -Force
Copy-Item (Join-Path $Root 'blackbox.yml') (Join-Path $bbDir.FullName 'blackbox.yml') -Force

Start-Logged 'prometheus' (Join-Path $promDir.FullName 'prometheus.exe') @(
  '--config.file=prometheus.yml',
  '--storage.tsdb.path=data',
  '--web.listen-address=127.0.0.1:9090',
  '--web.enable-lifecycle'
) $promDir.FullName $null

Start-Logged 'blackbox' (Join-Path $bbDir.FullName 'blackbox_exporter.exe') @(
  '--config.file=blackbox.yml',
  '--web.listen-address=127.0.0.1:9115'
) $bbDir.FullName $null

Start-Logged 'windows_exporter' $winExp.FullName @(
  '--web.listen-address=127.0.0.1:9182',
  '--collectors.enabled=cpu,cs,logical_disk,memory,net,os,service,system,tcp'
) $Stack $null

$gfRoot = $gfDir.FullName
$gfBin = Join-Path $gfRoot 'bin\grafana-server.exe'
Start-Logged 'grafana' $gfBin @("--homepath=$gfRoot") $gfRoot $null

Write-Output "stack start issued from $Stack"
