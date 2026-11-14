"""Tests for the S3 byte-range pixel reader.

Offline tests verify header parsing, FITS block padding, and WCS CRPIX shifting mathematics.
Live tests against the public AWS S3 bucket require RUN_NETWORK=1.
"""
import io
import os
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from astropy.io import fits
from astropy.wcs import WCS

from backend.app.clean import clean_cutout
from backend.app.s3_reader import (
    NPIX, S3NotInImage, S3ReaderError, hdu_end, parse_header, read_box, read_header,
)


def _make_dummy_header(cards: dict) -> bytes:
    """Create a standard FITS 2880-byte header block."""
    hdr = fits.Header()
    for k, v in cards.items():
        hdr[k] = v
    header_str = hdr.tostring()
    pad_len = -(-len(header_str) // 2880) * 2880
    return header_str.ljust(pad_len).encode("ascii")


def test_parse_header():
    """Verify parse_header finds the END card and parses card values."""
    buf = _make_dummy_header({"SIMPLE": True, "BITPIX": -32, "NAXIS": 2, "NAXIS1": 100, "NAXIS2": 100})
    parsed = parse_header(buf, 0)
    assert parsed is not None
    hdr, next_pos = parsed
    assert hdr["SIMPLE"] is True
    assert hdr["NAXIS1"] == 100
    assert next_pos == 2880


def test_hdu_end_padding():
    """Verify hdu_end pads data arrays to standard 2880-byte FITS boundaries."""
    # 2040 x 2040 float32 array = 16,646,400 bytes
    hdr = fits.Header({"SIMPLE": True, "BITPIX": -32, "NAXIS": 2, "NAXIS1": 2040, "NAXIS2": 2040})
    data_start = 2880
    next_hdu = hdu_end(hdr, data_start)
    assert (next_hdu - data_start) % 2880 == 0
    assert next_hdu == 2880 + 16646400

    # Table with PCOUNT heap
    hdr_table = fits.Header({"XTENSION": "BINTABLE", "BITPIX": 8, "NAXIS": 2, "NAXIS1": 10, "NAXIS2": 100, "PCOUNT": 50})
    next_table = hdu_end(hdr_table, 2880)
    assert (next_table - 2880) % 2880 == 0


def test_crpix_shift_mathematics():
    """Verify that shifting CRPIX preserves the exact sky-to-pixel mapping."""
    ra_center, dec_center = 269.45, 4.75

    full_hdr = fits.Header()
    full_hdr["SIMPLE"] = True
    full_hdr["BITPIX"] = -32
    full_hdr["NAXIS"] = 2
    full_hdr["NAXIS1"] = NPIX
    full_hdr["NAXIS2"] = NPIX
    full_hdr["CTYPE1"] = "RA---TAN"
    full_hdr["CTYPE2"] = "DEC--TAN"
    full_hdr["CRVAL1"] = ra_center
    full_hdr["CRVAL2"] = dec_center
    full_hdr["CRPIX1"] = 1020.5
    full_hdr["CRPIX2"] = 1020.5
    full_hdr["CDELT1"] = -6.15 / 3600.0
    full_hdr["CDELT2"] = 6.15 / 3600.0

    w_full = WCS(full_hdr)
    target_ra, target_dec = 269.46, 4.76
    x_full, y_full = w_full.world_to_pixel_values(target_ra, target_dec)
    x_full, y_full = float(x_full), float(y_full)

    x0 = int(round(x_full)) - 10
    y0 = int(round(y_full)) - 10

    crop_hdr = full_hdr.copy()
    crop_hdr["CRPIX1"] = full_hdr["CRPIX1"] - x0
    crop_hdr["CRPIX2"] = full_hdr["CRPIX2"] - y0
    crop_hdr["NAXIS1"] = 21
    crop_hdr["NAXIS2"] = 21

    w_crop = WCS(crop_hdr)
    x_crop, y_crop = w_crop.world_to_pixel_values(target_ra, target_dec)

    # Cropped coordinates must match full coordinates shifted by (x0, y0)
    assert x_crop == pytest.approx(x_full - x0, abs=1e-6)
    assert y_crop == pytest.approx(y_full - y0, abs=1e-6)


def test_s3_not_in_image_check():
    """Verify that coordinates falling outside the detector bounds raise S3NotInImage."""
    full_hdr = fits.Header()
    full_hdr["SIMPLE"] = True
    full_hdr["BITPIX"] = -32
    full_hdr["NAXIS"] = 2
    full_hdr["NAXIS1"] = NPIX
    full_hdr["NAXIS2"] = NPIX
    full_hdr["CTYPE1"] = "RA---TAN"
    full_hdr["CTYPE2"] = "DEC--TAN"
    full_hdr["CRVAL1"] = 10.0
    full_hdr["CRVAL2"] = 10.0
    full_hdr["CRPIX1"] = 1020.5
    full_hdr["CRPIX2"] = 1020.5
    full_hdr["CDELT1"] = -6.15 / 3600.0
    full_hdr["CDELT2"] = 6.15 / 3600.0

    prim_hdr = fits.Header({"SIMPLE": True})

    with patch("backend.app.s3_reader.read_header") as mock_hdr:
        mock_hdr.side_effect = [
            (prim_hdr, 2880, b""),
            (full_hdr, 5760, b""),
        ]
        # RA/Dec far away (e.g. 50.0, 50.0)
        with pytest.raises(S3NotInImage):
            read_box("dummy_key.fits", ra=50.0, dec=50.0, size_deg=0.05)


@pytest.mark.skipif(not os.environ.get("RUN_NETWORK"), reason="set RUN_NETWORK=1 for live S3 tests")
def test_live_s3_read_box(tmp_path):
    """Live verification against AWS S3 public bucket for Barnard's Star D2 exposure."""
    key = "dr1/level2/2026W12_1A/l2b-v27-2026-235/2/level2_2026W12_1A_0311_1D2_spx_l2b-v27-2026-235.fits"
    ra, dec = 269.44627, 4.76820
    out_file = tmp_path / "live_barnard_d2.fits"

    hdul = read_box(key, ra, dec, size_deg=0.08, target_path=out_file)
    assert out_file.exists()
    assert len(hdul) == 6
    assert [h.name for h in hdul] == ["PRIMARY", "IMAGE", "FLAGS", "VARIANCE", "ZODI", "WCS-WAVE"]

    cleaned = clean_cutout(out_file, ra, dec)
    assert cleaned["image"].shape == (47, 47)
    assert cleaned["wl_um"] == pytest.approx(1.3155, abs=0.001)
    assert cleaned["bw_um"] == pytest.approx(0.0317, abs=0.001)
    assert np.isfinite(cleaned["sigma"]).any()
