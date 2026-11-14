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
- Parity test: Compared S3 slice against the IRSA cutout API for Barnard's Star D2 (level2_2026W12_1A_0311_1D2):
  * IMAGE difference: 0.0
  * VARIANCE difference: 0.0
  * ZODI difference: 0.0
  * FLAGS bitmask: identical
  * Bad pixels: identical count and positions
- Fallback: Any S3 failure automatically drops back to the IRSA cutout service.
