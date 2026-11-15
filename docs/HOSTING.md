# Host Blinkit on your own VPS

Hosting on a VPS does **not** break the app. Official targets stay fast (local files). Live RA/Dec jobs still need outbound HTTPS to NASA IRSA, SIMBAD, and (for the map) Aladin CDNs — if IRSA is down, that is NASA’s side, not your VPS.

## 1. Server requirements

- Ubuntu 22.04+ (or similar)
- Python 3.12+
- Outbound HTTPS (IRSA, AWS SPHEREx bucket, SIMBAD, jsDelivr/Aladin)
- ~2 GB RAM recommended (astropy jobs)
- Disk for `cache/` (live cutouts grow)

## 2. Install

### Option A — GitHub only (recommended)

Official frames are in the repo. On the VPS:

```bash
git clone -b phase1-complete https://github.com/kripas1369/blinkit.git /opt/blinkit
cd /opt/blinkit
bash scripts/vps_git_setup.sh
certbot --nginx -d blinkit.study -d www.blinkit.study
```

Or one shot (after the script is on `phase1-complete`):

```bash
curl -fsSL https://raw.githubusercontent.com/kripas1369/blinkit/phase1-complete/scripts/vps_git_setup.sh | bash
certbot --nginx -d blinkit.study -d www.blinkit.study
```

### Option B — upload pack (optional)

```bash
bash scripts/pack_vps.sh
scp dist/blinkit-vps-*.tar.gz user@YOUR_VPS:~/
```

Then unpack under `/opt/blinkit` and follow `DEPLOY.txt`.

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

## 9. Primary + AWS backup (Team Not42)

| Host | Role |
|------|------|
| `blinkit.study` | Primary VPS |
| `aws.blinkit.study` | Backup on AWS EC2 (same repo, `DOMAIN=aws.blinkit.study`) |

After each `git push` to `phase1-complete`, run on **both** servers:

```bash
cd /opt/blinkit && git pull origin phase1-complete && sudo systemctl restart blinkit
```
