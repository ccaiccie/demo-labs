#!/usr/bin/env python3
"""Print the agent-desktop window id for a uniquely titled lab window only."""
import argparse, ctypes, json, sys
from ctypes import wintypes

user32 = ctypes.windll.user32
EnumWindows = user32.EnumWindows
EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
IsWindowVisible = user32.IsWindowVisible
IsIconic = user32.IsIconic
GetWindowTextLengthW = user32.GetWindowTextLengthW
GetWindowTextW = user32.GetWindowTextW
GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]

def titles():
    found = []
    def cb(hwnd, _):
        if not IsWindowVisible(hwnd) or IsIconic(hwnd):
            return True
        n = GetWindowTextLengthW(hwnd)
        if n <= 0:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        GetWindowTextW(hwnd, buf, n + 1)
        found.append((int(hwnd), buf.value))
        return True
    EnumWindows(EnumWindowsProc(cb), 0)
    return found

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--title-contains", required=True)
    args = ap.parse_args()
    needle = args.title_contains.lower()
    hits = [(h, t) for h, t in titles() if needle in t.lower()]
    if len(hits) != 1:
        print(json.dumps({"ok": False, "match_count": len(hits)}))
        return 1
    hwnd, title = hits[0]
    # agent-desktop window ids on Windows are w- followed by the handle.
    wid = f"w-{hwnd}"
    print(json.dumps({"ok": True, "window_id": wid, "title": title, "hwnd": hwnd}))
    return 0

if __name__ == "__main__":
    sys.exit(main())
