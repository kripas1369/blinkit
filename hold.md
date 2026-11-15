# HOLD — remaining (not blocking)

Six Eyes (per-detector deep + coarse spectrum) is **integrated in the main app**. Isolated `/lab/` pages were removed.

## Still optional later

### Gaia / WISE overlay polish
NASA hint: overlay Gaia / WISE. Core already exists (markers, map catalogs, proof). Optional polish:
1. Fill empty Gaia/CatWISE sidecars when TAP/ESA is up (`python -m scripts.render_missing --sidecars-only --all-existing`).
2. Click marker → ID + proper motion (pm) card.
3. Gaia pm arrow vs SPHEREx epochs on the flipbook.

### Lab 2 / 102-channel cube (not shipped)
DR1 All-Sky Cube drill-through was researched (`docs/RESEARCH_HOLD.md`) but the separate cube lab page was removed. Revisit only if you want true 102-point viz in-app.

## Rebuild Six Eyes products (friend / local)

```bash
source .venv/bin/activate
python -m scripts.six_eyes_lab barnard
python -m scripts.six_eyes_lab eps_ind_b
python -m scripts.six_eyes_lab wise0855
python -m scripts.six_eyes_lab rw_aur
python -m scripts.six_eyes_lab r_dra
```

Writes `frontend/frames/<target>/six_eyes/` (gitignored frames — each machine needs this once).
