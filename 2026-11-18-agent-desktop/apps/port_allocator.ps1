# Lab Port Allocator (WinForms) - intentional off-by-one for the agent-desktop demo.
# Requires: powershell -STA -File port_allocator.ps1
# Flip $script:OffByOne to $false after confirming the bug, then restart to re-verify.
$script:OffByOne = $true
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()
[System.Windows.Forms.Application]::SetCompatibleTextRenderingDefault($false)

$script:NextPort = 8000
$font = New-Object System.Drawing.Font("Segoe UI", 16)
$fontBig = New-Object System.Drawing.Font("Cascadia Mono", 28, [System.Drawing.FontStyle]::Bold)
$fontLog = New-Object System.Drawing.Font("Cascadia Mono", 14)
$bg = [System.Drawing.Color]::FromArgb(247, 244, 238)

$form = New-Object System.Windows.Forms.Form
$form.Text = "Lab Port Allocator - 2026-11-18-agent-desktop"
$form.StartPosition = "Manual"
$form.Location = New-Object System.Drawing.Point(1020, 80)
$form.Size = New-Object System.Drawing.Size(840, 680)
$form.BackColor = $bg
$form.Font = $font
$form.MinimumSize = New-Object System.Drawing.Size(740, 600)

function Write-Log([string]$line) {
  $logBox.AppendText($line + [Environment]::NewLine)
}

$hdr = New-Object System.Windows.Forms.Label
$hdr.Text = "Lab Port Allocator"
$hdr.Font = New-Object System.Drawing.Font("Segoe UI", 22, [System.Drawing.FontStyle]::Bold)
$hdr.AutoSize = $true
$hdr.Location = New-Object System.Drawing.Point(20, 16)
$form.Controls.Add($hdr)

$sub = New-Object System.Windows.Forms.Label
$sub.Text = "Allocate the next free TCP port for a local lab service."
$sub.AutoSize = $true
$sub.Location = New-Object System.Drawing.Point(20, 60)
$form.Controls.Add($sub)

$lblPort = New-Object System.Windows.Forms.Label
$lblPort.Text = "Starting port"
$lblPort.AutoSize = $true
$lblPort.Location = New-Object System.Drawing.Point(20, 110)
$form.Controls.Add($lblPort)

$portBox = New-Object System.Windows.Forms.TextBox
$portBox.Text = "8000"
$portBox.Width = 120
$portBox.Location = New-Object System.Drawing.Point(200, 106)
$portBox.AccessibleName = "Starting port"
$form.Controls.Add($portBox)

# Image-only plus button with no accessible name (agent must find it by role).
$plusBmp = New-Object System.Drawing.Bitmap 28, 28
$g = [System.Drawing.Graphics]::FromImage($plusBmp)
$g.Clear([System.Drawing.Color]::FromArgb(232, 238, 248))
$br = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(31, 111, 235))
$g.FillRectangle($br, 6, 12, 16, 4)
$g.FillRectangle($br, 12, 6, 4, 16)
$g.Dispose(); $br.Dispose()
$plusBtn = New-Object System.Windows.Forms.Button
$plusBtn.Image = $plusBmp
$plusBtn.Text = ""
$plusBtn.Width = 36; $plusBtn.Height = 36
$plusBtn.Location = New-Object System.Drawing.Point(330, 100)
$plusBtn.AccessibleName = ""
$plusBtn.AccessibleRole = [System.Windows.Forms.AccessibleRole]::PushButton
$plusBtn.TabStop = $true
$plusBtn.Add_Click({
  $n = 0
  if (-not [int]::TryParse($portBox.Text, [ref]$n)) { $n = $script:NextPort }
  $n++
  $script:NextPort = $n
  $portBox.Text = "$n"
  Write-Log "Starting port bumped to $n."
})
$form.Controls.Add($plusBtn)

$skip = New-Object System.Windows.Forms.CheckBox
$skip.Text = "Skip even ports"
$skip.AutoSize = $true
$skip.Location = New-Object System.Drawing.Point(20, 160)
$skip.AccessibleName = "Skip even ports"
$skip.Add_CheckedChanged({ Write-Log ("Skip even ports = " + $skip.Checked) })
$form.Controls.Add($skip)

function Get-Start {
  $n = 0
  if ([int]::TryParse($portBox.Text, [ref]$n)) { return $n }
  return $script:NextPort
}

function Allocate-Next {
  $script:NextPort = Get-Start
  if ($script:OffByOne) {
    $script:NextPort++
    $value = $script:NextPort
  } else {
    $value = $script:NextPort
    $script:NextPort++
  }
  if ($skip.Checked -and ($value % 2 -eq 0)) {
    $portBox.Text = "$($script:NextPort)"
    return Allocate-Next
  }
  $portBox.Text = "$($script:NextPort)"
  return $value
}

$allocBtn = New-Object System.Windows.Forms.Button
$allocBtn.Text = "Allocate next port"
$allocBtn.AutoSize = $true
$allocBtn.Location = New-Object System.Drawing.Point(20, 210)
$allocBtn.AccessibleName = "Allocate next port"
$allocBtn.Add_Click({
  $value = Allocate-Next
  $result.Text = "$value"
  Write-Log "Allocated port $value. Next start would be $($script:NextPort)."
})
$form.Controls.Add($allocBtn)

$resetBtn = New-Object System.Windows.Forms.Button
$resetBtn.Text = "Reset"
$resetBtn.AutoSize = $true
$resetBtn.Location = New-Object System.Drawing.Point(280, 210)
$resetBtn.AccessibleName = "Reset"
$resetBtn.Add_Click({
  $script:NextPort = 8000
  $portBox.Text = "8000"
  $result.Text = "(none yet)"
  $skip.Checked = $false
  Write-Log "Reset to starting port 8000."
})
$form.Controls.Add($resetBtn)

$lblLast = New-Object System.Windows.Forms.Label
$lblLast.Text = "Last allocated"
$lblLast.AutoSize = $true
$lblLast.Location = New-Object System.Drawing.Point(20, 270)
$form.Controls.Add($lblLast)

$result = New-Object System.Windows.Forms.Label
$result.Text = "(none yet)"
$result.Font = $fontBig
$result.AutoSize = $true
$result.ForeColor = [System.Drawing.Color]::FromArgb(31, 111, 235)
$result.Location = New-Object System.Drawing.Point(20, 305)
$result.AccessibleName = "Last allocated"
$form.Controls.Add($result)

$lblLog = New-Object System.Windows.Forms.Label
$lblLog.Text = "Allocation log"
$lblLog.AutoSize = $true
$lblLog.Location = New-Object System.Drawing.Point(20, 360)
$form.Controls.Add($lblLog)

$logBox = New-Object System.Windows.Forms.TextBox
$logBox.Multiline = $true
$logBox.ScrollBars = "Vertical"
$logBox.ReadOnly = $true
$logBox.Font = $fontLog
$logBox.Location = New-Object System.Drawing.Point(20, 395)
$logBox.Size = New-Object System.Drawing.Size(780, 180)
$logBox.Anchor = "Top,Left,Right,Bottom"
$logBox.AccessibleName = "Allocation log"
$form.Controls.Add($logBox)

$menu = New-Object System.Windows.Forms.MenuStrip
$file = New-Object System.Windows.Forms.ToolStripMenuItem "File"
$export = New-Object System.Windows.Forms.ToolStripMenuItem "Export log..."
$export.Add_Click({
  $dlg = New-Object System.Windows.Forms.SaveFileDialog
  $dlg.Title = "Export allocation log"
  $dlg.Filter = "Text files (*.txt)|*.txt|All files (*.*)|*.*"
  $dlg.FileName = "port-allocations.txt"
  if ($dlg.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    [IO.File]::WriteAllText($dlg.FileName, $logBox.Text)
    Write-Log "Exported log to $($dlg.FileName)."
    [System.Windows.Forms.MessageBox]::Show("Wrote $($dlg.FileName)", "Export complete")
  }
})
$quit = New-Object System.Windows.Forms.ToolStripMenuItem "Quit"
$quit.Add_Click({ $form.Close() })
[void]$file.DropDownItems.Add($export)
[void]$file.DropDownItems.Add($quit)
$help = New-Object System.Windows.Forms.ToolStripMenuItem "Help"
$about = New-Object System.Windows.Forms.ToolStripMenuItem "About"
$about.Add_Click({
  [System.Windows.Forms.MessageBox]::Show("A harmless local demo app for agent-desktop.`r`nOFF_BY_ONE is currently $($script:OffByOne).", "About Lab Port Allocator")
})
[void]$help.DropDownItems.Add($about)
[void]$menu.Items.Add($file)
[void]$menu.Items.Add($help)
$form.MainMenuStrip = $menu
$form.Controls.Add($menu)

Write-Log "Ready. OFF_BY_ONE=$($script:OffByOne). Starting port $($script:NextPort)."
[System.Windows.Forms.Application]::Run($form)
