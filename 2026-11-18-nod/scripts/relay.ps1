# Client-side relay for the Nod desktop app (runs on the Windows client, no admin needed).
# Nod only accepts an HTTPS origin or plain HTTP on localhost, so the app connects to
# http://localhost:4310 and this script forwards each connection to the relay on the Docker host.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File relay.ps1 -RemoteHost <docker-host-tailscale-ip> -RemotePort 8095
#
# Stop it by closing the window or: Get-NetTCPConnection -LocalPort 4310 -State Listen | % { Stop-Process -Id $_.OwningProcess }
param([Parameter(Mandatory=$true)][string]$RemoteHost, [int]$RemotePort = 8095, [int]$LocalPort = 4310)
$ErrorActionPreference = 'Stop'
$l = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, $LocalPort); $l.Start()
Write-Host "Listening on 127.0.0.1:$LocalPort -> ${RemoteHost}:$RemotePort"
while ($true) {
  $c = $l.AcceptTcpClient()
  try {
    $r = [Net.Sockets.TcpClient]::new(); $r.Connect($RemoteHost, $RemotePort)
    $c.NoDelay = $true; $r.NoDelay = $true
    $a = $c.GetStream(); $b = $r.GetStream()
    $t1 = $a.CopyToAsync($b); $t2 = $b.CopyToAsync($a)
    $cc = $c; $rr = $r
    [void][Threading.Tasks.Task]::WhenAny($t1, $t2).ContinueWith([Action[Threading.Tasks.Task]]{ param($x) try { $cc.Close() } catch {}; try { $rr.Close() } catch {} }.GetNewClosure())
  } catch { try { $c.Close() } catch {} }
}
