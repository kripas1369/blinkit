#!/usr/bin/env bash
# Build a VPS upload archive: app code + official frames (no .venv, no cache).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAMP="$(date -u +%Y%m%d)"
OUT_DIR="${ROOT}/dist"
NAME="blinkit-vps-${STAMP}"
STAGE="${OUT_DIR}/${NAME}"
ARCHIVE="${OUT_DIR}/${NAME}.tar.gz"

mkdir -p "${OUT_DIR}"
rm -rf "${STAGE}"
mkdir -p "${STAGE}"

echo "Staging ${NAME}…"
# Code + prepared official targets (gitignored frames must be copied explicitly)
rsync -a \
  --exclude '.venv' \
  --exclude 'venv' \
  --exclude '.git' \
  --exclude 'cache' \
  --exclude 'scratch' \
  --exclude 'dist' \
  --exclude 'node_modules' \
  --exclude '__pycache__' \
  --exclude '.pytest_cache' \
  --exclude '*.pyc' \
  --exclude '.DS_Store' \
  --exclude 'hold.md' \
  --exclude '.env' \
  --exclude '.env.*' \
  "${ROOT}/" "${STAGE}/"

if [[ ! -d "${STAGE}/frontend/frames/barnard" ]]; then
  echo "ERROR: frontend/frames/ missing official targets. Aborting." >&2
  exit 1
fi

mkdir -p "${STAGE}/cache"
cat > "${STAGE}/DEPLOY.txt" <<'EOF'
Blinkit — VPS deploy (official targets included)

1) Upload this folder (or the .tar.gz) to the server, e.g.:
   scp blinkit-vps-YYYYMMDD.tar.gz user@YOUR_VPS:~/
   ssh user@YOUR_VPS
   tar -xzf blinkit-vps-YYYYMMDD.tar.gz
   cd blinkit-vps-YYYYMMDD

2) Install:
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   mkdir -p cache

3) Run (production):
   export BLINKIT_DISABLE_DOCS=1
   uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 1

4) Optional: put Nginx + HTTPS in front (see docs/HOSTING.md).

Official frames are under frontend/frames/ — Barnard's Star and the other
hackathon targets load with no IRSA wait. Random RA/Dec still needs NASA IRSA.
EOF

cp "${ROOT}/docs/HOSTING.md" "${STAGE}/docs/HOSTING.md" 2>/dev/null || true

echo "Creating ${ARCHIVE}…"
tar -C "${OUT_DIR}" -czf "${ARCHIVE}" "${NAME}"

echo
echo "Ready to upload:"
echo "  ${ARCHIVE}"
du -sh "${ARCHIVE}" "${STAGE}/frontend/frames"
echo
echo "Upload example:"
echo "  scp ${ARCHIVE} user@YOUR_VPS:~/"
echo "  ssh user@YOUR_VPS 'tar -xzf ~/$(basename "${ARCHIVE}") && cd ~/$(basename "${ARCHIVE}" .tar.gz) && bash -s' <<'REMOTE'"
echo "  # then follow DEPLOY.txt on the server"
echo "REMOTE"
