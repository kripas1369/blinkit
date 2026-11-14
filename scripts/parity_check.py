"""Compare the S3 byte-range reader with the IRSA cutout service, pixel by pixel.

For each exposure: read a box around Barnard's Star from AWS S3 (backend/app/s3_reader.read_box) and
download a cutout of the same exposure from IRSA (ibe/cutout). The two boxes need not start at the same
detector pixel, so they are lined up with their own CRPIX (both are crops of the same detector image)
and only the overlapping pixels are compared.

Run from the repository root:  python -m scripts.parity_check
"""
import io
import time

import numpy as np
import requests
from astropy.io import fits

from backend.app.clean import wavelength_at
from backend.app.config import CUTOUT_URL
from backend.app.s3_reader import read_box

RA, DEC = 269.44627, 4.76820   # Barnard's Star at 2026.0
SIZE_DEG = 0.05

# One Barnard D2 exposure per visit, as found by the image search on 14 Nov 2026.
EXPOSURES = [
    "dr1/level2/2025W35_1A/l2b_retry-v27-2026-230/2/level2_2025W35_1A_0444_1D2_spx_l2b_retry-v27-2026-230.fits",
    "dr1/level2/2026W12_1A/l2b-v27-2026-235/2/level2_2026W12_1A_0311_1D2_spx_l2b-v27-2026-235.fits",
    "qr3/level2/2026W34_2A/l2b-v27-2026-243/2/level2_2026W34_2A_0264_2D2_spx_l2b-v27-2026-243.fits",
]


def irsa_cutout(key: str) -> fits.HDUList:
    params = {"ra": RA, "dec": DEC, "size": SIZE_DEG, "path": f"spherex/{key}"}
    for attempt in range(4):
        resp = requests.get(CUTOUT_URL, params=params, timeout=180)
        if resp.status_code == 200 and resp.content[:6] == b"SIMPLE":
            return fits.open(io.BytesIO(resp.content))
        time.sleep(2 ** attempt)
    raise RuntimeError(f"IRSA cutout failed: HTTP {resp.status_code}")


def overlap(s3: fits.HDUList, irsa: fits.HDUList, name: str) -> tuple[np.ndarray, np.ndarray]:
    """The same detector pixels from both boxes."""
    dx = s3["IMAGE"].header["CRPIX1"] - irsa["IMAGE"].header["CRPIX1"]
    dy = s3["IMAGE"].header["CRPIX2"] - irsa["IMAGE"].header["CRPIX2"]
    if abs(dx - round(dx)) > 1e-6 or abs(dy - round(dy)) > 1e-6:
        raise ValueError(f"boxes are not on the same pixel grid (dx={dx}, dy={dy})")
    dx, dy = int(round(dx)), int(round(dy))   # IRSA pixel (r, c) = S3 pixel (r + dy, c + dx)
    a, b = s3[name].data, irsa[name].data
    r0, r1 = max(0, -dy), min(b.shape[0], a.shape[0] - dy)
    c0, c1 = max(0, -dx), min(b.shape[1], a.shape[1] - dx)
    return a[r0 + dy:r1 + dy, c0 + dx:c1 + dx], b[r0:r1, c0:c1]


def compare(key: str) -> bool:
    print(f"\n{key.rsplit('/', 1)[-1]}")
    s3 = read_box(key, RA, DEC, SIZE_DEG)
    irsa = irsa_cutout(key)
    print(f"  box: S3 {s3['IMAGE'].data.shape}, IRSA {irsa['IMAGE'].data.shape}")
    same = True
    for name in ("IMAGE", "VARIANCE", "ZODI"):
        a, b = overlap(s3, irsa, name)
        nan_same = np.array_equal(np.isnan(a), np.isnan(b))
        ok = np.isfinite(a) & np.isfinite(b)
        max_diff = float(np.max(np.abs(a[ok] - b[ok]))) if ok.any() else float("nan")
        same &= nan_same and max_diff == 0.0
        print(f"  {name}: {a.size} pixels compared, max |S3 - IRSA| = {max_diff}, same NaN pixels: {nan_same}")
    a, b = overlap(s3, irsa, "FLAGS")
    n_diff = int(np.count_nonzero(a.astype(np.int64) != b.astype(np.int64)))
    same &= n_diff == 0
    print(f"  FLAGS: {a.size} pixels compared, {n_diff} differ")
    wl_s3, wl_irsa = wavelength_at(s3, RA, DEC), wavelength_at(irsa, RA, DEC)
    same &= wl_s3 == wl_irsa
    print(f"  wavelength, bandwidth at the star (um): S3 {wl_s3}, IRSA {wl_irsa}")
    print(f"  result: {'IDENTICAL' if same else 'DIFFERENT'}")
    return same


if __name__ == "__main__":
    print("=== S3 byte-range reader vs IRSA cutout service ===")
    print(f"position RA={RA} Dec={DEC}, box {SIZE_DEG} deg, run {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}")
    results = [compare(k) for k in EXPOSURES]
    print(f"\n{sum(results)} of {len(results)} exposures identical")
