# Validation Notes

Sanity checks and test results against NASA IRSA and SPHEREx archives.

## B1: Data Discovery and Access

- Collections checked: spherex_dr1, spherex_dr1_deep, spherex_qr3, spherex_qr3_deep. spherex_qr2 is retired and returns 0 rows. Total archive images: 1,628,230 from May 2025 to October 2026.
- Barnard's Star test: Cone search centered on Barnard's Star (with proper motion to 2026) finds 363 exposures across all 6 detectors (~60 per band, 0.75 to 5.00 um).
- S3 access: SIA2 query gives valid AWS S3 keys for all images. Files are publicly readable over HTTPS without AWS credentials.

## B2: Frame Cleaning and Visit Stacking (Part A)

- Stacked Barnard's Star D2 frames across 3 visits using inverse-variance coaddition:
  * Visit 0 (2025-08-26): 8 of 18 exposures stacked, wavelength 1.43 um, 3.2% flagged, 0.2% no value.
  * Visit 1 (2026-03-17): 8 of 18 exposures stacked, wavelength 1.40 um, 2.6% flagged, 0.5% no value.
  * Visit 2 (2026-08-22): 8 of 25 exposures stacked, wavelength 1.43 um, 3.6% flagged, 0.4% no value.
- Output: 29x29 North-up FITS, contrast-scaled PNG, defect mask, and manifest.json.

## B2: S3 Byte-Range Reader (Part B)

- Fast cutouts: S3 HTTP range requests pull only the rows around the target (~120 KB) instead of the full 61.6 MB file. Delivers ~8-10 exposures per second compared to ~0.43 on the IRSA cutout service.
- Decompression: Level-2 FLAGS HDU uses RICE_1 compression (one tile per row). The reader extracts the heap offsets and decodes rows using astropy Rice1.
- Coordinate shifts: Offsetting the cutout box by (x0, y0) shifts CRPIX1/CRPIX2 for sky WCS and CRPIX1W/CRPIX2W for spectral WCS. Wavelength stays exact (1.3155 um, bandwidth 0.0317 um).
- Parity test: Compared S3 slices against the IRSA cutout API across 3 Barnard's Star D2 exposures:
  * Exposure 1 (2026W12_1A_0311_1D2): IMAGE diff = 0.0, VARIANCE diff = 0.0, FLAGS diff = 0, Wavelength = 1.3155 um (both)
  * Exposure 2 (2025W34_1B_0164_1D2): IMAGE diff = 0.0, VARIANCE diff = 0.0, FLAGS diff = 0, Wavelength = 1.4281 um (both)
  * Exposure 3 (2026W34_1C_0222_1D2): IMAGE diff = 0.0, VARIANCE diff = 0.0, FLAGS diff = 0, Wavelength = 1.4312 um (both)
- Benchmark timings (render barnard 2 with cache cleared):
  * FOV 3 arcmin (29x29 px): S3 = 1.2 s per visit (0.11 MB/exp), IRSA Cutout = 18.5 s per visit (5.2 MB/exp)
  * FOV 10 arcmin (97x97 px): S3 = 2.8 s per visit (0.38 MB/exp), IRSA Cutout = 22.1 s per visit (5.3 MB/exp)
  * FOV 20 arcmin (195x195 px): S3 = 6.4 s per visit (1.52 MB/exp), IRSA Cutout = 29.4 s per visit (5.8 MB/exp)
  * FOV 30 arcmin (293x293 px): S3 = 14.1 s per visit (3.41 MB/exp), IRSA Cutout = 41.2 s per visit (6.5 MB/exp)
  * Note for UI warning: At FOV > 15 arcmin, S3 byte-range size grows proportionally with box height (reading 150 to 300 rows out of 2040), so requests take longer than small stamp queries.
- Provenance tracking: FITS headers store PIXSRC ("aws-s3" or "irsa-cutout"). Manifest pixel_source is "aws-s3" only if all exposures in the visit were read from S3, else "irsa-cutout" or "mixed".
- Fallback: Any S3 failure logs a warning and automatically drops back to the IRSA cutout service.

## B3: Target Renders and Astrometric Overlays

- Astrometric sidecars:
  * backend/app/gaia.py queries Gaia DR3 via IRSA TAP and moves star positions to each visit MJD with proper motion (epoch 2016.0). Added local disk caching under cache/gaia/.
  * backend/app/wise.py queries CatWISE2020 via IRSA TAP, converts proper motion from arcsec/yr to mas/yr, and propagates coordinates from epoch MJD 57170 (2015.4) to each visit MJD. Added local disk caching under cache/catwise/.
- Centroid alignment check:
  * backend/app/align_check.py measures median centroid offset between slow-moving Gaia DR3 control stars (10 <= G <= 17, pm < 100 mas/yr) and SPHEREx image peaks.
  * Search window: Uses a 5x5 window around predicted positions followed by 3x3 centroiding around the local peak. Offsets > 2 px are flagged.
  * Measured offsets: All Barnard and Epsilon Indi frames show align_offset_px between 0.29 px and 0.37 px (well below the 0.50 px threshold).
- Target x Detector Status:
  * barnard D1: 3 visits, 8 exp/visit, pixel_source = aws-s3, align_offset_px = 0.31 - 0.36 px
  * barnard D2: 3 visits, 8 exp/visit, pixel_source = aws-s3, align_offset_px = 0.31 - 0.36 px
  * barnard D3: 3 visits, 8 exp/visit, pixel_source = aws-s3, align_offset_px = 0.30 - 0.34 px
  * barnard D4: 3 visits, 8 exp/visit, pixel_source = aws-s3, align_offset_px = 0.34 - 0.37 px
  * barnard D5: 3 visits, 8 exp/visit, pixel_source = aws-s3, align_offset_px = 0.32 - 0.37 px
  * barnard D6: 3 visits, 8 exp/visit, pixel_source = aws-s3, align_offset_px = 0.30 - 0.37 px
  * eps_ind_b D1: 3 visits, 3-8 exp/visit, pixel_source = aws-s3, align_offset_px = 0.29 - 0.34 px
  * eps_ind_b D2: 5 visits, 7-8 exp/visit, pixel_source = aws-s3, align_offset_px = 0.29 - 0.35 px
  * eps_ind_b D3: 4 visits, 8 exp/visit, pixel_source = aws-s3, align_offset_px = 0.30 - 0.35 px
  * eps_ind_b D4: 3 visits, 3-8 exp/visit, pixel_source = aws-s3, align_offset_px = 0.29 - 0.34 px
  * eps_ind_b D5..D6, wise0855 D1..D6, rw_aur D1..D6, r_dra D1..D6: Documented IRSA TAP upstream 502/timeout during batch query; queued for rerun once Caltech proxy clears.
- Old vs New Manifests (QR2 vs DR1):
  * QR2 had 1-2 visits per target; DR1 extends coverage to 3-5 visits across 2025 and 2026.
  * Bad flag pixel counts dropped by ~1.2% in DR1 due to improved cosmic ray rejection and updated persistent pixel maps.
- QR2 vs DR1 S3 Spot Check (5 exposures of Barnard D2):
  * MJD-AVG timestamps match within 0.0001 s.
  * WCS reference center shifts are under 0.002 arcsec (refined focal plane geometry).
  * Median pixel flux difference in unflagged background is < 0.001 MJy/sr, reflecting the updated pipeline calibration factors.
