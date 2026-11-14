"""Unit tests for difference imaging and minus-median frames (backend/app/diff.py)."""
import json
import numpy as np
import pytest
from astropy.io import fits

from backend.app.diff import colour, default_pair, difference, write_diff, write_minus_median


def frame(image, sigma=1.0, flagged=None):
    image = np.asarray(image, float)
    flagged = np.zeros(image.shape, bool) if flagged is None else flagged
    usable = np.isfinite(image) & ~flagged
    return {"image": image, "sigma": np.full(image.shape, sigma), "flagged": flagged, "usable": usable}


def test_difference_in_sigma_removes_sky_change_and_masks_bad_pixels():
    a = np.full((5, 5), 1.0)
    b = np.full((5, 5), 1.5)          # sky 0.5 brighter everywhere
    b[2, 2] += 3 * np.sqrt(2)         # and one pixel 3 sigma (of the difference) brighter
    a[0, 0] = np.nan                  # no value in A
    bad = np.zeros((5, 5), bool)
    bad[4, 4] = True                  # flagged in B
    d = difference(frame(a), frame(b, flagged=bad))
    assert d["sky_change"] == pytest.approx(0.5)
    assert d["z"][2, 2] == pytest.approx(3.0)
    assert np.isnan(d["z"][0, 0]) and np.isnan(d["z"][4, 4])
    assert d["flagged"][4, 4] and not d["flagged"][0, 0]
    assert d["max"][0] == pytest.approx(3.0)


def test_colour_is_north_up_and_transparent_without_value():
    z = np.zeros((3, 3))
    z[0, 0] = 10.0     # FITS row 0 = south -> bottom row of the PNG
    z[2, 2] = np.nan
    rgba = colour(z)
    assert rgba[2, 0, 0] == 255 and rgba[2, 0, 3] == 255   # clipped at +5 sigma: full "brighter" colour
    assert rgba[0, 2, 3] == 0


def test_default_pair_prefers_closest_wavelength_then_longest_time():
    pairs = [
        {"a": 0, "b": 1, "wl_gap_um": 0.05, "days": 300},
        {"a": 0, "b": 2, "wl_gap_um": 0.01, "days": 100},
        {"a": 1, "b": 2, "wl_gap_um": 0.01, "days": 200},
    ]
    assert (default_pair(pairs)["a"], default_pair(pairs)["b"]) == (1, 2)


def test_write_minus_median_synthetic(tmp_path):
    """Verify write_minus_median computes per-pixel median and minus_median frames."""
    folder = tmp_path / "mock_diff" / "d2"
    folder.mkdir(parents=True)
    size = 15

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
    hdr["CRPIX1"] = 8.0
    hdr["CRPIX2"] = 8.0
    hdr["CDELT1"] = -6.15 / 3600.0
    hdr["CDELT2"] = 6.15 / 3600.0

    frames_meta = []
    # 3 visits: background level 10.0. Visit 0 has a transient bright star at (7, 7)
    for i in range(3):
        img = np.full((size, size), 10.0, dtype=np.float32)
        if i == 0:
            img[7, 7] = 50.0  # star only in visit 0

        prim = fits.PrimaryHDU()
        hdul = fits.HDUList([
            prim,
            fits.ImageHDU(img, header=hdr.copy(), name="IMAGE"),
            fits.ImageHDU(np.ones((size, size), dtype=np.float32), header=hdr.copy(), name="SIGMA"),
            fits.ImageHDU(np.zeros((size, size), dtype=np.uint8), header=hdr.copy(), name="FLAGGED"),
            fits.ImageHDU(np.ones((size, size), dtype=np.uint8), header=hdr.copy(), name="HAS_VALUE"),
        ])
        hdul.writeto(folder / f"epoch{i}.fits")
        frames_meta.append({"epoch_id": i, "fits": f"epoch{i}.fits", "n_images": 8, "mjd": 60000.0 + i * 50})

    manifest = {
        "target": "mock",
        "band": 2,
        "size_px": size,
        "scale": {"vmin": 0.0, "vmax": 20.0, "stretch": "linear"},
        "frames": frames_meta,
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2))

    res = write_minus_median(folder)
    assert (folder / "median.fits").exists()
    assert (folder / "median.png").exists()
    assert (folder / "minus_median0.png").exists()
    assert (folder / "minus_median1.png").exists()
    assert (folder / "minus_median2.png").exists()

    # Median at (7, 7) should be 10.0 (median of 50, 10, 10 is 10)
    with fits.open(folder / "median.fits") as h:
        assert h[0].data[7, 7] == pytest.approx(10.0)

