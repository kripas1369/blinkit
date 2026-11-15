# Host Blinkit on your own VPS

Hosting on a VPS does **not** break the app. Official targets stay fast (local files). Live RA/Dec jobs still need outbound HTTPS to NASA IRSA, SIMBAD, and (for the map) Aladin CDNs — if IRSA is down, that is NASA’s side, not your VPS.

## 1. Server requirements

- Ubuntu 22.04+ (or similar)
- Python 3.12+
- Outbound HTTPS (IRSA, AWS SPHEREx bucket, SIMBAD, jsDelivr/Aladin)
- ~2 GB RAM recommended (astropy jobs)
- Disk for `cache/` (live cutouts grow)

## 2. Install

### Option A — recommended upload pack (includes official frames)

On your laptop (in the Blinkit repo):

```bash
bash scripts/pack_vps.sh
# → dist/blinkit-vps-YYYYMMDD.tar.gz  (~code + frontend/frames/, no cache/.venv)
scp dist/blinkit-vps-*.tar.gz user@YOUR_VPS:~/
```

On the VPS:

```bash
tar -xzf blinkit-vps-*.tar.gz
cd blinkit-vps-*
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
mkdir -p cache
# Follow DEPLOY.txt in the unpack folder
```

`frontend/frames/` is gitignored, so a plain `git clone` alone will **not** ship Barnard's Star. The pack script copies those ~10 MB of prepared targets.

### Option B — git + copy frames

```bash
git clone <your-repo-url> blinkit
cd blinkit
# copy frames from your machine:
#   rsync -av frontend/frames/ user@YOUR_VPS:/path/to/blinkit/frontend/frames/
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
mkdir -p cache
```

## 3. Run (production)

Bind to all interfaces (not only localhost):

```bash
export BLINKIT_DISABLE_DOCS=1          # hide /api/docs on the public site
# optional: export SPHEREX_COLLECTIONS=spherex_qr3,spherex_qr3_deep,spherex_dr1,spherex_dr1_deep
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

Use **`--workers 1`**. Frame jobs share one in-process queue; multiple workers would duplicate jobs.

## 4. systemd (example)

`/etc/systemd/system/blinkit.service`:

```ini
[Unit]
Description=Blinkit SPHEREx
After=network.target

[Service]
User=www-data
WorkingDirectory=/opt/blinkit
Environment=BLINKIT_DISABLE_DOCS=1
ExecStart=/opt/blinkit/.venv/bin/uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now blinkit
```

## 5. Nginx reverse proxy (HTTPS)

Point your domain at the VPS, then:

```nginx
server {
  listen 443 ssl http2;
  server_name blinkit.example.com;
  # ssl_certificate …;
  # ssl_certificate_key …;

  client_max_body_size 20m;
  proxy_read_timeout 120s;

  location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }
}
```

One origin is enough: FastAPI already serves the frontend and `/api/*`.

## 6. Firewall

- Open **80/443** to the world
- Do **not** expose port 8000 publicly if Nginx proxies it
- Allow outbound **443** (IRSA / SIMBAD / CDNs)

## 7. What visitors see when IRSA fails

Raw TAP/502 strings are rewritten to a short note: Blinkit is fine; NASA IRSA did not answer. Flipbook for prepared targets still works.

## 8. Quick health check

```bash
curl -s https://YOUR_DOMAIN/api/health
# {"ok":true}
```
