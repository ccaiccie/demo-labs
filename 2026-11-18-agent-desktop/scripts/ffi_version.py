#!/usr/bin/env python3
"""Call the official agent-desktop C library for version only. No desktop snapshot."""
import ctypes, json, sys
from ctypes import c_char_p, c_int, c_uint, POINTER, byref
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DLL = ROOT / "ffi" / "extracted" / "agent-desktop-ffi-v1.3.1-x86_64-pc-windows-msvc" / "lib" / "agent_desktop_ffi.dll"

def main():
    if not DLL.exists():
        print("missing dll", DLL, file=sys.stderr)
        return 1
    lib = ctypes.CDLL(str(DLL))
    lib.ad_abi_version.restype = c_uint
    lib.ad_abi_version.argtypes = []
    lib.ad_version.restype = c_int
    lib.ad_version.argtypes = [POINTER(c_char_p)]
    lib.ad_free_string.restype = None
    lib.ad_free_string.argtypes = [c_char_p]
    major = lib.ad_abi_version()
    out = c_char_p()
    rc = lib.ad_version(byref(out))
    raw = out.value
    if raw is not None:
        lib.ad_free_string(out)
    env = json.loads(raw) if raw else {"ok": False, "rc": rc}
    print(json.dumps({"abi_major": major, "ad_version_rc": rc, "envelope": env}, indent=2))
    return 0 if rc == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
