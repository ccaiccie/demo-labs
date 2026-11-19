# Verify the Nod Windows installer before running it.
# Compare the hash with the sha256 digest shown next to the asset on the GitHub release page.
param([string]$Path = "$env:USERPROFILE\Downloads\nod-Setup-x64.exe",
      [string]$Expected = '67338CB5C5D118BB34A3E86FC467D04E64BD2302FA1895490F2CD0897C1B8E7E')  # nod-v0.8.4
$h = (Get-FileHash $Path -Algorithm SHA256).Hash
"SHA256  : $h"
"Matches : $($h -eq $Expected)"
$sig = Get-AuthenticodeSignature $Path
"Status  : $($sig.Status)"
"Signer  : $($sig.SignerCertificate.Subject)"
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole('Administrators')
"Admin   : $admin   (local mode needs WSL 2, and installing WSL needs admin)"
