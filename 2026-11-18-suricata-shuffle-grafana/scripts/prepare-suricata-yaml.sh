#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/suricata/etc/suricata.yaml"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

echo "[*] Extracting default suricata.yaml from jasonish/suricata:latest"
docker run --rm --entrypoint cat jasonish/suricata:latest /etc/suricata/suricata.yaml > "$TMP/suricata.yaml"

python3 - "$TMP/suricata.yaml" "$OUT" << 'PY'
import sys, re
src, dst = sys.argv[1], sys.argv[2]
text = open(src, encoding="utf-8", errors="replace").read()

# Ensure local.rules is loaded. Prefer appending under rule-files if present.
if "local.rules" not in text:
    # common pattern in default config
    if re.search(r"^rule-files:\s*$", text, re.M):
        text = re.sub(
            r"(^rule-files:\s*\n(?:\s*-\s*.+\n)*)",
            r"\1  - /etc/suricata/rules/local.rules\n",
            text,
            count=1,
            flags=re.M,
        )
    else:
        # fallback: add a rule-files block near default-rule-path
        text = text.replace(
            "default-rule-path: /var/lib/suricata/rules",
            "default-rule-path: /var/lib/suricata/rules\nrule-files:\n  - suricata.rules\n  - /etc/suricata/rules/local.rules",
            1,
        )

# Force eve-log enabled if somehow off
text = re.sub(r"(eve-log:\n\s+enabled:\s*)no", r"\1yes", text)

open(dst, "w", encoding="utf-8").write(text)
print(f"[+] wrote {dst} ({len(text)} bytes)")
PY

# Also ensure rules dir exists in the volume by priming via a short container later
echo "[+] suricata.yaml ready"
