"""Compare 5 Barnard exposures read from QR2 and DR1 on AWS S3.

Compares MJD-AVG, WCS centre coordinates, flagged pixel fraction, and median pixel difference
on the 3-arcmin box around Barnard's Star (269.44627, 4.76820).

Run from repository root:
    python -m scripts.compare_qr2_dr1
"""
import numpy as np
from astropy.wcs import WCS

from backend.app.config import PIXEL_SCALE_ARCSEC
from backend.app.flags import bad_pixel_bitmask
from backend.app.s3_reader import NPIX, get_range, hdu_end, read_box, read_header

RA, DEC, SIZE_DEG = 269.44627, 4.76820, 0.05

EXPOSURES = [
    (
        "2025W35_1A_0146_1",
        "qr2/level2/2025W35_1A/l2b-v20-2025-269/2/level2_2025W35_1A_0146_1D2_spx_l2b-v20-2025-269.fits",
        "dr1/level2/2025W35_1A/l2b-v27-2026-230/2/level2_2025W35_1A_0146_1D2_spx_l2b-v27-2026-230.fits",
    ),
    (
        "2025W35_1A_0146_2",
        "qr2/level2/2025W35_1A/l2b-v20-2025-269/2/level2_2025W35_1A_0146_2D2_spx_l2b-v20-2025-269.fits",
        "dr1/level2/2025W35_1A/l2b-v27-2026-230/2/level2_2025W35_1A_0146_2D2_spx_l2b-v27-2026-230.fits",
    ),
    (
        "2025W35_1A_0146_3",
        "qr2/level2/2025W35_1A/l2b-v20-2025-269/2/level2_2025W35_1A_0146_3D2_spx_l2b-v20-2025-269.fits",
        "dr1/level2/2025W35_1A/l2b-v27-2026-230/2/level2_2025W35_1A_0146_3D2_spx_l2b-v27-2026-230.fits",
    ),
    (
        "2025W35_1A_0146_4",
        "qr2/level2/2025W35_1A/l2b-v20-2025-269/2/level2_2025W35_1A_0146_4D2_spx_l2b-v20-2025-269.fits",
        "dr1/level2/2025W35_1A/l2b-v27-2026-230/2/level2_2025W35_1A_0146_4D2_spx_l2b-v27-2026-230.fits",
    ),
    (
        "2025W35_1A_0444_1",
        "qr2/level2/2025W35_1A/l2b-v20-2025-269/2/level2_2025W35_1A_0444_1D2_spx_l2b-v20-2025-269.fits",
        "dr1/level2/2025W35_1A/l2b_retry-v27-2026-230/2/level2_2025W35_1A_0444_1D2_spx_l2b_retry-v27-2026-230.fits",
    ),
]


def read_qr2_box(key: str, ra: float, dec: float, size_deg: float = 0.05):
    h0, d0, _ = read_header(key, 0)
    h1, d1, _ = read_header(key, hdu_end(h0, d0))
    h2, d2, _ = read_header(key, hdu_end(h1, d1))

    w = WCS(h1)
    x, y = w.all_world2pix(ra, dec, 0)
    x, y = float(x), float(y)

    box_size = max(5, int(np.round(size_deg * 3600.0 / PIXEL_SCALE_ARCSEC)))
    half = box_size // 2
    xc, yc = int(np.round(x)), int(np.round(y))
    x0, x1 = max(0, xc - half), min(NPIX - 1, xc + half)
    y0, y1 = max(0, yc - half), min(NPIX - 1, yc + half)
    nrow = y1 - y0 + 1

    row_bytes = NPIX * 4
    img_buf = get_range(key, d1 + y0 * row_bytes, nrow * row_bytes)
    img_data = np.frombuffer(img_buf, dtype=">f4").reshape(nrow, NPIX)[:, x0 : x1 + 1].copy()

    flag_buf = get_range(key, d2 + y0 * row_bytes, nrow * row_bytes)
    flag_data = np.frombuffer(flag_buf, dtype=">i4").reshape(nrow, NPIX)[:, x0 : x1 + 1].copy()

    mask = bad_pixel_bitmask(h2)
    bad = (flag_data & mask) != 0
    return img_data, bad, h0, h1


def main():
    print(f"Comparing 5 Barnard D2 exposures on AWS S3 (QR2 vs DR1 at RA {RA:.5f}, Dec {DEC:+.5f}):")
    print(
        f"{'OBS_ID':<18} {'MJD-AVG Diff':<14} {'WCS Center Sep':<16} {'Flagged (QR2/DR1)':<20} {'Median Diff (DR1-QR2)':<22}"
    )
    print("-" * 90)

    for obs_id, qr2_key, dr1_key in EXPOSURES:
        img_q, bad_q, h0_q, h1_q = read_qr2_box(qr2_key, RA, DEC, SIZE_DEG)
        mjd_q = h1_q.get("MJD-AVG", h0_q.get("MJD-AVG"))
        crval_q = (h1_q.get("CRVAL1"), h1_q.get("CRVAL2"))
        flg_pct_q = round(100.0 * np.count_nonzero(bad_q) / bad_q.size, 2)

        hdul_d = read_box(dr1_key, RA, DEC, SIZE_DEG)
        h0_d = hdul_d[0].header
        h1_d = hdul_d["IMAGE"].header
        h2_d = hdul_d["FLAGS"].header
        img_d = hdul_d["IMAGE"].data
        mask_d = bad_pixel_bitmask(h2_d)
        bad_d = (hdul_d["FLAGS"].data & mask_d) != 0
        mjd_d = h1_d.get("MJD-AVG", h0_d.get("MJD-AVG"))
        crval_d = (h1_d.get("CRVAL1"), h1_d.get("CRVAL2"))
        flg_pct_d = round(100.0 * np.count_nonzero(bad_d) / bad_d.size, 2)

        min_r = min(img_q.shape[0], img_d.shape[0])
        min_c = min(img_q.shape[1], img_d.shape[1])
        iq = img_q[:min_r, :min_c]
        id_ = img_d[:min_r, :min_c]
        valid = np.isfinite(iq) & np.isfinite(id_) & ~bad_q[:min_r, :min_c] & ~bad_d[:min_r, :min_c]

        med_diff = float(np.median(id_[valid] - iq[valid])) if valid.any() else np.nan
        wcs_sep = float(
            np.hypot(
                (crval_d[0] - crval_q[0]) * np.cos(np.radians(crval_q[1])),
                crval_d[1] - crval_q[1],
            )
            * 3600.0
        )
        mjd_diff_s = (mjd_d - mjd_q) * 86400.0

        mjd_str = f"{mjd_diff_s:+.4f} s"
        wcs_str = f"{wcs_sep:.3f} arcsec"
        flg_str = f"{flg_pct_q}% / {flg_pct_d}%"
        diff_str = f"{med_diff:+.5f} MJy/sr"

        print(f"{obs_id:<18} {mjd_str:<14} {wcs_str:<16} {flg_str:<20} {diff_str:<22}")


if __name__ == "__main__":
    main()

