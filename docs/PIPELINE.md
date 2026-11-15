# How Blinkit connects: frontend ↔ backend ↔ NASA data

One short map of how a click in the browser becomes SPHEREx images on screen.

## Big picture

```
Browser (frontend/)          FastAPI (backend/app/main.py)         Outside
─────────────────            ─────────────────────────────         ────────
Name / RA Dec / FOV    →     /api/resolve, /api/coverage      →   SIMBAD, IRSA
Official target pick   →     /api/frames?target=&band=        →   frontend/frames/…
Any sky position       →     /api/frames?ra=&dec= (job 202)   →   IRSA + AWS S3
Flip / blink / color   ←     static PNGs + manifest.json
Diff / minus / stack   ←     /api/diff, /api/stack (+ files)
Motion proof           ←     /api/proof + Gaia
Six Eyes               ←     frontend/frames/<target>/six_eyes/
Sky map                ←     Aladin Lite (ESA CDN HiPS)
```

The same process serves the API and the website (`uvicorn backend.app.main:app`). Static files live under `frontend/`; JSON APIs under `/api/…`.

## Two ways to get frames

1. **Prepared targets** (Barnard's Star, WISE 0855, ε Ind B, R Dra, RW Aur)  
   Already rendered under `frontend/frames/<target>/d<1–6>/`. The UI loads `manifest.json` and PNGs from disk. Fast; works even if IRSA is slow.

2. **Any RA/Dec**  
   `GET /api/frames?ra=&dec=&band=` starts a background render job (`HTTP 202` + short status), then returns the same shape of manifest when ready. Pixels come from the public AWS copy of SPHEREx (`nasa-irsa-spherex`); search goes through IRSA (SIA first, TAP if needed).

## Backend steps (render path)

| Step | Module | What it does |
|------|--------|----------------|
| Resolve name / PM | `coords.py`, `motion.py` | SIMBAD → RA/Dec; move to ~2026.0 with proper motion |
| Find exposures | `archive.py` | IRSA cone search; group into visits |
| Read pixels | `s3_reader.py` | HTTP range reads of IMAGE/VARIANCE/ZODI/FLAGS (cutout fallback) |
| Clean | `flags.py`, `clean.py` | Mask hardware defects; keep real sources; subtract zodiacal light |
| Align | `align.py`, `coadd.py` | Reproject north-up; inverse-variance visit coadd |
| Products | `render.py`, `diff.py`, `stack.py`, `proof.py` | PNGs, `manifest.json`, diffs, minus-median, stack, Gaia proof |
| Catalogs | `gaia.py`, `wise.py` | Marker overlays for the flipbook |

Details of file layout: [FRAMES_FORMAT.md](FRAMES_FORMAT.md). Measured checks: [VALIDATION.md](VALIDATION.md).

## Frontend steps

| Piece | Role |
|-------|------|
| `js/app.js` | Wires search, sky map, modes, and API calls |
| `js/frames.js` | Loads or polls `/api/frames` |
| `js/flipbook.js` | Images, blink, color composite, minus-median, stack |
| `js/diffview.js` | Visit A/B difference panels |
| `js/proof.js` | Measured shift vs Gaia |
| `js/sixeyes.js` | Deep stack per detector + coarse spectrum |
| `js/urlstate.js` | Keeps `?ra=&dec=&fov=&det=` shareable in the address bar |
| `js/sky.js` | Aladin Lite map (ESA CDN tiles) |

Color composite is built in the browser from visit PNGs (`js/composite.js`). Diff and stack products are made on the server (or pre-rendered for official targets).

## What the user sees vs what is computed

- **Blink / flip** — time-ordered visit images (honest animation, no cross-fade).
- **Color** — early / mid / late visits as RGB (WiseView-style idea, SPHEREx visits).
- **Minus median** — each visit minus the median of all visits (movers stand out).
- **Add visits** — inverse-variance stack (`stack.py`).
- **Difference** — \((B - A - \Delta\mathrm{sky}) / \sqrt{\sigma_A^2 + \sigma_B^2}\).
- **Proof** — centroid shift vs Gaia DR3 prediction.
- **Six Eyes** — one deep image per detector D1–D6 for the same patch.

## Errors the UI is meant to survive

- IRSA / TAP slow or 502 → SIA fallback, then last cached exposure list; friendly “archive side” copy (not raw URLs).
- Missing prepared folder → empty state / job message, not a blank crash.
- Gaia / CatWISE down → overlays empty; flipbook still works.
- Partial visit set → stack/diff only use visits that exist; warnings in the panel when useful.

## Hosting note

Production: Nginx → `uvicorn` on one host (`docs/HOSTING.md`). Official frames stay on disk; random-sky jobs hit IRSA/AWS live.
