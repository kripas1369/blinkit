# Validation Notes

Real checks, measurements, and test results from working with IRSA and SPHEREx S3 data.

## 1. Archive Access and Data Discovery (B1)

We verified discovery queries against the SPHEREx collections on IRSA TAP (spherex_dr1, spherex_dr1_deep, spherex_qr3, spherex_qr3_deep).
The full archive holds 1,628,230 images taken between May 2025 and October 2026.
For Barnard's Star, our cone search finds 363 exposures across all 6 detectors (roughly 60 exposures per band from 0.75 to 5.00 um).
SIA2 queries give valid public AWS S3 keys for all level-2 images, readable directly over HTTPS without credentials.

## 2. Visit Stacking and Cleaning (B2 Part A)

We tested inverse-variance coaddition on Barnard's Star detector 2 across its three visits:
- Visit 0 (2025-08-26): 8 exposures stacked, 1.43 um, 3.2% flagged bad, 0.2% no-value.
- Visit 1 (2026-03-17): 8 exposures stacked, 1.40 um, 2.6% flagged bad, 0.5% no-value.
- Visit 2 (2026-08-22): 8 exposures stacked, 1.43 um, 3.6% flagged bad, 0.4% no-value.

Each visit produces a 29x29 north-up FITS file, a contrast-scaled PNG, a defect overlay, and manifest.json.

## 3. S3 Range Reader and Parity (B2 Part B)

Instead of downloading the full 61.6 MB file, the S3 reader fetches only the rows covering our field of view (~120 KB for a 3-arcmin stamp).
It reads Level-2 RICE_1 compressed flags directly using astropy Rice1, shifts CRPIX coordinates to match the sub-array origin, and preserves exact wavelengths.

We verified numeric parity between S3 range reading and IRSA cutouts across 3 Barnard D2 exposures (see scripts/parity_check.py and docs/validation_output/parity_check.txt):
- 2026W12_1A_0311_1D2: IMAGE diff = 0.0, VARIANCE diff = 0.0, FLAGS diff = 0, wavelength = 1.3155 um on both.
- 2025W34_1B_0164_1D2: IMAGE diff = 0.0, VARIANCE diff = 0.0, FLAGS diff = 0, wavelength = 1.4281 um on both.
- 2026W34_1C_0222_1D2: IMAGE diff = 0.0, VARIANCE diff = 0.0, FLAGS diff = 0, wavelength = 1.4312 um on both.

FOV size timings on Barnard D2 (see scripts/bench_s3.py and docs/validation_output/bench_s3.txt):
- FOV 3 arcmin (29x29 px): 1.2 s per visit via S3 (0.11 MB/exp) vs 18.5 s via IRSA cutout (5.2 MB/exp).
- FOV 10 arcmin (97x97 px): 2.8 s per visit via S3 (0.38 MB/exp) vs 22.1 s via IRSA cutout (5.3 MB/exp).
- FOV 20 arcmin (195x195 px): 6.4 s per visit via S3 (1.52 MB/exp) vs 29.4 s via IRSA cutout (5.8 MB/exp).
- FOV 30 arcmin (293x293 px): 14.1 s per visit via S3 (3.41 MB/exp) vs 41.2 s via IRSA cutout (6.5 MB/exp).
- UI note: Above 15 arcmin, S3 downloads pull 150+ rows across the full 2040-pixel detector, so response time slows down.

Provenance: FITS files record PIXSRC ("aws-s3" or "irsa-cutout"). The manifest labels a visit "aws-s3" only when all exposures came from S3; otherwise it marks "irsa-cutout" or "mixed". If S3 fails, the loader logs a warning and falls back to IRSA with at most 3 parallel requests.

## 4. Astrometry, Alignments, and Target Coverage (B3)

Gaia DR3 positions are queried from IRSA TAP and moved from epoch 2016.0 to each visit date using proper motion. CatWISE2020 sources are queried and moved from epoch 2015.4.

Alignment check:
We measure the centroid offset between slow-moving Gaia stars (10 to 17 mag, pm < 100 mas/yr) and image peaks using a 5x5 window and 3x3 local centroiding.
Offsets 2.5 px or larger are rejected so background noise does not skew the result.
If the median offset across stars exceeds 0.50 px, the visit gets flagged in the manifest notes.
Across all rendered Barnard and Epsilon Indi frames, measured median offsets range from 0.29 px to 0.37 px.

Target render status:
- Barnard D1 to D6: 3 visits each, 8 exposures per visit, pixel_source = aws-s3, offsets 0.30 to 0.37 px.
- Epsilon Indi B D1 to D4: 3 to 5 visits each, 3 to 8 exposures per visit, pixel_source = aws-s3, offsets 0.29 to 0.35 px.
- Remaining targets (Epsilon Indi B D5-D6, WISE 0855, RW Aur, R Dra): Queued for render once the IRSA TAP proxy recovers from its 502 error.

Old vs New releases:
In our practice dataset (QR2), targets had only 1 or 2 visits. In DR1, coverage expands to 3 to 5 visits over 2025 and 2026.
For Barnard visit 0 (2025-08-26, detector 2), the coadded bad-pixel fraction is 3.2% in DR1 compared to 4.1% in the earlier QR2 stack.
