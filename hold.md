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

## For your friend (Govinda) — pull, branch, then edit

Do **not** commit directly on `main`. Work on a new branch and open a PR.

```bash
cd /path/to/blinkit
git checkout main
git pull origin main

# New branch for his edits (pick a clear name)
git checkout -b govinda/six-eyes-followup

source .venv/bin/activate
uvicorn backend.app.main:app --port 8000
```

Rebuild Six Eyes products locally (frames are gitignored — each machine needs this once):

```bash
python -m scripts.six_eyes_lab barnard
python -m scripts.six_eyes_lab eps_ind_b
python -m scripts.six_eyes_lab wise0855
python -m scripts.six_eyes_lab rw_aur
python -m scripts.six_eyes_lab r_dra
```

Check: official target → scroll to **Six Eyes** → tap an eye for the large card.

When he has code changes:

```bash
git add -A
git status
git commit -m "Describe why the change helps"
git push -u origin HEAD
gh pr create --base main --title "Short title" --body "## Summary
- …

## Test plan
- [ ] Six Eyes loads for all 5 targets
- [ ] Flipbook still works
"
```

Optional: refill empty Gaia/WISE sidecars when IRSA/ESA is up:

```bash
python -m scripts.render_missing --sidecars-only --all-existing
```
