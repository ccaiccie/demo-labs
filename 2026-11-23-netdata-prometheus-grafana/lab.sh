#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
# Force the local socket, never a remote Docker context inherited from a
# production shell. Run as a user trusted with Docker in this dedicated VM.
unset DOCKER_HOST DOCKER_CONTEXT
d(){ docker -H unix:///var/run/docker.sock compose "$@"; }
die(){ printf 'Error: %s\n' "$*" >&2; exit 1; }
command -v docker >/dev/null || die 'Docker Engine and the Compose plugin are required.'
command -v python3 >/dev/null || die 'Python 3 is required.'
[[ "$(uname -s):$(uname -m)" == "Linux:x86_64" ]] || die 'This digest-pinned lab targets a Linux amd64 VM.'
d version >/dev/null || die 'Docker Compose is not available.'
wait_http(){
  python3 - "$1" <<'PY'
import sys, time, urllib.request
url=sys.argv[1]
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
for _ in range(30):
    try:
        with opener.open(url,timeout=2) as r:
            if r.status == 200:
                print("Ready:",url); break
    except OSError:
        pass
    time.sleep(2)
else:
    raise SystemExit("Service never became ready: "+url)
PY
}
case "${1:-}" in
  pull)
    d config --quiet
    refs=$(d config --images)
    mapfile -t images <<< "$refs"
    [[ "${#images[@]}" -eq 3 ]] || die 'Expected three pinned image references.'
    for image in "${images[@]}"; do
      docker -H unix:///var/run/docker.sock image pull --platform linux/amd64 "$image"
    done
    ;;
  start)
    # Never overwrite or compete with a running listener in this VM.
    # This is only an availability check; Docker still binds the real ports.
    python3 - <<'PORTS'
import socket
for kind, port in [(socket.SOCK_DGRAM,8125),
                   (socket.SOCK_STREAM,8199),
                   (socket.SOCK_STREAM,9090),
                   (socket.SOCK_STREAM,3090)]:
    try:
        with socket.socket(socket.AF_INET,kind) as s:
            s.bind(("127.0.0.1",port))
    except OSError as err:
        raise SystemExit(f"Port {port} is unavailable; no containers were started: {err}")
PORTS
    [[ ! -L .secrets && ! -L .secrets/grafana-admin ]] || die 'Unexpected symlink in secret path.'
    # Secret content is never displayed. 0444 lets container UID 472 read
    # the file through its individual mount; the directory is mode 0700.
    install -d -m 0700 .secrets
    if [[ ! -s .secrets/grafana-admin ]]; then
      (umask 077; python3 -c 'import secrets; print(secrets.token_urlsafe(42))' > .secrets/grafana-admin)
      chmod 0444 .secrets/grafana-admin
    fi
    d up -d --pull never netdata
    wait_http http://127.0.0.1:8199/api/v1/info
    python3 phase.py baseline > setup-baseline.log &
    seed=$!
    cleanup_seed(){ kill "$seed" 2>/dev/null || true; wait "$seed" 2>/dev/null || true; }
    trap cleanup_seed EXIT
    ready=0
    for ((i=0;i<15;i++)); do
      if python3 configure.py > setup-configure.log 2>&1; then
        ready=1; break
      fi
      sleep 2
    done
    if [[ "$ready" != 1 ]]; then
      cat setup-configure.log >&2
      die 'The expected gauges did not appear in Netdata.'
    fi
    cat setup-configure.log
    d config --quiet
    d up -d --pull never prometheus grafana
    wait_http http://127.0.0.1:9090/-/ready
    wait_http http://127.0.0.1:3090/api/health
    d ps
    printf '\nPrometheus targets: http://127.0.0.1:9090/targets\nGrafana: http://127.0.0.1:3090/d/netdata-checkout\n'
    ;;
  replay)
    python3 phase.py baseline spike recovery | tee phases.log
    python3 validate.py
    ;;
  verify)
    python3 validate.py
    ;;
  stop)
    d down
    ;;
  *)
    printf 'Usage: %s {pull|start|replay|verify|stop}\n' "$0" >&2
    exit 2
    ;;
esac
