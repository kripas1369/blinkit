# Phase 1 status (B1–B5)

Cross-check against `wise-blink-practice/docs/hackathon/{KRIPAS_TASKS,GOVINDA_TASKS}.md` and the practice repo layout. Updated **15 Nov 2026**.

**Summary:** All **code** for B1–B4 is on `main`; B5 **sign-off docs/tools** are done. **Data product:** **10/30** frame folders on disk (IRSA TAP outage blocks the rest). Local git tag `phase1` exists; **not pushed** until `git push origin main phase1`.

---

## Block matrix

| Block | Kripas (plan) | Govinda (plan) | Code on `main` | Data / validation | Overall |
|-------|---------------|----------------|----------------|-------------------|---------|
| **B1** | API, resolve, coverage, URL, coord tab | archive, config, flags, coverage, S3 keys | Done | VALIDATION §1; SIA-first added post-B5 | **Done** |
| **B2** | `/api/frames`, flipbook, player, timeline | clean, align, coadd, render, s3_reader | Done | VALIDATION §2–3; parity `scripts/parity_check.py` | **Done** |
| **B3** | D1–D6 bar, Gaia/CatWISE API, flags, FOV 30′, releases panel | gaia, wise, align check, 30 renders | Done | **10/30** folders; §4 table + QR2/DR1 script | **Partial data** |
| **B4** | diff/proof/stack APIs, 4 flipbook modes, URL | diff, stack, proof, minus-median | Done | Proofs on 10 folders; §5 B4 | **Done (on disk)** |
| **B5** | Manual checks, targets.js, README, `phase1` tag | check_frames, compare_qr2_dr1, docs | Done | §6–7; `phase1_signoff.py` | **Sign-off partial** |

---

## B1 — Find data / API base

| Criterion (plan) | Kripas | Govinda |
|------------------|--------|---------|
| `pytest backend/tests` | 103 passed | same |
| `COLLECTIONS` QR3+DR1, env override | — | `test_b1_archive.py` |
| `/api/health`, `/api/resolve`, `/api/coverage`, `/api/releases` | main.py | archive `releases()` |
| `find_images` + `s3_key` | uses archive | archive + SIA fallback |
| QR2 search 0 rows at Barnard position | — | Confirmed in original B1 run (QR2 dropped from IRSA collections Nov 2026) |
| VALIDATION B1 numbers | — | §1 archive counts |
| SIMBAD resolve, URL state, coord tab | resolve.js, urlstate.js, tests | no frontend edits |
| No cross-ownership violations | backend + frontend B1 scope | no main/frontend |

**Extra (post-plan):** Image search **SIA → TAP → cache** (`6b8f1f0`) for IRSA outages.

---

## B2 — Frames and S3

| Criterion | Kripas | Govinda |
|-----------|--------|---------|
| Barnard D2 plays in flipbook | yes (10 folders) | render pipeline |
| `manifest` fields: release, flag_counts, pixel_source, collections_checked, newest_obs_date | API + FRAMES_FORMAT | render.py |
| S3 vs cutout max diff 0 (3 exposures) | — | §3 + `validation_output/parity_check.txt` |
| S3 bench 3′–30′ | — | §3 table |
| `s3_reader` + cutout fallback | — | `test_s3_reader.py` |
| `test_pipeline.py` | — | passes |

---

## B3 — Overlays and 30 folders

| Criterion | Kripas | Govinda |
|-----------|--------|---------|
| Detector bar D1–D6 | flipbook + index | — |
| Gaia / CatWISE `/api/gaia` `/api/wise` | main.py | write_gaia, write_wise |
| Flag legend, align warning >0.5 px | flags_legend.js, manifest | align_check.py |
| FOV ≤30′, releases panel | urlstate, app.js | — |
| 30 folders + gaia.json + wise.json each | **10 only** | render batch **paused** |
| target × detector table in VALIDATION | partial table §4 | full table when 30 exist |
| QR2 vs DR1 on AWS | — | `scripts/compare_qr2_dr1.py` §4 |
| `pixel_source = aws-s3` | all 10 folders | check_frames |
| `test_wise.py` | — | passes |

**Gap:** wise0855, rw_aur, r_dra (6× each) + eps_ind_b D5–D6 = **20 folders**.

---

## B4 — Add / subtract visits

| Criterion | Kripas | Govinda |
|-----------|--------|---------|
| `/api/diff`, `/api/proof`, `/api/stack?visits=` | main.py | writers |
| AFTER_RENDER steps | wired | diff, stack, proof, minus_median |
| Modes: Images, Minus median, Add visits, Difference | flipbook.js | — |
| Barnard shift within 0.5 px | proof UI | §5: 0.05 px D2 |
| Stack noise ≈ √N | stack API | §5: 1.73× vs √3 |
| Minus-median sky offset fix | diffview | `a50ea36` |
| Files in all 30 folders | **10 only** | sidecars on rendered set |
| `test_diff.py`, `test_b4_api.py`, frontend diff_proof | pass | Govinda tests |

---

## B5 — Sign-off

| Criterion | Kripas | Govinda |
|-----------|--------|---------|
| `scripts/check_frames.py` | uses in signoff | authored; §6 |
| Barnard ~1.7 px + Gaia | targets.js + §7 | proof |
| WISE / RW Aur / R Dra variable checks | **blocked** (no frames) | — |
| Eps Ind B motion | D2–D4 pass; D1 disagree | proof |
| Random job / empty sky | pytest + §7 | — |
| `targets.js` ratings | updated from proof | — |
| README + AI disclosure | README.md | — |
| `frame_notes.py` measured | updated 10 targets | plan item |
| `phase1` tag | local `phase1` | plan wants GitHub push |
| `check_frames` 30/30 | **10/10** | Govinda done when |

---

## Practice repo parity (read-only)

| Practice module / feature | In `blinkit` |
|---------------------------|--------------|
| archive, render, diff, proof, measure, gaia | yes |
| s3_reader, stack, wise, align_check | yes (stack/wise split for hackathon) |
| lightcurve, spectrum, pixels, spots, ask, eclipse | **Phase 2+** (removed from Phase 1 main) |
| 30 folders under `frontend/frames` | practice has QR2-era set; blinkit has 10 DR1/QR3 |

---

## What “Phase 1 complete” still needs

1. **Render** 20 missing folders when IRSA TAP allows Gaia/CatWISE post-steps.
2. **`python -m scripts.check_frames`** → 30/30 PASS.
3. **VALIDATION §7** — tick WISE / RW Aur / R Dra rows after browser check.
4. **`git push origin main`** and **`git push origin phase1`**.
5. Optional: amend tag message if you want tag only after 30/30 (current tag = code sign-off).

---

## Quick commands

```bash
python -m scripts.phase1_signoff
python -m scripts.check_frames
python -m pytest backend/tests -q
cd frontend && npm test
```

See also: [VALIDATION.md](VALIDATION.md), [DATA_FLOW.md](DATA_FLOW.md), [FRAMES_FORMAT.md](FRAMES_FORMAT.md).