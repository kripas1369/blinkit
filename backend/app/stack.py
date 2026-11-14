"""Add up visit frames (epoch<i>.fits) with inverse-variance weights to increase signal-to-noise.

Coadds all visits (or selected visits) using 1 / sigma² weighting from coadd.coadd.
Noise drops approximately as 1 / sqrt(N), revealing faint objects.
Outputs stack.fits, stack.png, and stack.json.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS

from backend.app.coadd import coadd
from backend.app.render import save_frame_fits, save_png

FORMAT = "spherex-blink-stack/1"


def load_visit_frame(fits_path: Path) -> dict:
    """Load epoch<i>.fits into aligned dict for coadd.coadd."""
    with fits.open(fits_path) as hdul:
        image = hdul["IMAGE"].data.astype(np.float32)
        sigma = hdul["SIGMA"].data.astype(np.float32)
        bad = hdul["FLAGGED"].data.astype(bool)
        covered = hdul["HAS_VALUE"].data.astype(bool)
        mjd = float(hdul[0].header.get("MJD-AVG", 0.0))
        n_images = int(hdul[0].header.get("NIMAGES", 1))
        pixsrc = hdul[0].header.get("PIXSRC")
    return {
        "image": image,
        "sigma": sigma,
        "bad": bad,
        "covered": covered,
        "inside": np.ones_like(covered, dtype=bool),
        "mjd": mjd,
        "n_images": n_images,
        "pixsrc": pixsrc,
    }


def write_stack(folder: Path, visits: list[int] | None = None) -> dict:
    """Stack visit frames (epoch<i>.fits) with 1/variance weights."""
    manifest_path = folder / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"No manifest.json in {folder}")
    manifest = json.loads(manifest_path.read_text())

    frames = manifest["frames"]
    if visits is not None:
        frames = [f for f in frames if f["epoch_id"] in visits]
    if not frames:
        raise ValueError(f"No matching visits to stack in {folder}")

    loaded = [load_visit_frame(folder / f["fits"]) for f in frames]
    coadded = coadd(loaded)

    # Calculate noise metrics
    single_sigmas = []
    for l in loaded:
        usable = l["covered"] & ~l["bad"] & np.isfinite(l["sigma"]) & (l["sigma"] > 0)
        if usable.any():
            single_sigmas.append(float(np.median(l["sigma"][usable])))
    median_single_sigma = float(np.median(single_sigmas)) if single_sigmas else 1.0

    stack_usable = coadded["covered"] & ~coadded["bad"] & np.isfinite(coadded["sigma"]) & (coadded["sigma"] > 0)
    noise_per_pixel = float(np.median(coadded["sigma"][stack_usable])) if stack_usable.any() else 1.0

    noise_ratio = round(median_single_sigma / noise_per_pixel, 2) if noise_per_pixel > 0 else 1.0

    with fits.open(folder / frames[0]["fits"]) as hdul:
        wcs_hdr = hdul["IMAGE"].header
        grid_wcs = WCS(wcs_hdr)

    detector = manifest["band"]
    mean_mjd = float(np.mean([l["mjd"] for l in loaded]))
    total_images = sum(f["n_images"] for f in frames)
    pix_sources = {l["pixsrc"] for l in loaded if l.get("pixsrc")}
    pixel_source = (
        "aws-s3"
        if pix_sources == {"aws-s3"}
        else ("irsa-cutout" if pix_sources == {"irsa-cutout"} else "mixed")
    )

    # Save stack.fits
    save_frame_fits(
        coadded,
        grid_wcs,
        round(mean_mjd, 5),
        total_images,
        detector,
        "stack",
        folder / "stack.fits",
        pixel_source=pixel_source,
    )

    # Save stack.png
    save_png(coadded["image"], coadded["covered"], manifest["scale"], folder / "stack.png")

    # Save stack.json
    chosen_visits = [f["epoch_id"] for f in frames]
    result = {
        "format": FORMAT,
        "target": manifest["target"],
        "band": detector,
        "visits": chosen_visits,
        "n_visits": len(chosen_visits),
        "n_images": total_images,
        "noise_per_pixel": round(noise_per_pixel, 4),
        "single_visit_noise": round(median_single_sigma, 4),
        "noise_ratio_vs_single_visit": noise_ratio,
        "unit": "MJy/sr",
    }
    (folder / "stack.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("folders", type=Path, nargs="+", help="e.g. frontend/frames/barnard/d2")
    parser.add_argument("--visits", type=int, nargs="*", default=None, help="Epoch IDs to stack (default all)")
    args = parser.parse_args()
    for folder in args.folders:
        res = write_stack(folder, visits=args.visits)
        print(
            f"{folder}: stacked {res['n_visits']} visits ({res['n_images']} exposures), "
            f"noise {res['noise_per_pixel']} MJy/sr (gain {res['noise_ratio_vs_single_visit']}x vs single visit)"
        )


if __name__ == "__main__":
    main()

