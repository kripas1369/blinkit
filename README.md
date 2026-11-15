# Blinkit — SPHEREx flipbook (NASA Space Apps 2026)

**Planet X and SPHEREx:** compare real SPHEREx images of the same patch of sky across visits in a flipbook, with Gaia/CatWISE markers, difference and minus-median views, visit stacks, and motion proofs against Gaia DR3.

Team **Not42** (Kripas Khatiwada & Govinda). Phase 1 tag: `phase1`.

## What it does

- Resolve a name or pick an official demo target; choose SPHEREx detector **D1–D6** and field of view up to **30 arcmin**.
- **Prepared frames** under `frontend/frames/` for five challenge targets (when rendered).
- For any **RA/Dec**, the API can build frames in the background (`HTTP 202` then poll).
- Modes: **Images** (flip/blink), **Minus median**, **Add visits** (stack), **Difference**.
- **Shareable / embeddable URLs** — the address bar carries `ra`, `dec`, `fov`, `det`, and view options. **Share** copies the link for other sites and projects.
- **Six Eyes** — deep stack per detector (D1–D6) with coarse spectrum for official targets (`scripts/six_eyes_lab.py` builds `frontend/frames/<target>/six_eyes/`).

## Shareable URLs (coordinates in the link)

Open a sky position directly (example: Barnard's Star, 11′ FOV, detector 2):

```
http://127.0.0.1:8000/?ra=269.446269&dec=4.768205&fov=11&det=2
```

| Param | Meaning |
|-------|---------|
| `ra`, `dec` | degrees (required for a deep link) |
| `fov` | field of view in arcmin (1–30) |
| `det` | SPHEREx detector 1–6 |
| `mode` | optional: `flip`, `blink`, `diff`, `stack`, `minus` |
| `gaia`, `wise` | optional overlays `0`/`1` |

Embed in another page:

```html
<iframe
  src="https://YOUR_HOST/?ra=269.446269&dec=4.768205&fov=11&det=2"
  title="Blinkit SPHEREx view"
  width="100%" height="640" loading="lazy"></iframe>
```

The UI keeps the URL in sync as you change target/FOV/detector; **Share** copies the current link.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# API + static site (recommended)
uvicorn backend.app.main:app --port 8000
# Open http://localhost:8000 — API docs at /api/docs
```

Static-only (no live jobs): `cd frontend && python3 -m http.server 8000` — only folders that exist under `frontend/frames/` work.

## Host on a VPS

See **[docs/HOSTING.md](docs/HOSTING.md)**. Use `uvicorn … --host 0.0.0.0 --workers 1` behind Nginx. Official targets stay local/fast; if NASA IRSA is down, visitors see a short “archive side” note — not raw 502/TAP URLs.

## Test

```bash
source .venv/bin/activate
python -m pytest backend/tests -q
python -m scripts.check_frames          # audit prepared folders
python -m scripts.phase1_signoff        # B5 automated checks

cd frontend && npm test
```

## Data sources

| Data | Source |
|------|--------|
| SPHEREx discovery | NASA/IPAC [IRSA](https://irsa.ipac.caltech.edu/) (SIA first, TAP fallback) |
| SPHEREx pixels | Public AWS copy `nasa-irsa-spherex` (HTTP range reads); IRSA cutout fallback |
| Gaia DR3 | IRSA TAP `gaia_dr3_source` (ESA archive fallback) |
| CatWISE2020 | IRSA TAP `catwise_2020` |
| Name search | CDS SIMBAD (via astroquery) |
| Sky map | CDS Aladin Lite tiles in the UI |

Stack: Python 3.12+, **astropy**, **astroquery**, **pyvo**, **reproject**, **FastAPI**, vanilla JS frontend.

## Keeping up with new SPHEREx releases

NASA publishes SPHEREx data quickly. Blinkit is built to follow without rewriting the app:

1. **Live discovery** — every search hits IRSA (SIA → TAP). New exposures appear as soon as they are indexed.
2. **Switch collections with one env var** (no code change):
   ```bash
   export SPHEREX_COLLECTIONS=spherex_qr3,spherex_qr3_deep,spherex_dr1,spherex_dr1_deep,spherex_dr2
   uvicorn backend.app.main:app --port 8000
   ```
3. **Re-render** prepared targets (or open any RA/Dec so a background job pulls the latest):
   ```bash
   python -m backend.app.render barnard 2 --out frontend/frames
   ```
4. **UI** — “Data as of …” under the flipbook comes from `GET /api/releases`. If IRSA lists a collection we are not searching yet, the Data panel shows how to enable it.

**Already done once:** when IRSA retired QR2, we moved to QR3 + DR1 (`SPHEREX_COLLECTIONS` / defaults), compared QR2 vs DR1 on S3 (`scripts/compare_qr2_dr1.py`), and documented the differences in [docs/VALIDATION.md](docs/VALIDATION.md). Prepared flipbooks are **snapshots**; random-sky jobs stay **live**.

## Phase 1 status

- **B1–B5 code:** complete. Branch **`phase1-complete`** finished the **30/30** frame set (`scripts/check_frames.py` PASS).
- **Data:** all five targets × D1–D6 under `frontend/frames/` (gitignored). Some Gaia/CatWISE sidecars are empty until IRSA TAP/ESA answers — re-run `python -m scripts.render_missing --sidecars-only --all-existing`.
- Audit: [docs/PHASE1_STATUS.md](docs/PHASE1_STATUS.md). Measurements: [docs/VALIDATION.md](docs/VALIDATION.md). Pipeline: [docs/DATA_FLOW.md](docs/DATA_FLOW.md).

## AI disclosure

Code was ported from our pre-event private practice repository (`wise-blink-practice`) and extended during the hackathon with help from AI coding assistants (Cursor). All validation numbers in `docs/VALIDATION.md` come from scripts and tests run on real IRSA/AWS data, not hand-written estimates.

## Repo layout

- `backend/app/` — archive, S3 reader, render pipeline, Gaia/WISE, diff/stack/proof, FastAPI `main.py`
- `frontend/` — flipbook UI (`js/flipbook.js`, `diffview.js`, `proof.js`)
- `frontend/frames/` — prepared flipbook products (gitignored in full builds; sample targets may be present locally)
- `docs/FRAMES_FORMAT.md` — manifest and sidecar JSON schema
- `scripts/` — `check_frames.py`, `compare_qr2_dr1.py`, `phase1_signoff.py`