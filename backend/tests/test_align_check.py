"""Unit tests for astrometric alignment checker (backend/app/align_check.py)."""
from unittest.mock import patch
import numpy as np
from astropy.io import fits
from backend.app.align_check import measure_align_offset


def test_measure_align_offset_synthetic():
    """Verify centroid offset measurement with synthetic control stars."""
    size = 29
    img = np.zeros((size, size), dtype=np.float32)

    # Put a star at (14, 14) with a tiny shift (e.g. 0.2 px)
    img[13:16, 13:16] = [[1, 3, 1], [3, 10, 3], [1, 3, 1]]

    hdr = fits.Header()
    hdr["SIMPLE"] = True
    hdr["BITPIX"] = -32
    hdr["NAXIS"] = 2
    hdr["NAXIS1"] = size
    hdr["NAXIS2"] = size
    hdr["CTYPE1"] = "RA---TAN"
    hdr["CTYPE2"] = "DEC--TAN"
    hdr["CRVAL1"] = 100.0
    hdr["CRVAL2"] = 20.0
    hdr["CRPIX1"] = 15.0
    hdr["CRPIX2"] = 15.0
    hdr["CDELT1"] = -6.15 / 3600.0
    hdr["CDELT2"] = 6.15 / 3600.0

    mock_stars = [
        {
            "source_id": "1",
            "ra": 100.0,
            "dec": 20.0,
            "pmra": 0.0,
            "pmdec": 0.0,
            "parallax": 5.0,
            "g_mag": 14.5,
        }
    ]

    with patch("backend.app.align_check.gaia_stars", return_value=mock_stars):
        offset = measure_align_offset(img, hdr, 100.0, 20.0, visit_mjd=60000.0)
        assert offset is not None
        assert offset < 0.5


def test_measure_align_offset_rejects_distant_noise():
    """Verify that a noise peak > 2.5 px away from expected position is rejected."""
    size = 29
    img = np.zeros((size, size), dtype=np.float32)

    # Star expected at (14, 14). Place a solitary noise peak at (16, 16) -> dist = sqrt(2^2 + 2^2) = 2.83 px (> 2.5)
    img[16, 16] = 50.0

    hdr = fits.Header()
    hdr["SIMPLE"] = True
    hdr["BITPIX"] = -32
    hdr["NAXIS"] = 2
    hdr["NAXIS1"] = size
    hdr["NAXIS2"] = size
    hdr["CTYPE1"] = "RA---TAN"
    hdr["CTYPE2"] = "DEC--TAN"
    hdr["CRVAL1"] = 100.0
    hdr["CRVAL2"] = 20.0
    hdr["CRPIX1"] = 15.0
    hdr["CRPIX2"] = 15.0
    hdr["CDELT1"] = -6.15 / 3600.0
    hdr["CDELT2"] = 6.15 / 3600.0

    mock_stars = [
        {
            "source_id": "1",
            "ra": 100.0,
            "dec": 20.0,
            "pmra": 0.0,
            "pmdec": 0.0,
            "parallax": 5.0,
            "g_mag": 14.5,
        }
    ]

    with patch("backend.app.align_check.gaia_stars", return_value=mock_stars):
        offset = measure_align_offset(img, hdr, 100.0, 20.0, visit_mjd=60000.0)
        # Because the distant noise peak is > 2.5 px, it should be rejected and return None
        assert offset is None


