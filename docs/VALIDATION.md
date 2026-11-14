# Validation Notes

Live sanity checks against NASA IRSA and SPHEREx archives to ensure real data flows cleanly through the pipeline before downstream processing.

---

## B1: Data Discovery & Access

### Active Collections & The Retired QR2
Querying the deprecated `spherex_qr2` returns **0 rows**. The active mission data is split across four collections: `spherex_dr1`, `spherex_dr1_deep`, `spherex_qr3`, and `spherex_qr3_deep`. Across these collections, the archive hosts **1,628,230 images** spanning May 2025 to October 2026 (`MJD 60789.75` to `61318.00`).

### Barnard's Star Ground Truth
A cone search centered on Barnard’s Star (propagated with proper motion to 2026) finds **363 real exposures** evenly distributed across all six detectors (~60 frames per band, covering 0.75 to 5.00 µm).

### Direct S3 Cloud Access
While the TAP `cloud_access` column is currently blank, our SIA2 fallback resolves valid AWS S3 keys for 100% of images. Each file is directly readable over HTTPS from the public bucket:
`https://nasa-irsa-spherex.s3.us-east-1.amazonaws.com/dr1/level2/2025W33_2C/l2b-v27-2026-228/6/level2_2025W33_2C_0321_1D6_spx_l2b-v27-2026-228.fits`

---

## B2: Frame Cleaning & Visit Stacking (Part A)

### Barnard's Star D2 Visit Stacking
Generated production flipbook frames across three distinct observation epochs using inverse-variance coaddition (`render barnard 2`):
* **Visit 0 (2025-08-26):** 8 of 18 exposures stacked, $\lambda = 1.4281\,\mu\text{m}$, 3.2% flagged, 0.2% no value (DR1 release).
* **Visit 1 (2026-03-17):** 8 of 18 exposures stacked, $\lambda = 1.4016\,\mu\text{m}$, 2.6% flagged, 0.5% no value (DR1 release).
* **Visit 2 (2026-08-22):** 8 of 25 exposures stacked, $\lambda = 1.4253\,\mu\text{m}$, 3.6% flagged, 0.4% no value (QR3 release).

### Manifest Schema & Pixel Products
Each visit generates a North-up $29\times29$ pixel science FITS, a contrast-scaled RGBA PNG, and a flagged defect overlay. Top-level `manifest.json` tracks `collections_checked` and `newest_obs_date` (`2026-09-22 15:05 UTC`), while each frame records individual `flag_counts`, `release`, and `pixel_source`.
