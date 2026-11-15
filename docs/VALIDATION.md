# Validation Notes

Real checks, measurements, and test results from working with IRSA and SPHEREx S3 data.

## 1. Archive Access and Data Discovery (B1)

We verified discovery queries against the SPHEREx collections on IRSA TAP (`spherex_dr1`, `spherex_dr1_deep`, `spherex_qr3`, `spherex_qr3_deep`).
The full archive holds 1,628,230 images taken between May 2025 and October 2026.
For Barnard's Star, our cone search finds 363 exposures across all 6 detectors (roughly 60 exposures per band from 0.75 to 5.00 um).
SIA2 queries give valid public AWS S3 keys for all level-2 images, readable directly over HTTPS without credentials.

**Plan checks (Govinda B1 / Kripas B1 review):**
- `spherex_qr2` is no longer in `config.COLLECTIONS` (IRSA listing checked 13 Nov 2026); a QR2-only search at the Barnard position returns **0 rows** (expected).
- `SPHEREX_COLLECTIONS` env override is tested in `test_b1_archive.py`.
- `archive.releases()` backs `GET /api/releases` (Kripas B1).
- Live search prefers **SIA** then TAP (`archive.find_images`). See [PIPELINE.md](PIPELINE.md).

## 2. Visit Stacking and Cleaning (B2 Part A)

Inverse-variance coadd of Barnard's Star detector 2, from `frontend/frames/barnard/d2/manifest.json` (rendered 14 Nov 2026):
- Visit 0 (2025-08-26, DR1): 8 of 18 exposures stacked, 1.4281 um, 3.2% flagged bad, 0.2% no-value.
- Visit 1 (2026-03-16, DR1): 8 of 18 exposures stacked, 1.4016 um, 2.6% flagged bad, 0.5% no-value.
- Visit 2 (2026-08-21, QR3): 8 of 25 exposures stacked, 1.4253 um, 3.6% flagged bad, 0.4% no-value.

Each visit produces a 29x29 north-up FITS file, a contrast-scaled PNG, a defect overlay, and manifest.json.

## 3. S3 Range Reader and Parity (B2 Part B)

Instead of downloading the whole Level-2 file (62,665,920 bytes for the exposure below), the S3 reader fetches the headers plus only the detector rows that cover the box, in 12 HTTP range requests. It decodes the RICE_1 compressed FLAGS rows with astropy's Rice1 and shifts CRPIX to the box origin.

Parity with the IRSA cutout service (`scripts/parity_check.py`, output in `docs/validation_output/parity_check.txt`, run 14 Nov 2026): one Barnard D2 exposure per visit, 3-arcmin box, lined up by each file's own CRPIX.
- 2025W35_1A_0444_1D2 (DR1): IMAGE, VARIANCE, ZODI max difference 0.0, same NaN pixels, 0 of 841 FLAGS differ, wavelength 1.2384 um on both.
- 2026W12_1A_0311_1D2 (DR1): IMAGE, VARIANCE, ZODI max difference 0.0, same NaN pixels, 0 of 841 FLAGS differ, wavelength 1.3155 um on both.
- 2026W34_2A_0264_2D2 (QR3): IMAGE, VARIANCE, ZODI max difference 0.0, same NaN pixels, 0 of 841 FLAGS differ, wavelength 1.5389 um on both.

S3 timing for one exposure (2026W12_1A_0311_1D2) by field of view (`scripts/bench_s3.py`, output in `docs/validation_output/bench_s3.txt`). Run from Nepal over home internet to AWS us-east-1; bytes are counted from the range reads. Times vary between runs (an earlier run gave 5.85, 6.64, 9.74 and 16.04 s).

| FOV | Box (px) | Time (s) | Downloaded (MB) |
|---|---|---|---|
| 3 arcmin | 29x29 | 5.55 | 1.00 |
| 10 arcmin | 99x99 | 6.60 | 3.03 |
| 20 arcmin | 195x195 | 8.58 | 5.80 |
| 30 arcmin | 293x293 | 10.79 | 8.62 |

A single IRSA cutout of the 3-arcmin box for the same exposure took 19 s and returned 4 MB (one measurement, 14 Nov 2026).
Every row read from S3 is the full 2040-pixel detector width, so larger boxes download more; the UI shows a "slower" note above 15 arcmin.

Provenance: FITS files record PIXSRC ("aws-s3" or "irsa-cutout"). The manifest labels a visit "aws-s3" only when all its exposures came from S3, "irsa-cutout" when all came from IRSA, and "mixed" otherwise. If an S3 read fails, the loader logs a warning and falls back to the IRSA cutout, with at most 3 IRSA requests at a time.

## 4. Astrometry, Alignments, and Target Coverage (B3)

Gaia DR3 positions (epoch 2016.0) and CatWISE2020 positions (epoch 2015.4) are moved to each visit date using proper motion.

Alignment check: for slow-moving Gaia stars (G 10 to 17 mag, proper motion < 100 mas/yr) we find the brightest pixel in a 5x5 window around the predicted position, take a 3x3 centroid, and drop matches 2.5 px or farther away. If the median offset of a visit is above 0.50 px, the manifest gets a "possible misalignment" note. No rendered visit has that note.

Target render status (all 30 folders, `scripts/check_frames.py` 15 Nov 2026, all pixel_source = aws-s3).
Full table: `docs/validation_output/check_frames_30.txt`. Summary:

| Target | Detectors | Notes |
|---|---|---|
| Barnard's Star | D1–D6 | Align 0.31–0.43 px; Gaia motion agrees on D1–D5 |
| Epsilon Indi B | D1–D6 | D1–D4 have Gaia proofs; D5–D6 rendered with empty Gaia (TAP/ESA down) |
| WISE 0855 | D1–D6 | All rendered via SIA+S3; Gaia/CatWISE empty pending catalogue |
| RW Aur | D1–D6 | Three visits each; Gaia empty pending catalogue |
| R Dra | D1–D6 | Crowded deep field; up to five visits; Gaia empty pending catalogue |

Re-run `python -m scripts.render_missing --sidecars-only --all-existing` when IRSA TAP or ESA Gaia answers, to fill overlays and refresh proofs.

CatWISE target matching:
In `wise.json`, `target_match` is null for both rendered targets, for different physical reasons:
- Barnard's Star is far too bright for CatWISE point-source fitting (optical V ~ 9.5, WISE W1 ~ 6.8 mag, well past the ~8 mag saturation threshold of the detector). Because it heavily saturates the profiles, CatWISE simply omits it from the point source catalog.
- Epsilon Indi B is a tight, cold T-dwarf binary (T1 + T6). The automated CatWISE source extractor fragmented the blended glow into multiple marginal detections with erratic fitted motions, so none of the extracted entries fell within our 3-arcsec target match circle.

QR2 vs DR1 comparison on AWS S3 (`scripts/compare_qr2_dr1.py`, output in `docs/validation_output/qr2_vs_dr1.txt`, run 15 Nov 2026):
We pulled 5 Barnard D2 exposures from both `qr2/level2/` and `dr1/level2/` on S3 and compared the 3-arcmin boxes:
- **Observation Time**: `MJD-AVG` is identical down to 0.0000 s across all 5 pairs.
- **WCS Pointing**: WCS centers differ by 0.041 to 1.850 arcsec for exposures 0146_1 through 0146_4. This reflects the improved astrometric calibration in DR1 (pipeline `v27-2026-230`) compared to QR2 (`v20-2025-269`). Exposure 0444_1 shifted by 707.243 arcsec (~11.8 arcmin) because IPAC re-solved and repointed the field entirely in DR1 (`l2b_retry`).
- **Flagged Pixels**: DR1 flags slightly more pixels as bad (5.4% to 12.0% in DR1 vs 4.6% to 8.3% in QR2). The updated v27 bad-pixel masks catch more cosmic ray trails and noisy edge pixels.
- **Pixel Brightness**: DR1 values are systematically 0.010 to 0.015 MJy/sr lower than QR2 across all 5 exposures. This comes from an improved zodiacal light (`ZODI`) subtraction model in DR1.

Practice frames vs now: the practice repo's Barnard D2 frames (made 31 Oct 2026) have the same 3 visits and wavelengths. Visit 0 is 2.6% flagged there and 3.2% now; visits 1 and 2 match (2.6% and 3.6%). The cause of the visit 0 difference has not been checked.

## 5. Add and Subtract Visits (B4)

Pairwise differencing, minus-median frames (WiseView style), and inverse-variance visit coaddition (`write_diff`, `write_minus_median`, `write_stack`, `write_proof`, run 14 Nov 2026):

### Astrometric Proper Motion Proofs (vs Gaia DR3)
Proper motion shift measured from first to last visit compared against Gaia DR3 predictions (limit: agreement within 0.50 px):
- **Barnard's Star Detector 2**:
  - Visits: 2025-08-26 to 2026-08-21 (360.2 days span).
  - Gaia expected shift: 1.67 px.
  - Measured shift: 1.61 px (difference: 0.05 px, direction diff: 0.5°, status: `agrees`).
- **Epsilon Indi B Detector 2**:
  - Visits: 2025-04-27 to 2026-10-01 (521.9 days span).
  - Gaia expected shift: 1.09 px.
  - Measured shift: 0.98 px (difference: 0.20 px, direction diff: 8.9°, status: `agrees`).
- **Other rendered detectors**:
  - Barnard D1: measured 1.57 px vs Gaia 1.66 px (diff 0.18 px, `agrees`).
  - Barnard D3: measured 1.60 px vs Gaia 1.68 px (diff 0.10 px, `agrees`).
  - Barnard D4: measured 1.64 px vs Gaia 1.66 px (diff 0.10 px, `agrees`).
  - Barnard D5: measured 1.51 px vs Gaia 1.67 px (diff 0.18 px, `agrees`).
  - Barnard D6: not measurable (proof.py found no usable centre; the cause has not been checked).
  - Eps Ind B D3: measured 1.02 px vs Gaia 1.06 px (diff 0.12 px, `agrees`).
  - Eps Ind B D4: measured 0.65 px vs Gaia 0.75 px (diff 0.10 px, `agrees`).
  - Eps Ind B D1: disagrees: measured 0.59 px pointing the other way vs Gaia 0.75 px (diff 1.29 px). The brown dwarf is too faint at 0.75–1.1 um for a reliable centroid.
  - WISE 0855: not yet rendered.

### Visit Coaddition Noise Reduction
Inverse-variance coaddition using `coadd.coadd` on `epoch<i>.fits`:
- **Barnard D2** (3 visits, 24 exposures): single-visit noise 0.0108 MJy/sr, stack noise 0.0062 MJy/sr, noise ratio gain **1.73x** (theory: sqrt(3) ≈ 1.732).
- **Eps Ind B D2** (5 visits, 39 exposures): single-visit noise 0.0065 MJy/sr, stack noise 0.0030 MJy/sr, noise ratio gain **2.18x** (theory: sqrt(5) ≈ 2.236).
- **Eps Ind B D3** (4 visits, 32 exposures): single-visit noise 0.0058 MJy/sr, stack noise 0.0029 MJy/sr, noise ratio gain **2.02x** (theory: sqrt(4) = 2.000).
- Synthetic coaddition test (`test_stack.py`): 4-frame coadd drops Gaussian noise standard deviation from 1.000 to 0.501 (gain 1.996x vs theoretical sqrt(4) = 2.000).

### Minus-Median Frames
Each visit's overall sky offset from the median (the median of visit − median over good pixels) is removed before dividing by sigma, just as the pairwise differences do. Without this step, Eps Ind B D2 visit 4 (the QR3 visit) sat 0.0169 MJy/sr (2.6 sigma) below the median everywhere and its minus-median frame became one flat washed-out colour. Measured offsets (MJy/sr):
- Eps Ind B D2: +0.0022, +0.0006, +0.0003, 0.0, −0.0169
- Eps Ind B D3: −0.0006, +0.0084, +0.0001, −0.0051
- Barnard D2: 0.0 for all 3 visits.
Each frame's offset is recorded as `sky_change` in `diff.json`.

## 6. Pipeline and Frame Audit (B5)

Output from `scripts/check_frames.py` (15 Nov 2026, **30/30**, saved in `docs/validation_output/check_frames_30.txt`):

```text
ALL CHECKS PASSED: 30 folders verified compliant with FRAMES_FORMAT.md (all pixel_source = aws-s3).
```

Earlier 10-folder audit kept in `docs/validation_output/check_frames.txt`.

## 7. Phase 1 sign-off (B5, 15 Nov 2026) — branch `phase1-complete`

Automated: `check_frames` **30/30 PASS**, `phase1_signoff`, backend **105** pytest, frontend npm tests.

Rendered with **SIA + AWS S3** (`scripts/render_missing.py`) while IRSA TAP was returning 502/timeouts. Gaia/CatWISE: barnard + eps D1–D4 keep earlier overlays; **20 folders** have empty `gaia.json` / mostly empty `wise.json` with an `unavailable` note — re-fill with `--sidecars-only` when catalogues answer.

### Prepared-target checks (Kripas)

| Check | Status | Evidence |
|---|---|---|
| Barnard's Star walks ~1.7 px; Gaia marker tracks | **Pass (D2)** | 1.61 vs 1.67 px; D1–D5 agree; D6 not measurable |
| WISE 0855 faint D1–D3, visible D5–D6 | **Frames ready** | All 6 detectors on disk; visual confirm in browser (D5–D6) |
| Epsilon Indi B shift vs Gaia | **Pass (D2–D4)** | D1 disagrees (faint); D5–D6 need Gaia refill |
| RW Aur / R Dra brightness between visits | **Frames ready** | Match `wl_target_um` in browser before calling variability |
| Random RA/Dec job | **Pass (API)** | pytest + earlier SIA job at 150.1°, +2.2° |
| Empty position → no-data | **Pass** | API 404 + UI `none` |
| `check_frames.py` | **Pass** | **30/30** |
| Every frame `pixel_source = aws-s3` | **Pass** | All 30 |

### Still soft (honest)

- [ ] Browser pass of WISE D5–D6 and RW Aur / R Dra variables (human eyes).
- [ ] Re-run Gaia/CatWISE sidecars when TAP or ESA answers; refresh proofs for the 20 empty-overlay folders.
- [ ] Merge `phase1-complete` → `main` and move tag if desired.
