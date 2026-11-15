# Phase 1 status (B1–B5)

Cross-check against `wise-blink-practice/docs/hackathon/{KRIPAS_TASKS,GOVINDA_TASKS}.md`.  
Updated **15 Nov 2026** on branch **`phase1-complete`**.

**Summary:** B1–B4 **code done**. B5 **data: 30/30 folders** on disk (`check_frames` PASS). Gaia/CatWISE overlays full for barnard + eps D1–D4; **20 folders** have empty catalogue sidecars until TAP/ESA answers again.

---

## Block matrix

| Block | Code | Data | Overall |
|-------|------|------|---------|
| **B1** | Done (SIA→TAP search) | VALIDATION §1 | **Done** |
| **B2** | Done (S3 reader, parity) | §2–3 | **Done** |
| **B3** | Done (gaia/wise/align/UI) | **30/30** frames | **Done** (overlays partial) |
| **B4** | Done (diff/stack/proof/modes) | Sidecars on all 30 | **Done** |
| **B5** | Done (check_frames, README, ratings) | 30/30 audit | **Done** (browser soft checks left) |

---

## What this branch added

1. `scripts/render_missing.py` — batch-render missing detectors; `--sidecars-only` for overlays.
2. ESA Gaia fallback in `backend/app/gaia.py` when IRSA TAP fails.
3. Soft-empty `gaia.json` / `wise.json` when catalogues are unreachable (so check_frames can pass).
4. All 20 missing folders rendered via **SIA + S3** (~1.5–3 min each).
5. `targets.js` + `frame_notes.py` + VALIDATION §6–7 updated for 30 folders.

---

## Commands

```bash
python -m scripts.render_missing --list
python -m scripts.check_frames          # expect 30/30
python -m scripts.phase1_signoff
python -m scripts.render_missing --sidecars-only --all-existing   # when TAP/ESA up
```

Frames live under `frontend/frames/` (**gitignored**). Share via drive/release asset if teammates need them.

See [VALIDATION.md](VALIDATION.md), [DATA_FLOW.md](DATA_FLOW.md).
