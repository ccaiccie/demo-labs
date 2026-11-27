#!/usr/bin/env bash
# Reproducible installer for netlab, containerlab, ansible, graphviz, and sshpass
# on WSL Ubuntu 24.04. Does not touch any existing Docker containers or networks.
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run this script as root (e.g. sudo bash scripts/install-netlab.sh or wsl -d Ubuntu-24.04 -u root ...)." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

echo "[1/5] Installing OS packages (python3, pip, venv, graphviz, sshpass, curl, jq, iproute2)..."
apt-get update -qq
apt-get install -y -qq \
  python3 python3-pip python3-venv pipx \
  graphviz sshpass curl jq ca-certificates gnupg lsb-release iproute2

echo "[2/5] Installing netlab (networklab) and ansible..."
python3 -m pip install --break-system-packages --upgrade networklab ansible

echo "[3/5] Installing containerlab (if not already present)..."
if ! command -v containerlab >/dev/null 2>&1; then
  bash -c "$(curl -sL https://get.containerlab.dev)"
else
  echo "containerlab already installed: $(containerlab version | head -n 1)"
fi

echo "[4/5] Verifying Docker daemon access..."
docker version --format 'Docker Client: {{.Client.Version}} / Server: {{.Server.Version}}'

echo "[5/5] Verifying installed tool versions..."
netlab --version
containerlab version | head -n 4
ansible-playbook --version | head -n 1
dot -V
sshpass -V | head -n 1

echo "Install complete. Run 'netlab up' inside the lab directory."
