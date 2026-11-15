# Blinkit — SPHEREx flipbook (NASA Space Apps 2026)

Compare real SPHEREx visits of the same sky in a flipbook: blink, color, minus-median, difference, visit stack, and Gaia motion proof.

**Team Not42** (Kripas Khatiwada & Govinda) · Branch: `phase1-complete`

| | URL |
|---|-----|
| **Live (primary)** | [https://blinkit.study](https://blinkit.study) |
| **Live (AWS backup)** | [https://aws.blinkit.study](https://aws.blinkit.study) |

Inspired by [WiseView](http://byw.tools/wiseview) (WISE blink tool). Built for SPHEREx Level-2 from NASA IRSA / AWS. See [docs/WHAT_WE_BUILT.md](docs/WHAT_WE_BUILT.md).

## What you can do

- Open an official demo target (default: Barnard's Star) or any RA/Dec.
- Pick detector **D1–D6** and FOV up to **30′**.
- Modes: **Images** (flip/blink), **Color**, **Minus median**, **Add visits**, **Difference**.
- **Six Eyes** — deep stack per detector + coarse spectrum (official targets).
- **Share** — the address bar keeps `ra`, `dec`, `fov`, `det` for links and embeds.

Example deep link:

```
https://blinkit.study/?ra=269.446269&dec=4.768205&fov=11&det=2
```

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.app.main:app --port 8000
# http://localhost:8000  ·  API docs: /api/docs
```

## Test

```bash
source .venv/bin/activate
python -m pytest backend/tests -q
python -m scripts.check_frames
python -m scripts.phase1_signoff
cd frontend && npm test
```

## Docs (keep these)

| Doc | What it is |
|-----|------------|
| [docs/PIPELINE.md](docs/PIPELINE.md) | How frontend, backend, and NASA data connect |
| [docs/AI_TOOLS.md](docs/AI_TOOLS.md) | Where we used AI (tests, render, filters, math, coords, errors) |
| [docs/WHAT_WE_BUILT.md](docs/WHAT_WE_BUILT.md) | New methods, WiseView + paper refs, done vs not done |
| [docs/FRAMES_FORMAT.md](docs/FRAMES_FORMAT.md) | Manifest / sidecar layout |
| [docs/VALIDATION.md](docs/VALIDATION.md) | Measured checks on real data |
| [docs/HOSTING.md](docs/HOSTING.md) | VPS / Nginx / deploy |
| [docs/SUBMISSION_30S.md](docs/SUBMISSION_30S.md) | Short pitch |

## Data sources

| Data | Source |
|------|--------|
| SPHEREx discovery | NASA/IPAC [IRSA](https://irsa.ipac.caltech.edu/) (SIA → TAP) |
| SPHEREx pixels | Public AWS `nasa-irsa-spherex` (range reads); IRSA cutout fallback |
| Gaia DR3 | IRSA TAP (ESA fallback) |
| CatWISE2020 | IRSA TAP |
| Names | CDS SIMBAD |
| Sky map | Aladin Lite (ESA CDN HiPS) |

Stack: Python 3.12+, astropy, astroquery, pyvo, reproject, FastAPI, vanilla JS.

New SPHEREx releases: set `SPHEREX_COLLECTIONS=…` and re-render or open any RA/Dec. Details in [VALIDATION.md](docs/VALIDATION.md).

## Repo layout

- `backend/app/` — archive, S3 reader, render, diff/stack/proof, FastAPI
- `frontend/` — flipbook UI
- `frontend/frames/` — prepared products for official targets
- `scripts/` — `check_frames.py`, `phase1_signoff.py`, `six_eyes_lab.py`, …
