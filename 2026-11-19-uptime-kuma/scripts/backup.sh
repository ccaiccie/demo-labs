#!/usr/bin/env bash
# Back up the Uptime Kuma data volume (SQLite database, settings, uploads) to a tarball.
# Uptime Kuma 2.x has no JSON export in Settings; the data volume is the backup.
set -euo pipefail
VOL="${VOL:-uptime-kuma-lab_kuma-data}"
OUT="${1:-kuma-backup-$(date +%Y%m%d-%H%M).tgz}"
docker run --rm -v "$VOL":/data:ro -v "$PWD":/backup alpine:3.20 tar czf "/backup/$OUT" -C /data .
ls -lh "$OUT"
tar tzf "$OUT" | head -n 15
