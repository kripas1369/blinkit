#!/usr/bin/env bash
# Run ON the VPS as root. Installs Blinkit from GitHub only.
#   curl -fsSL https://raw.githubusercontent.com/kripas1369/blinkit/phase1-complete/scripts/vps_git_setup.sh | bash
# Or after clone: bash scripts/vps_git_setup.sh
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/kripas1369/blinkit.git}"
BRANCH="${BRANCH:-phase1-complete}"
REMOTE_DIR="${REMOTE_DIR:-/opt/blinkit}"
DOMAIN="${DOMAIN:-blinkit.study}"

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq git python3 python3-venv python3-pip nginx certbot python3-certbot-nginx >/dev/null

if [[ -d "${REMOTE_DIR}/.git" ]]; then
  cd "${REMOTE_DIR}"
  git fetch origin
  git checkout "${BRANCH}"
  git pull --ff-only origin "${BRANCH}"
else
  rm -rf "${REMOTE_DIR}"
  git clone -b "${BRANCH}" "${REPO_URL}" "${REMOTE_DIR}"
  cd "${REMOTE_DIR}"
fi

python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt
mkdir -p cache

if [[ ! -f frontend/frames/barnard/d2/manifest.json ]]; then
  echo "ERROR: official frames missing from repo (frontend/frames/)." >&2
  exit 1
fi

cat > /etc/systemd/system/blinkit.service <<EOF
[Unit]
Description=Blinkit SPHEREx
After=network.target

[Service]
WorkingDirectory=${REMOTE_DIR}
Environment=BLINKIT_DISABLE_DOCS=1
ExecStart=${REMOTE_DIR}/.venv/bin/uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable blinkit
systemctl restart blinkit
sleep 2
curl -sf http://127.0.0.1:8000/api/health

cat > /etc/nginx/sites-available/blinkit <<EOF
server {
    listen 80;
    server_name ${DOMAIN} www.${DOMAIN};

    client_max_body_size 20m;
    proxy_read_timeout 120s;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

ln -sf /etc/nginx/sites-available/blinkit /etc/nginx/sites-enabled/blinkit
nginx -t
systemctl reload nginx

echo
echo "HTTP OK. Now get HTTPS (Certbot will edit Nginx):"
echo "  certbot --nginx -d ${DOMAIN} -d www.${DOMAIN}"
echo
echo "Then open https://${DOMAIN}"
