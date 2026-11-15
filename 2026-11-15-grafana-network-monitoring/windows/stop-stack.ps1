$ErrorActionPreference = 'Continue'
$NewsStack = 'C:\Users\superuser\Downloads\NewsLessons\2026-11-15-grafana-network-monitoring\stack'
$LogDir = Join-Path $NewsStack 'logs'
foreach ($name in @('grafana','prometheus','blackbox','windows_exporter')) {
  $pf = Join-Path $LogDir "$name.pid"
  if (Test-Path $pf) {
    $id = (Get-Content $pf | Select-Object -First 1).Trim()
    if ($id) {
      Stop-Process -Id ([int]$id) -Force -ErrorAction SilentlyContinue
      Write-Output "stopped $name pid=$id"
    }
    Remove-Item $pf -Force -ErrorAction SilentlyContinue
  }
}
# fallback by process name
Get-Process prometheus,blackbox_exporter,grafana-server,windows_exporter,windows_exporter-0.32.1-amd64 -ErrorAction SilentlyContinue |
  Stop-Process -Force -ErrorAction SilentlyContinue
Write-Output 'stack stop complete'
