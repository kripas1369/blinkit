"""Tests for visit stacking and noise reduction (backend/app/stack.py)."""
import json
import numpy as np
import pytest
from astropy.io import fits

from backend.app.coadd import coadd
from backend.app.stack import load_visit_frame, stack_names, write_stack


def test_subset_stack_uses_tagged_file_names():
    assert stack_names(None, [0, 1, 2]) == ("stack.fits", "stack.png", "stack.json")
    assert stack_names([0, 1, 2], [0, 1, 2]) == ("stack.fits", "stack.png", "stack.json")
    assert stack_names([0, 2], [0, 1, 2]) == ("stack_0_2.fits", "stack_0_2.png", "stack_0_2.json")


def test_coadd_noise_reduction_synthetic():
    """Verify that coadding N independent frames reduces noise close to 1 / sqrt(N)."""
    np.random.seed(42)
    n_frames = 4
    size = 29
    sigma_in = 1.0

    aligned = []
    for _ in range(n_frames):
        noise_img = np.random.normal(0.0, sigma_in, (size, size)).astype(np.float32)
        aligned.append({
            "image": noise_img,
            "sigma": np.full((size, size), sigma_in, dtype=np.float32),
            "bad": np.zeros((size, size), dtype=bool),
            "covered": np.ones((size, size), dtype=bool),
            "inside": np.ones((size, size), dtype=bool),
        })

    result = coadd(aligned)
    # Output noise array should equal sigma_in / sqrt(N) = 1.0 / 2 = 0.5
    expected_sigma = sigma_in / np.sqrt(n_frames)
    assert np.allclose(result["sigma"], expected_sigma, atol=1e-5)

    # Measured empirical scatter of the coadded pixels should also drop by ~sqrt(4) = 2x
    measured_std = float(np.std(result["image"]))
    assert measured_std == pytest.approx(expected_sigma, rel=0.10)


def test_write_stack_synthetic_folder(tmp_path):
    """Verify write_stack writes stack.fits, stack.png, and stack.json with correct gain."""
    size = 29
    folder = tmp_path / "mock_target" / "d2"
    folder.mkdir(parents=True)

    hdr = fits.Header()
    hdr["SIMPLE"] = True
    hdr["BITPIX"] = -32
    hdr["NAXIS"] = 2
    hdr["NAXIS1"] = size
    hdr["NAXIS2"] = size
    hdr["CTYPE1"] = "RA---TAN"
    hdr["CTYPE2"] = "DEC--TAN"
    hdr["CRVAL1"] = 269.45
    hdr["CRVAL2"] = 4.75
    hdr["CRPIX1"] = 15.0
    hdr["CRPIX2"] = 15.0
    hdr["CDELT1"] = -6.15 / 3600.0
    hdr["CDELT2"] = 6.15 / 3600.0

    n_visits = 4
    frames_meta = []
    for i in range(n_visits):
        prim = fits.PrimaryHDU()
        prim.header["MJD-AVG"] = 60000.0 + i * 100.0
        prim.header["NIMAGES"] = 8
        prim.header["PIXSRC"] = "aws-s3"

        img_data = np.random.normal(0.0, 1.0, (size, size)).astype(np.float32)
        sigma_data = np.full((size, size), 1.0, dtype=np.float32)
        bad_data = np.zeros((size, size), dtype=np.uint8)
        cov_data = np.ones((size, size), dtype=np.uint8)

        hdul = fits.HDUList([
            prim,
            fits.ImageHDU(img_data, header=hdr.copy(), name="IMAGE"),
            fits.ImageHDU(sigma_data, header=hdr.copy(), name="SIGMA"),
            fits.ImageHDU(bad_data, header=hdr.copy(), name="FLAGGED"),
            fits.ImageHDU(cov_data, header=hdr.copy(), name="HAS_VALUE"),
        ])
        fits_name = f"epoch{i}.fits"
        hdul.writeto(folder / fits_name)

        frames_meta.append({
            "epoch_id": i,
            "fits": fits_name,
            "n_images": 8,
            "mjd": 60000.0 + i * 100.0,
        })

    manifest = {
        "target": "mock_target",
        "band": 2,
        "size_px": size,
        "scale": {"vmin": -1.0, "vmax": 1.0, "stretch": "linear"},
        "frames": frames_meta,
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2))

    res = write_stack(folder)
    assert (folder / "stack.fits").exists()
    assert (folder / "stack.png").exists()
    assert (folder / "stack.json").exists()

    assert res["n_visits"] == 4
    assert res["n_images"] == 32
    assert res["noise_ratio_vs_single_visit"] == pytest.approx(2.0, abs=0.05)

