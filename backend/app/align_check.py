"""Astrometric alignment check between SPHEREx frame and Gaia DR3 control stars."""
import numpy as np
from astropy.wcs import WCS

from backend.app.coords import mjd_to_year
from backend.app.gaia import gaia_stars, star_at


def measure_align_offset(
    image: np.ndarray,
    header,
    ra_center: float,
    dec_center: float,
    visit_mjd: float,
    radius_deg: float = 0.05,
    stars: list[dict] | None = None,
) -> float | None:
    """Median centroid offset (pixels) between slow-moving Gaia DR3 control stars and image peaks.

    Selects stars with 10 <= G <= 17 and proper motion < 100 mas/yr.
    Returns median offset in pixels, or None if no control stars are found.
    """
    if stars is None:
        try:
            stars = gaia_stars(ra_center, dec_center, radius_deg)
        except Exception:
            return None

    control = [
        s for s in stars
        if s["g_mag"] is not None and 10.0 <= s["g_mag"] <= 17.0
        and (s["pmra"] is None or (s["pmra"]**2 + s["pmdec"]**2)**0.5 < 100.0)
    ]
    if not control:
        return None

    w = WCS(header)
    year = mjd_to_year(visit_mjd)
    ny, nx = image.shape
    offsets = []

    for s in control:
        s_ra, s_dec = star_at(s, year)
        x_exp, y_exp = w.world_to_pixel_values(s_ra, s_dec)
        xc, yc = int(round(float(x_exp))), int(round(float(y_exp)))
        if 2 <= xc < nx - 2 and 2 <= yc < ny - 2:
            patch = image[yc - 1:yc + 2, xc - 1:xc + 2]
            if np.all(np.isfinite(patch)) and np.max(patch) > 0:
                patch_pos = np.maximum(patch, 0)
                p_sum = patch_pos.sum()
                if p_sum > 0:
                    yy, xx = np.indices(patch.shape)
                    cy = yc - 1 + np.sum(yy * patch_pos) / p_sum
                    cx = xc - 1 + np.sum(xx * patch_pos) / p_sum
                    dist = float(np.hypot(cx - x_exp, cy - y_exp))
                    if dist < 1.5:
                        offsets.append(dist)

    if not offsets:
        return None
    return round(float(np.median(offsets)), 2)

