"""Six Eyes research lab — isolated from the main Blinkit UI.

Builds per-detector deep coadds (inverse-variance stack of visit epochs) for one
target, extracts a coarse 6-point aperture spectrum at the cutout centre, and
writes everything under frontend/lab/data/<target>/ for frontend/lab/six_eyes.html.

Writes under frontend/frames/<target>/six_eyes/ for the Six Eyes panel.
Does not modify frontend/js/app.js.
"""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from astropy.io import fits

from backend.app.stack import write_stack

REPO = Path(__file__).resolve().parents[1]
FRAMES = REPO / "frontend" / "frames"
LAB_DATA = REPO / "frontend" / "lab" / "data"
FORMAT = "blinkit-six-eyes-lab/1"

# Nominal band centres (µm) for the coarse spectrum x-axis (FACTS / instrument table).
BAND_CENTER_UM = {1: 0.92, 2: 1.36, 3: 2.02, 4: 3.12, 5: 4.12, 6: 4.71}
BAND_RANGE_UM = {
    1: (0.75, 1.09),
    2: (1.10, 1.62),
    3: (1.63, 2.41),
    4: (2.42, 3.82),
    5: (3.83, 4.41),
    6: (4.42, 5.00),
}


def aperture_flux(
    fits_path: Path,
    radius_px: float = 1.5,
    search_radius_px: float = 5.0,
) -> dict:
    """Mean IMAGE near the brightest usable pixel inside a search box around cutout centre.

    Bright targets often leave a NaN core; movers smear in deep stacks. Lab method:
    search for max finite unflagged pixel within search_radius, then average r=radius_px.
    Visualization only — not Tractor / IRSA Spectrophotometry.
    """
    with fits.open(fits_path) as hdul:
        image = hdul["IMAGE"].data.astype(np.float64)
        sigma = hdul["SIGMA"].data.astype(np.float64)
        bad = hdul["FLAGGED"].data.astype(bool)
        covered = hdul["HAS_VALUE"].data.astype(bool)
    h, w = image.shape
    cy, cx = (h - 1) / 2.0, (w - 1) / 2.0
    yy, xx = np.ogrid[:h, :w]
    good = covered & ~bad & np.isfinite(image) & np.isfinite(sigma) & (sigma > 0)
    empty = {
        "flux_mjy_sr": None,
        "sigma_mjy_sr": None,
        "n_pixels": 0,
        "aperture_radius_px": radius_px,
        "search_radius_px": search_radius_px,
        "peak_y": None,
        "peak_x": None,
        "anchor": "none",
    }

    def measure(py: float, px: float, anchor: str) -> dict | None:
        aper = (yy - py) ** 2 + (xx - px) ** 2 <= radius_px ** 2
        usable = aper & good
        n = int(usable.sum())
        if n == 0:
            return None
        return {
            "flux_mjy_sr": round(float(np.mean(image[usable])), 6),
            "sigma_mjy_sr": round(float(np.median(sigma[usable])), 6),
            "n_pixels": n,
            "aperture_radius_px": radius_px,
            "search_radius_px": search_radius_px,
            "peak_y": int(round(py)),
            "peak_x": int(round(px)),
            "anchor": anchor,
        }

    # Prefer geometric centre (correct for faint / cold targets). If the core is
    # empty (saturation hole), fall back to brightest usable pixel in the search box.
    at_centre = measure(cy, cx, "cutout_centre")
    if at_centre is not None:
        return at_centre
    search = (yy - cy) ** 2 + (xx - cx) ** 2 <= search_radius_px ** 2
    cand = good & search
    if not cand.any():
        return empty
    masked = np.where(cand, image, -np.inf)
    peak_flat = int(np.argmax(masked))
    py, px = divmod(peak_flat, w)
    return measure(py, px, "peak_in_search_box") or empty


def ensure_stack(folder: Path) -> dict:
    """Reuse stack artifacts if present; otherwise write_stack.

    Some older stack.json files omit png/fits keys even when stack.png exists —
    treat those as reusable so we do not depend on re-running write_stack.
    """
    stack_json = folder / "stack.json"
    stack_fits = folder / "stack.fits"
    stack_png = folder / "stack.png"
    if stack_fits.exists() and stack_png.exists():
        data = json.loads(stack_json.read_text()) if stack_json.exists() else {}
        data.setdefault("png", "stack.png")
        data.setdefault("fits", "stack.fits")
        data.setdefault("n_visits", 0)
        data.setdefault("n_images", 0)
        data.setdefault("noise_per_pixel", None)
        data.setdefault("single_visit_noise", None)
        data.setdefault("noise_ratio_vs_single_visit", None)
        if (folder / data["png"]).exists() and (folder / data["fits"]).exists():
            return data
    return write_stack(folder)


def build_target(key: str, detectors: list[int], aperture_radius: float) -> dict:
    # Lab copy + prepared-frames copy (main app reads frames/<target>/six_eyes/).
    out_dir = LAB_DATA / key
    frames_out = FRAMES / key / "six_eyes"
    out_dir.mkdir(parents=True, exist_ok=True)
    frames_out.mkdir(parents=True, exist_ok=True)
    eyes = []
    spectrum = []

    for det in detectors:
        folder = FRAMES / key / f"d{det}"
        if not (folder / "manifest.json").exists():
            eyes.append({"band": det, "status": "missing", "reason": "no manifest"})
            continue
        manifest = json.loads((folder / "manifest.json").read_text())
        stack = ensure_stack(folder)
        png_name = f"deep_D{det}.png"
        src_png = folder / stack["png"]
        shutil.copy2(src_png, out_dir / png_name)
        shutil.copy2(src_png, frames_out / png_name)
        phot = aperture_flux(folder / stack["fits"], radius_px=aperture_radius)
        lo, hi = BAND_RANGE_UM[det]
        eye = {
            "band": det,
            "status": "ok",
            "label": f"D{det}",
            "band_range_um": list(manifest.get("band_range_um") or [lo, hi]),
            "wl_center_um": BAND_CENTER_UM[det],
            "png": png_name,
            "png_url": f"/frames/{key}/six_eyes/{png_name}",
            "source_stack": str((folder / stack["png"]).relative_to(REPO)),
            "n_visits": stack["n_visits"],
            "n_images": stack["n_images"],
            "noise_per_pixel": stack["noise_per_pixel"],
            "single_visit_noise": stack.get("single_visit_noise"),
            "noise_ratio_vs_single_visit": stack.get("noise_ratio_vs_single_visit"),
            "photometry": phot,
            "caveat": (
                "Band-averaged inverse-variance coadd of visit epochs; mixes LVF channels "
                "within this detector (see METHODOLOGY.md)."
            ),
        }
        eyes.append(eye)
        spectrum.append({
            "band": det,
            "wl_um": BAND_CENTER_UM[det],
            "wl_lo_um": lo,
            "wl_hi_um": hi,
            "flux_mjy_sr": phot["flux_mjy_sr"],
            "sigma_mjy_sr": phot["sigma_mjy_sr"],
            "n_pixels": phot["n_pixels"],
        })

    meta = {
        "format": FORMAT,
        "target": key,
        "made_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "method": (
            "Per detector: inverse-variance stack of north-up visit epoch*.fits "
            "(backend.app.stack.write_stack); photometry = mean in r="
            f"{aperture_radius} px around the brightest usable pixel within 5 px of cutout centre "
            "(peak-anchored; handles saturated cores and mild mover smear)."
        ),
        "limitations": [
            "Each deep_Di mixes the ~17 LVF channels of that detector — not a single spectral channel.",
            "Peak-anchored aperture can follow a smear lobe for fast movers; flipbook owns motion.",
            "Lab spectrum is visualization only; IRSA Spectrophotometry Tool is for science spectra.",
            "Not the DR1 All-Sky Cube (102 planes); Six Eyes is a 6-detector deep stack for visualization only.",
        ],
        "references": [
            "docs/WHAT_WE_BUILT.md",
            "IRSA SPHEREx data products / All-Sky Cube docs",
        ],
        "ra": None,
        "dec": None,
        "fov_arcmin": None,
        "eyes": eyes,
        "spectrum": spectrum,
    }
    # Position from first available manifest
    for det in detectors:
        man = FRAMES / key / f"d{det}" / "manifest.json"
        if man.exists():
            m = json.loads(man.read_text())
            meta["ra"] = m.get("ra")
            meta["dec"] = m.get("dec")
            meta["fov_arcmin"] = m.get("fov_arcmin")
            meta["label"] = m.get("label", key)
            break

    payload = json.dumps(meta, indent=2) + "\n"
    (out_dir / "six_eyes.json").write_text(payload)
    (frames_out / "six_eyes.json").write_text(payload)
    return meta


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("target", nargs="?", default="barnard", help="frames/<target> key")
    parser.add_argument("--detectors", type=int, nargs="*", default=[1, 2, 3, 4, 5, 6])
    parser.add_argument("--aperture-radius", type=float, default=1.5, help="pixels")
    parser.add_argument("--rebuild-stacks", action="store_true", help="force write_stack even if stack.* exists")
    args = parser.parse_args()
    if args.rebuild_stacks:
        for det in args.detectors:
            folder = FRAMES / args.target / f"d{det}"
            if (folder / "manifest.json").exists():
                write_stack(folder)
    result = build_target(args.target, args.detectors, args.aperture_radius)
    ok = sum(1 for e in result["eyes"] if e.get("status") == "ok")
    print(f"Six Eyes lab → {LAB_DATA / args.target}/six_eyes.json  ({ok}/6 detectors)")
    for e in result["eyes"]:
        if e.get("status") != "ok":
            print(f"  D{e['band']}: {e.get('reason', e['status'])}")
            continue
        phot = e["photometry"]
        print(
            f"  D{e['band']}: visits={e['n_visits']} imgs={e['n_images']} "
            f"noise_gain={e.get('noise_ratio_vs_single_visit')}x "
            f"aperture={phot['flux_mjy_sr']}±{phot['sigma_mjy_sr']} MJy/sr"
        )


if __name__ == "__main__":
    main()
