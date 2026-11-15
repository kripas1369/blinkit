#!/usr/bin/env bash
# Upload Blinkit pack to the VPS and install + start it.
# Usage (from your Mac Terminal, where SSH passphrase works):
#   bash scripts/deploy_vps.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VPS="${VPS:-root@163.61.41.54}"
REMOTE_DIR="${REMOTE_DIR:-/opt/blinkit}"
PACK="$(ls -t "${ROOT}/dist"/blinkit-vps-*.tar.gz 2>/dev/null | head -1 || true)"

if [[ -z "${PACK}" || ! -f "${PACK}" ]]; then
  echo "Building pack…"
  bash "${ROOT}/scripts/pack_vps.sh"
  PACK="$(ls -t "${ROOT}/dist"/blinkit-vps-*.tar.gz | head -1)"
fi

BASE="$(basename "${PACK}")"

echo "Uploading ${PACK} → ${VPS}:/tmp/"
scp "${PACK}" "${VPS}:/tmp/${BASE}"

echo "Installing on ${VPS} under ${REMOTE_DIR}…"
ssh "${VPS}" "BASE='${BASE}' REMOTE_DIR='${REMOTE_DIR}' bash -s" <<'REMOTE'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip >/dev/null

rm -rf "${REMOTE_DIR}"
mkdir -p "${REMOTE_DIR}"
tar -xzf "/tmp/${BASE}" -C "${REMOTE_DIR}" --strip-components=1
rm -f "/tmp/${BASE}"
cd "${REMOTE_DIR}"
python3 -m venv .venv
. .venv/bin/activate
pip install -q -r requirements.txt
mkdir -p cache

cat > /etc/systemd/system/blinkit.service <<UNIT
[Unit]
Description=Blinkit SPHEREx
After=network.target

[Service]
Type=simple
WorkingDirectory=${REMOTE_DIR}
Environment=BLINKIT_DISABLE_DOCS=1
ExecStart=${REMOTE_DIR}/.venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 1
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable blinkit
systemctl restart blinkit
sleep 2
systemctl --no-pager --full status blinkit || true
curl -s -o /dev/null -w "health:%{http_code}\n" http://127.0.0.1:8000/api/health || true
curl -s -o /dev/null -w "home:%{http_code}\n" http://127.0.0.1:8000/ || true
echo "Official frames:"
ls "${REMOTE_DIR}/frontend/frames"
echo "Done. Open http://163.61.41.54:8000/"
REMOTE

echo
echo "If the page does not load from outside, open port 8000:"
echo "  ssh ${VPS} \"ufw allow 8000/tcp || true\""
