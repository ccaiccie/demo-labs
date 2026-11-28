#!/bin/sh
# creates a 12 MB binary-looking file for the web server (not committed)
dd if=/dev/urandom of="$(dirname "$0")/../web/html/backup.bin" bs=1M count=12 2>/dev/null
