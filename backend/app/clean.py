"""Step 2a, part 1: turn one raw cutout into a clean picture with its noise and bad-pixel mask."""
import logging
import warnings

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS, FITSFixedWarning

from backend.app.config import BAD_FLAG_NAMES
from backend.app.flags import bad_pixel_bitmask, flag_bits

warnings.simplefilter("ignore", FITSFixedWarning)
logging.getLogger("astropy").setLevel(logging.WARNING)


def wavelength_at(hdul: fits.HDUList, ra: float, dec: float) -> tuple[float | None, float | None]:
    """Wavelength and bandwidth (µm) at the sky position, from the file's spectral WCS (key "W").

    SPHEREx's filter (LVF) changes wavelength across the detector, so this differs per exposure.
    Astropy copies the image's SIP distortion into WCS "W"; it must be turned off there, because the
    filter's wavelength map is not optically distorted (IRSA spherex_intro tutorial, section 8b).
    """
    try:
        sky = WCS(hdul["IMAGE"].header)
        spec = WCS(hdul["IMAGE"].header, fobj=hdul, key="W")
        spec.sip = None
        x, y = sky.world_to_pixel_values(ra, dec)
        wl, bw = spec.pixel_to_world_values(x, y)
        wl, bw = float(wl), float(bw)
    except Exception:  # no WCS-WAVE table or no "W" keys: say "unknown", never guess
        return None, None
    if not (np.isfinite(wl) and np.isfinite(bw)):
        return None, None
    return round(wl, 4), round(bw, 4)


def clean_cutout(path, ra: float | None = None, dec: float | None = None) -> dict:
    """IMAGE − ZODI, sigma = sqrt(VARIANCE), the official bad-pixel mask, MJD-AVG and the WCS.

    NaN stays NaN (e.g. a saturated star core): the file has no value there.
    SOURCE is a label, not a defect, so it never makes a pixel bad (see flags.py).
    """
    with fits.open(path) as hdul:
        header = hdul["IMAGE"].header
        image = hdul["IMAGE"].data.astype(float) - hdul["ZODI"].data.astype(float)
        variance = hdul["VARIANCE"].data.astype(float)
        flags = hdul["FLAGS"].data
        flags_hdr = hdul["FLAGS"].header
        bad = (flags & bad_pixel_bitmask(flags_hdr)) != 0
        wl, bw = wavelength_at(hdul, ra, dec) if ra is not None else (None, None)
        with np.errstate(invalid="ignore"):
            sigma = np.where(variance > 0, np.sqrt(variance), np.nan)
        bits = flag_bits(flags_hdr)
        flag_counts = {
            name: int(np.sum((flags & (1 << bits[name])) != 0))
            for name in BAD_FLAG_NAMES if name in bits
        }
        for name in BAD_FLAG_NAMES:
            flag_counts.setdefault(name, 0)
        pixsrc = hdul[0].header.get("PIXSRC") or header.get("PIXSRC")
        return {
            "image": image,
            "sigma": sigma,
            "bad": bad,
            "wcs": WCS(header),
            "mjd": float(header["MJD-AVG"]),  # when the picture was taken; DATE is processing time
            "wl_um": wl,
            "bw_um": bw,
            "flag_counts": flag_counts,
            "pixel_source": pixsrc,
        }

