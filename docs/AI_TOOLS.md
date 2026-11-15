# AI tools we used (and what we still checked by hand)

Team **Not42** built Blinkit for NASA Space Apps 2026. Coding help came mainly from **Cursor** (AI pair-programming in the editor). Practice and research lived first in our private repo `wise-blink-practice`, then landed here.

AI did **not** invent the science claims. Numbers in [VALIDATION.md](VALIDATION.md) come from scripts and tests on real IRSA / AWS SPHEREx data.

## Where AI helped most

| Area | What AI assisted with | What we verified |
|------|----------------------|------------------|
| **Testing** | Drafting and extending `backend/tests/` (API, archive, diff, stack, coords, SIA fallback, Gaia fallback) | `pytest backend/tests`; `scripts/check_frames.py` (30/30 prepared folders); `scripts/phase1_signoff.py`; frontend `npm test` |
| **Rendering** | Wiring FastAPI jobs, PNG/FITS product paths, flipbook modes, color composite in the browser | Open Barnard + each mode on https://blinkit.study / local; re-render with `backend.app.render` when releases change |
| **Data filtering** | Defect bitmasks (`flags.py`), visit grouping, SIA→TAP failover, friendly public error text | Flagged-pixel overlays; empty-archive and IRSA-down paths; SOURCE bit kept unmasked so real stars stay |
| **Math** | Difference \(z\)-maps, inverse-variance weights, minus-median, noise ratios in Six Eyes | Spot-check formulas against `diff.py` / `stack.py`; compare stack noise to \(1/\sqrt{N}\) in validation notes |
| **Coordinates** | North-up WCS grid, proper motion to ~2026.0, pixel↔sky click, shareable `?ra=&dec=` URLs | Gaia alignment offsets on prepared targets; Barnard deep-link; FOV clamp 1–30′ |
| **Error handling** | HTTP 202 job polling, PIXSRC provenance (`aws-s3` / `irsa-cutout`), empty Gaia sidecars, Aladin tile host fix (ESA CDN) | Kill IRSA or bad HiPS host in testing; confirm UI still explains the failure |

## What we did *not* leave to AI alone

- Choosing official demo targets and default (Barnard's Star).
- Deciding which IRSA collections to search (`SPHEREX_COLLECTIONS` / QR3 + DR1).
- Reading mission and citizen-science papers (see [WHAT_WE_BUILT.md](WHAT_WE_BUILT.md)).
- Deploying to the VPS (git pull + systemd + Nginx + Let's Encrypt for blinkit.study).
- Final publish cleanup: dead UI removed, docs trimmed to what judges and users need.

## Honest summary for submission

> We used AI coding assistants (Cursor) to move faster on plumbing, tests, and UI. The pipeline math, archive behavior, and validation numbers were run and checked by the team on real SPHEREx data.
