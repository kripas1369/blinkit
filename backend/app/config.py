"""Fixed settings: archive addresses, SPHEREx facts, and where downloads are cached.

Every value here is checked against a source (see docs/plan/FACTS.md).
"""
import os
from pathlib import Path

TAP_URL = "https://irsa.ipac.caltech.edu/TAP"
CUTOUT_URL = "https://irsa.ipac.caltech.edu/ibe/cutout"
S3_BUCKET_URL = "https://nasa-irsa-spherex.s3.us-east-1.amazonaws.com"
SPHEREX_PIXELS = os.environ.get("SPHEREX_PIXELS", "s3")  # "s3" or "cutout".

# The main CDS server did not respond on 29 Oct 2026; the Harvard mirror did.
SIMBAD_SERVERS = ("simbad.cds.unistra.fr", "simbad.harvard.edu")

# Science image collections in spherex.obscore.
# QR2 is no longer listed by IRSA search (checked 13 Nov 2026); QR3 and DR1 are active.
# "_deep" = the extra visits to the two SPHEREx Deep Fields near the ecliptic poles.
_DEFAULT_COLLECTIONS = ("spherex_qr3", "spherex_qr3_deep", "spherex_dr1", "spherex_dr1_deep")
COLLECTIONS = tuple(
    [c.strip() for c in os.environ["SPHEREX_COLLECTIONS"].split(",") if c.strip()]
    if os.environ.get("SPHEREX_COLLECTIONS")
    else _DEFAULT_COLLECTIONS
)

PIXEL_SCALE_ARCSEC = 6.15

# Gaia DR3 at IRSA (table name checked 29 Oct 2026); every position is for epoch 2016.0 (ref_epoch).
GAIA_TABLE = "gaia_dr3_source"
GAIA_EPOCH = 2016.0

# Wavelength range of each detector in micrometres (SPHEREx Explanatory Supplement).
DETECTORS = {
    1: (0.75, 1.09),
    2: (1.10, 1.62),
    3: (1.63, 2.41),
    4: (2.42, 3.82),
    5: (3.83, 4.41),
    6: (4.42, 5.00),
}

# Pixels with any of these flags are bad (Supplement v2.0, section 3.4.3, Mosaic Tool list).
# Bit positions are NOT fixed here; they are read from the MP_* keywords of each FLAGS header,
# and names missing from a release's header are simply skipped.
# SOURCE (bit 21) is deliberately absent: it labels a known object, it is not a defect.
BAD_FLAG_NAMES = (
    "TRANSIENT", "SUR_ERROR", "NONFUNC", "DICHROIC", "MISSING_DATA", "HOT", "COLD",
    "PHANMISS", "NONLINEAR", "PERSIST", "CROSSTALK", "GHOST", "GHOST_FPA", "GHOST_EXT",
    "STREAK", "BLOOM", "SNOWBALL", "HALO", "SATELLITE_HALO",
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = REPO_ROOT / "cache"

# IRSA answered "503 busy" when we sent 4+ cutout requests at once (31 Oct 2026).
MAX_PARALLEL_DOWNLOADS = 3
RETRIES = 4

# The cutout service always sends the full PSF cube (121 x 101 x 101, ~4.9 MB) with each cutout and
# cannot leave it out (IRSA cutout docs, checked 12 Nov 2026). Nothing here reads it (PSF_FWHM is an
# IMAGE header keyword), so it is dropped before saving: ~5 MB -> ~0.1 MB per cutout.
DROP_PSF_FROM_CUTOUTS = True
# Live jobs remove the least recently used cutouts once the cache passes this size.
CUTOUT_CACHE_MAX_GB = 10.0
