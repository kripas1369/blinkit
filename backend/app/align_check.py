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
        if 3 <= xc < nx - 3 and 3 <= yc < ny - 3:
            search_patch = image[yc - 2:yc + 3, xc - 2:xc + 3]
            if np.all(np.isfinite(search_patch)) and np.max(search_patch) > 0:
                py, px = np.unravel_index(np.argmax(search_patch), search_patch.shape)
                peak_y = yc - 2 + int(py)
                peak_x = xc - 2 + int(px)
                if 1 <= peak_x < nx - 1 and 1 <= peak_y < ny - 1:
                    patch = image[peak_y - 1:peak_y + 2, peak_x - 1:peak_x + 2]
                    patch_pos = np.maximum(patch, 0)
                    p_sum = patch_pos.sum()
                    if p_sum > 0:
                        yy, xx = np.indices(patch.shape)
                        cy = peak_y - 1 + np.sum(yy * patch_pos) / p_sum
                        cx = peak_x - 1 + np.sum(xx * patch_pos) / p_sum
                        dist = float(np.hypot(cx - x_exp, cy - y_exp))
                        offsets.append(dist)

    if not offsets:
        return None
    return round(float(np.median(offsets)), 2)

