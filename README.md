# Blinkit — SPHEREx flipbook (NASA Space Apps 2026)

**Planet X and SPHEREx:** compare real SPHEREx images of the same patch of sky across visits in a flipbook, with Gaia/CatWISE markers, difference and minus-median views, visit stacks, and motion proofs against Gaia DR3.

Team **Not42** (Kripas Khatiwada & Govinda). Phase 1 tag: `phase1`.

## What it does

- Resolve a name or pick an official demo target; choose SPHEREx detector **D1–D6** and field of view up to **30 arcmin**.
- **Prepared frames** under `frontend/frames/` for five challenge targets (when rendered).
- For any **RA/Dec**, the API can build frames in the background (`HTTP 202` then poll).
- Modes: **Images** (flip/blink), **Minus median**, **Add visits** (stack), **Difference**.

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
| Gaia DR3 | IRSA TAP `gaiadr3.gaia_source` |
| CatWISE2020 | IRSA TAP `catwise_2020` |
| Name search | CDS SIMBAD (via astroquery) |
| Sky map | CDS Aladin Lite tiles in the UI |

Stack: Python 3.12+, **astropy**, **astroquery**, **pyvo**, **reproject**, **FastAPI**, vanilla JS frontend.

## Phase 1 status

- Pipeline B1–B4: code complete on `main`. See [docs/DATA_FLOW.md](docs/DATA_FLOW.md) and [docs/VALIDATION.md](docs/VALIDATION.md).
- **10 of 30** target/detector frame folders on disk (barnard D1–D6, epsilon Indi B D1–D4) as of 15 Nov 2026; remaining renders blocked when IRSA TAP is down (image search uses SIA when possible).

## AI disclosure

Code was ported from our pre-event private practice repository (`wise-blink-practice`) and extended during the hackathon with help from AI coding assistants (Cursor). All validation numbers in `docs/VALIDATION.md` come from scripts and tests run on real IRSA/AWS data, not hand-written estimates.

## Repo layout

- `backend/app/` — archive, S3 reader, render pipeline, Gaia/WISE, diff/stack/proof, FastAPI `main.py`
- `frontend/` — flipbook UI (`js/flipbook.js`, `diffview.js`, `proof.js`)
- `frontend/frames/` — prepared flipbook products (gitignored in full builds; sample targets may be present locally)
- `docs/FRAMES_FORMAT.md` — manifest and sidecar JSON schema
- `scripts/` — `check_frames.py`, `compare_qr2_dr1.py`, `phase1_signoff.py`