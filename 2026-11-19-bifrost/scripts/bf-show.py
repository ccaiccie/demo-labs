#!/usr/bin/env python3
"""Pretty-print a Bifrost chat or MCP JSON body. Never prints secrets."""
import json, re, sys
from pathlib import Path

def red(s: str) -> str:
    s = re.sub(r"sk-[A-Za-z0-9_-]+", "sk-REDACTED", s)
    s = re.sub(r"(Bearer )\S+", r"\1REDACTED", s)
    return s

def main() -> int:
    raw = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace") if len(sys.argv) > 1 else sys.stdin.read()
    raw = raw.strip()
    # MCP SSE: data: {...}
    if raw.startswith("event:") or "data:" in raw[:80]:
        for line in raw.splitlines():
            if line.startswith("data:"):
                raw = line[5:].strip()
                break
    try:
        obj = json.loads(raw)
    except Exception:
        print(red(raw)[:1200])
        return 0
    # chat completion
    if isinstance(obj, dict) and (obj.get("choices") or obj.get("error") or obj.get("type")):
        if "id" in obj: print("id:", obj.get("id"))
        if "model" in obj: print("model:", obj.get("model"))
        if "usage" in obj: print("usage:", json.dumps(obj.get("usage")))
        ch = obj.get("choices") or []
        if ch:
            msg = (ch[0] or {}).get("message") or {}
            content = msg.get("content")
            tools = msg.get("tool_calls")
            if content: print("content:", content)
            if tools: print("tool_calls:", red(json.dumps(tools))[:800])
        err = obj.get("error") or (obj if obj.get("type") else None)
        if obj.get("type") or obj.get("error"):
            print("error_type:", obj.get("type") or (obj.get("error") or {}).get("type") if isinstance(obj.get("error"), dict) else obj.get("type"))
            print("status_code:", obj.get("status_code"))
            if isinstance(obj.get("error"), dict):
                print("error:", red(obj["error"].get("message") or json.dumps(obj["error"]))[:400])
            elif obj.get("error"):
                print("error:", red(str(obj.get("error")))[:400])
        return 0
    # MCP tools/list
    if isinstance(obj, dict) and "result" in obj:
        res = obj["result"]
        if isinstance(res, dict) and "tools" in res:
            names = [t.get("name") for t in res.get("tools") or []]
            print("tools:", ", ".join(str(n) for n in names))
            return 0
        if isinstance(res, dict) and ("content" in res or "structuredContent" in res):
            print("result:", red(json.dumps(res, indent=2))[:2000])
            return 0
        print(red(json.dumps(res, indent=2))[:2000])
        return 0
    print(red(json.dumps(obj, indent=2))[:2000])
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
