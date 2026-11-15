# HOLD — local only (gitignored, not on GitHub)

Six Eyes is in the main app. Optional later: Gaia/WISE polish; DR1 cube 102 viz.

## For your friend — pull, new branch, then edit

```bash
git checkout main
git pull origin main
git checkout -b govinda/six-eyes-followup

source .venv/bin/activate
uvicorn backend.app.main:app --port 8000

python -m scripts.six_eyes_lab barnard
python -m scripts.six_eyes_lab eps_ind_b
python -m scripts.six_eyes_lab wise0855
python -m scripts.six_eyes_lab rw_aur
python -m scripts.six_eyes_lab r_dra
```

Then edit → commit → `git push -u origin HEAD` → `gh pr create --base main`
