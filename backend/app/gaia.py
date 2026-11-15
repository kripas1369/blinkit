"""Gaia DR3 stars in the frames' field, moved to the date of each visit.

Gaia gives every star's position for 2016.0 and its proper motion. Moving each star to the time of
each SPHEREx visit tells us where it should be in that frame; a star that sits on its markers in
every visit is moving as Gaia says. Parallax is not applied (at most ~0.09 SPHEREx pixels).

    python -m backend.app.gaia frontend/frames/barnard/d2
"""
import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from backend.app import archive
from backend.app.align import target_grid
from backend.app.config import CACHE_DIR, GAIA_EPOCH, GAIA_TABLE, PIXEL_SCALE_ARCSEC
from backend.app.coords import mjd_to_year
from backend.app.motion import position_at, separation_arcsec

FORMAT = "spherex-blink-gaia/1"
TARGET_MATCH_ARCSEC = 3.0  # half a SPHEREx pixel
MAX_MOTION_ARCSEC_PER_YEAR = 11.0  # Barnard's Star moves 10.4″/yr
MARGIN_PX = 1.0


def _gaia_row_value(row, name):
    v = row[name]
    return None if np.ma.is_masked(v) or not np.isfinite(float(v)) else float(v)


def _stars_from_table(table) -> list[dict]:
    stars = []
    for row in table:
        epoch = _gaia_row_value(row, "ref_epoch")
        if epoch is not None and abs(epoch - GAIA_EPOCH) > 0.01:
            raise archive.ArchiveError(
                f"Gaia source {row['source_id']} has ref_epoch {epoch}, expected {GAIA_EPOCH}"
            )
        stars.append({
            "source_id": str(row["source_id"]),
            "ra": float(row["ra"]),
            "dec": float(row["dec"]),
            "pmra": _gaia_row_value(row, "pmra"),
            "pmdec": _gaia_row_value(row, "pmdec"),
            "parallax": _gaia_row_value(row, "parallax"),
            "g_mag": _gaia_row_value(row, "phot_g_mean_mag"),
        })
    return stars


def _gaia_from_esa(ra: float, dec: float, radius_deg: float):
    """Gaia DR3 via ESA's archive (astroquery) when IRSA TAP is down."""
    from astroquery.gaia import Gaia

    Gaia.ROW_LIMIT = -1
    adql = f"""
        SELECT source_id, ra, dec, pmra, pmdec, parallax, phot_g_mean_mag, ref_epoch
        FROM gaiadr3.gaia_source
        WHERE CONTAINS(POINT('ICRS', ra, dec), CIRCLE('ICRS', {ra:.8f}, {dec:.8f}, {radius_deg:.6f})) = 1
    """
    return Gaia.launch_job(adql).get_results()


def gaia_stars(ra: float, dec: float, radius_deg: float) -> list[dict]:
    """Every Gaia DR3 source within radius_deg of (ra, dec), as Gaia lists it (positions for 2016.0).

    Tries NASA/IPAC IRSA first (same TAP as SPHEREx). If IRSA is down, falls back to ESA's
    Gaia archive through astroquery so overlays and proofs still work.
    """
    cache_file = CACHE_DIR / "gaia" / f"{ra:.5f}_{dec:+.5f}_{radius_deg:.4f}_gaia.json"
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text())
        except Exception:
            pass

    table = None
    source = f"{GAIA_TABLE} at NASA/IPAC IRSA"
    try:
        table = archive.run_query(f"""
            SELECT source_id, ra, dec, pmra, pmdec, parallax, phot_g_mean_mag, ref_epoch
            FROM {GAIA_TABLE}
            WHERE CONTAINS(POINT('ICRS', ra, dec), CIRCLE('ICRS', {ra:.8f}, {dec:.8f}, {radius_deg:.6f})) = 1
        """)
    except archive.ArchiveError as irsa_error:
        # TAP cooldown means IRSA just failed hard; ESA often hangs ~60s and blocks the job queue.
        if "not retried for a few minutes" in str(irsa_error):
            raise
        print(f"  warning: IRSA Gaia failed ({irsa_error}); trying ESA Gaia archive")
        try:
            table = _gaia_from_esa(ra, dec, radius_deg)
            source = "gaiadr3.gaia_source at ESA (astroquery)"
        except Exception as esa_error:
            raise archive.ArchiveError(f"{irsa_error}; ESA Gaia also failed: {esa_error}") from esa_error

    stars = _stars_from_table(table)
    if "ESA" in source:
        print(f"  Gaia: {len(stars)} stars from {source}")
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(stars, indent=1))
    return stars


def search_radius_deg(fov_arcmin: float, years_from_gaia: float) -> float:
    """Half the frame's diagonal plus the farthest any star could have moved since 2016.0."""
    half_diagonal = fov_arcmin / 60.0 / 2.0 * math.sqrt(2)
    return half_diagonal + (MAX_MOTION_ARCSEC_PER_YEAR * abs(years_from_gaia) + MARGIN_PX * PIXEL_SCALE_ARCSEC) / 3600.0


def star_at(star: dict, year: float) -> tuple[float, float]:
    if star["pmra"] is None or star["pmdec"] is None:
        return star["ra"], star["dec"]
    return position_at(star["ra"], star["dec"], star["pmra"], star["pmdec"], GAIA_EPOCH, year)


def markers(
    ra: float,
    dec: float,
    fov_arcmin: float,
    frames: list[dict],
    stars: list[dict],
    target_year: float | None = None,
) -> dict:
    """Where each Gaia star should be in each frame, in PNG pixels (x to the right, y down, 0 = first
    pixel's centre), plus which star is the target (nearest to the grid centre at target_year)."""
    grid, size = target_grid(ra, dec, fov_arcmin)
    years = [mjd_to_year(f["mjd"]) for f in frames]
    out, target = [], None

    for star in stars:
        xy = []
        for year in years:
            s_ra, s_dec = star_at(star, year)
            x, y = grid.world_to_pixel_values(s_ra, s_dec)
            xy.append([round(float(x), 3), round(float(size - 1 - y), 3)])

        if not any(
            -0.5 - MARGIN_PX <= x <= size - 0.5 + MARGIN_PX
            and -0.5 - MARGIN_PX <= y <= size - 0.5 + MARGIN_PX
            for x, y in xy
        ):
            continue

        entry = {
            "source_id": star["source_id"],
            "g_mag": None if star["g_mag"] is None else round(star["g_mag"], 2),
            "pmra": star["pmra"] and round(star["pmra"], 2),
            "pmdec": star["pmdec"] and round(star["pmdec"], 2),
            "parallax": star["parallax"] and round(star["parallax"], 2),
            "has_motion": star["pmra"] is not None,
            "xy": xy,
        }
        out.append(entry)

        if target_year is not None:
            sep = separation_arcsec(*star_at(star, target_year), ra, dec)
            if sep <= TARGET_MATCH_ARCSEC and (target is None or sep < target[1]):
                target = (entry, sep)

    if target:
        target[0]["target"] = True

    out.sort(key=lambda s: (s["g_mag"] is None, s["g_mag"] if s["g_mag"] is not None else 0))
    return {
        "stars": out,
        "target_match": {"source_id": target[0]["source_id"], "sep_arcsec": round(target[1], 3)} if target else None,
    }


def write_gaia(folder: Path) -> dict:
    """gaia.json for a frames folder.

    If IRSA and ESA are both unreachable, still write an empty gaia.json so the flipbook
    and check_frames can proceed; re-run this module when a catalogue answers again.
    """
    manifest = json.loads((folder / "manifest.json").read_text())
    ra, dec, fov = manifest["ra"], manifest["dec"], manifest["fov_arcmin"]
    frames = manifest["frames"]
    years = [mjd_to_year(f["mjd"]) for f in frames]
    radius = search_radius_deg(fov, max(abs(y - GAIA_EPOCH) for y in years))
    unavailable = None
    try:
        stars = gaia_stars(ra, dec, radius)
    except archive.ArchiveError as exc:
        print(f"  warning: Gaia query failed ({exc}); writing empty gaia.json")
        stars = []
        unavailable = str(exc)

    result = markers(ra, dec, fov, frames, stars, target_year=2026.0)

    gaia = {
        "format": FORMAT,
        "catalogue": f"Gaia DR3 ({GAIA_TABLE} at NASA/IPAC IRSA; ESA fallback when IRSA is down)",
        "catalogue_epoch": GAIA_EPOCH,
        "query": {
            "ra": ra, "dec": dec, "radius_deg": round(radius, 6), "n_returned": len(stars),
            **({"unavailable": unavailable} if unavailable else {}),
        },
        "method": f"each Gaia DR3 position (epoch {GAIA_EPOCH}) moved in a straight line with its proper "
                  "motion to the frame's MJD; parallax not applied; stars without a Gaia proper motion "
                  "stay at their 2016.0 position",
        "pixel_convention": "PNG pixels: x to the right (west), y down (south), 0 = centre of the first pixel",
        "target_match_rule": f"the Gaia star nearest the grid centre at 2026.0, if within {TARGET_MATCH_ARCSEC}″",
        "target_match": result["target_match"],
        "frames": [{"epoch_id": f["epoch_id"], "mjd": f["mjd"], "year": round(y, 4)} for f, y in zip(frames, years)],
        "stars": result["stars"],
        "made_by": "backend/app/gaia.py",
        "made_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "data_credit": "ESA Gaia DR3, via NASA/IPAC IRSA (ESA archive fallback)",
    }
    (folder / "gaia.json").write_text(json.dumps(gaia, indent=1, ensure_ascii=False) + "\n")
    return gaia


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("folders", type=Path, nargs="+", help="e.g. frontend/frames/barnard/d2")
    args = parser.parse_args()
    for folder in args.folders:
        g = write_gaia(folder)
        match = g["target_match"]
        target = next((s for s in g["stars"] if s.get("target")), None)
        moved = ""
        if target:
            (x0, y0), (x1, y1) = target["xy"][0], target["xy"][-1]
            moved = f", target moves {math.hypot(x1 - x0, y1 - y0):.2f} px first -> last visit"
        print(f"{folder}: {len(g['stars'])} Gaia stars in the frame ({g['query']['n_returned']} returned), "
              f"target match {match}{moved}")


if __name__ == "__main__":
    main()
