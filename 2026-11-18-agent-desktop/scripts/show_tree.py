#!/usr/bin/env python3
"""Print a compact accessibility tree: role, name, ref. No file-dialog values."""
import json, sys

SKIP_ROLES = {"treeitem", "outline", "listbox", "option"}

def walk(n, acc):
    if not isinstance(n, dict):
        return
    role = n.get("role")
    rec = {"role": role, "name": n.get("name"), "ref": n.get("ref_id"), "actions": n.get("available_actions")}
    if n.get("children_count"):
        rec["children_count"] = n.get("children_count")
    # values only for small lab fields, never for file-dialog rows
    if role in ("textfield", "statictext", "checkbox", "combobox") and role not in SKIP_ROLES:
        val = n.get("value")
        if isinstance(val, str) and len(val) <= 80 and "\\Users\\" not in val.replace("/", "\\"):
            rec["value"] = val
    if rec.get("name") or rec.get("ref") or rec.get("children_count"):
        if role not in SKIP_ROLES:
            acc.append({k: v for k, v in rec.items() if v not in (None, "", [])})
    for c in n.get("children") or []:
        walk(c, acc)

def main():
    raw = sys.stdin.read()
    try:
        env = json.loads(raw)
    except json.JSONDecodeError:
        print(raw[:400])
        return 1
    if not env.get("ok"):
        err = env.get("error") or {}
        print("ERROR", err.get("code"), err.get("message"))
        return 1
    data = env.get("data") or {}
    if env.get("command") == "snapshot":
        print("app=", data.get("app"), "snapshot_id=", data.get("snapshot_id"), "ref_count=", data.get("ref_count"), "complete=", data.get("complete"))
        rows = []
        walk(data.get("tree") or {}, rows)
        for r in rows:
            print(r)
        return 0
    # other commands: print a short envelope, no deep data dump
    keys = {k: data.get(k) for k in data if k in ("action", "disposition", "app", "version", "os", "target", "snapshot_id", "ref_count", "match", "found", "observed", "predicate", "state_root", "platform", "permissions", "supported_surfaces")}
    print("ok", env.get("ok"), "command", env.get("command"))
    print(json.dumps(keys, indent=2)[:2000])
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
