# 2026-11-18-agent-desktop

A hands-on Windows lab for [Vercel Labs agent-desktop](https://github.com/vercel-labs/agent-desktop) (`npm` package `agent-desktop`, docs at [agent-browser.dev/desktop](https://agent-browser.dev/desktop)).

agent-desktop is a command-line computer-use tool for AI agents. It reads a desktop app's OS accessibility tree (UI Automation on Windows, AX on macOS, AT-SPI on Linux) and returns JSON with a ref for every element the agent can act on. **It has no model inside.** The observe, act, and verify loop lives in your agent or in the commands you type.

This folder is the lab from the Network Technician demo. All traffic and GUI work stays on the local machine. Do not snapshot everyday browser windows.

## Privacy

Snapshots, clipboard reads, screenshots, command output, and file-dialog trees can contain private desktop content. Keep them out of public logs and out of git.

- Set `AGENT_DESKTOP_HOME` to a user-private folder (for example `%LOCALAPPDATA%\agent-desktop-lab`). A directory under `Downloads` may inherit extra ACLs; agent-desktop then fails with a private-file DACL error.
- Always snapshot with `--app` or `--window-id`. Never snapshot the focused desktop blindly.
- Do not run `list-windows --app chrome.exe` or `snapshot --app chrome.exe` if Chrome is already running with personal tabs.
- For a Save As dialog, click **Hide Folders** first, then use `find` for the File name field and the Save button. Do not dump the full dialog tree.
- `scripts/lab_window.py` prints a window id only when exactly one visible window title matches. It does not print other titles.
- `scripts/show_tree.py` prints role, name, and ref, and skips file-dialog tree rows.

Grok Bot, if it is used to drive the machine, must stay open (minimized is fine). Closing it can disconnect the session.

## Chrome extensions

**This lab does not install a Chrome extension.** Official docs drive web contents with `launch --cdp` (a loopback-only DevTools port) plus a CDP client such as agent-browser, not with a browser plugin. Because no extension is required, none was installed, and there is no third-party extension source to review for spyware, telemetry, exfiltration, remote code, or obfuscation.

If you later want to add a Chrome plugin, review its **entire** source first (network calls, permissions, remote code, obfuscation), write down the review, and skip the plugin if anything is suspicious. A throwaway profile, if you launch one, should use `--disable-extensions` and `--user-data-dir` pointed at `lab-chrome-profile/` (gitignored), with only the local page in `pages/lab.html`. `launch chrome --cdp` refuses to attach to a browser that is already running; do not quit someone else's Chrome to force it.

## Requirements

- Windows 10 1809+ or Windows 11, interactive desktop session (not session 0).
- Node.js and `npm install -g --allow-scripts=agent-desktop agent-desktop` (the postinstall unpacks the native binary). This lab was tested with agent-desktop **1.3.1**.
- PowerShell. Quote every ref in single quotes (`'@s123:e8'`), because a bare `@token` is the splatting operator.
- Optional: Ubuntu 24.04 WSL, to run the Linux binary for `status` only.

## Quick start

```powershell
$env:AGENT_DESKTOP_HOME = Join-Path $env:LOCALAPPDATA "agent-desktop-lab"
New-Item -ItemType Directory -Force -Path $env:AGENT_DESKTOP_HOME | Out-Null

agent-desktop version
agent-desktop status
agent-desktop permissions
agent-desktop skills get desktop
agent-desktop skills get platform
```

`status` should show `platform: windows`, `accessibility: granted`, and a `state_root` under your private home.

## Exercises (what the demo actually ran)

### 1. Calculator

```powershell
agent-desktop launch calc.exe --activate
# The window is owned by CalculatorApp.exe
agent-desktop snapshot --app CalculatorApp.exe --skeleton -i --compact | python .\scripts\show_tree.py
agent-desktop snapshot --app CalculatorApp.exe -i --compact | python .\scripts\show_tree.py
agent-desktop find --app CalculatorApp.exe --role button --name Seven --first
```

Buttons are named `Seven`, `Plus`, `Five`, `Equals`, and `Clear`, not `7`. A skeleton snapshot marks a keypad group with `children_count: 9` but that group has no `ref_id`, so `--root` cannot drill into it. Take a full interactive snapshot instead.

Headless `click` uses the UIA Invoke pattern and **does not move the mouse**. After `Seven + Five =`, the display static text is named `Display is 12`. Confirm with:

```powershell
agent-desktop wait --app CalculatorApp.exe --text "Display is 12" --timeout 5000
```

Headless `hover` returns `POLICY_DENIED`. `hover --headed` moves the pointer (a physical mouse-move). A `--headed click` on a calculator key is still a semantic invoke, so use `hover` or the mouse commands if you want a visible pointer.

### 2. Notepad, menus, and Save As

```powershell
agent-desktop launch notepad.exe --activate
agent-desktop snapshot --app notepad.exe -i --compact | python .\scripts\show_tree.py
```

If a "new version of Notepad" banner appears, click `Dismiss`, not `Install`. Write text headless with `set-value` on the `Text Editor` field. Headless `type` returns `POLICY_DENIED` (keystroke synthesis needs `--headed`).

Expand `File`, take a **fresh** snapshot, and click `Save As...` immediately. A stale menu ref can time out. After the dialog opens:

1. `find --name "Hide Folders"` and click it, so personal locations are not on screen.
2. `find` the `File name:` field and the `Save` button only.
3. `set-value` a full path under this lab's `notes\` folder, then click `Save`.

### 3. STALE_REF and bare refs

Refs belong to the snapshot that created them. Reusing a `Dismiss` ref after the banner is gone returns `STALE_REF`. A bare `@e1` returns `INVALID_ARGS`. Take a new snapshot and use the new qualified refs (`@<snapshot_id>:eN`).

### 4. Accessibility limits: Tkinter vs WinForms

`apps/port_allocator.py` is a Tkinter "Lab Port Allocator". On Windows its snapshot is almost empty (menus and one unnamed button). The Allocate field and log are not in the UIA tree. That is a limit of what Tkinter exposes, not a bug in agent-desktop.

`apps/port_allocator.ps1` is the same app in WinForms. Launch it with:

```powershell
powershell -STA -NoProfile -ExecutionPolicy Bypass -File .\apps\port_allocator.ps1
python .\scripts\lab_window.py --title-contains "Lab Port Allocator"
agent-desktop snapshot --window-id 'w-...' -i --compact | python .\scripts\show_tree.py
```

You should see `Starting port`, `Skip even ports`, `Allocate next port`, `Reset`, `Allocation log`, File/Help menus, and **one unnamed button** (the plus control).

- `set-value` on Starting port, then click the unnamed plus button to bump it.
- `toggle` on `Skip even ports` (delivered and verified).
- With `OffByOne = $true` (the default), the first Allocate returns **8001**, skipping 8000.
- Set `OffByOne = $false` in the script, restart, and Allocate returns 8000, then 8001.

A WinForms `MessageBox` About dialog can open and still return `TIMEOUT` on the Invoke; prefer the Notepad Save As dialog, plus `find`, for a reliable dialog demo.

### 5. C library

The CLI and the C library share the same core. Download the official Windows x64 FFI zip and verify the SHA-256 (do not use a third-party build):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\download_ffi.ps1
python .\scripts\ffi_version.py
```

Expected: ABI major **7**, `ad_version` envelope reports **1.3.1**. The script only calls version APIs; it does not snapshot the focused window.

SHA-256 for `agent-desktop-ffi-v1.3.1-x86_64-pc-windows-msvc.zip`:

`b2578949ca0b3421b8bd014d1015de4232f69d1ac13fca0026191fd471c5f878`

### 6. Linux under WSL (optional)

The npm package includes `agent-desktop-linux-x64`. On Ubuntu 24.04 WSL with WSLg, `status` reported platform `linux`, version 1.3.1, accessibility granted, and surfaces `window`, `sheet`, `alert`, and `menu`. Do not snapshot the WSL desktop session if it may contain private windows.

```bash
cp /mnt/c/Users/superuser/AppData/Roaming/npm/node_modules/agent-desktop/bin/agent-desktop-linux-x64 /tmp/agent-desktop
chmod +x /tmp/agent-desktop
/tmp/agent-desktop version
/tmp/agent-desktop status
```

## Notes from testing

| Topic | Result |
| --- | --- |
| Install | `npm install -g` needed `--allow-scripts=agent-desktop` so the native binary unpacked |
| Calculator process | `launch calc.exe` starts `CalculatorApp.exe` |
| Headless click | Cursor position unchanged; 7+5=12 worked |
| Headed hover | Pointer moved; headless hover is `POLICY_DENIED` |
| Notepad set-value | `delivered_verified` via ValuePattern |
| Save As | Worked after a fresh snapshot; earlier stale menu refs timed out |
| State directory | `%USERPROFILE%\Downloads\...` failed DACL check because of an inherited group |
| Tkinter | Form controls missing from UIA |
| WinForms | Full tree; unnamed plus button; off-by-one visible in the log |
| About MessageBox | Dialog appeared but click often returned `TIMEOUT` |
| Chrome `--cdp` | Not used against an already-running Chrome (would require quitting it) |

## License

Lab scripts and the sample app are for this demo. agent-desktop itself is Apache-2.0.
