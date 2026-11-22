#!/bin/sh
set -eu

if ! command -v git >/dev/null 2>&1; then
  apk add --no-cache git >/dev/null
fi

SRC_DIR="/src/git-repo"
WORK_DIR="/tmp/work-repo"
BARE_DIR="/srv/git/nautobot-lab-repo.git"

rm -rf "${WORK_DIR}" "${BARE_DIR}"
mkdir -p "${WORK_DIR}" /srv/git

if [ -d "${SRC_DIR}" ] && [ "$(ls -A "${SRC_DIR}" 2>/dev/null)" ]; then
  cp -r "${SRC_DIR}/." "${WORK_DIR}/"
else
  echo "# Nautobot Lab Git Repository" > "${WORK_DIR}/README.md"
fi

# Strip any nested .git directory if present in source mount
rm -rf "${WORK_DIR}/.git"

git config --global --add safe.directory '*'
cd "${WORK_DIR}"
git init -b main
git config user.name "Nautobot Lab"
git config user.email "lab@lab.internal"
git add -A
git commit -m "Initial Nautobot lab data source commit"

git clone --bare "${WORK_DIR}" "${BARE_DIR}"
git --git-dir="${BARE_DIR}" update-server-info

echo "Serving bare Git repository at http://git-server:8000/nautobot-lab-repo.git"
exec python3 -m http.server 8000 --bind 0.0.0.0 --directory /srv/git
