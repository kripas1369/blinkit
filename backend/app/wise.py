"""CatWISE2020 sources in the frames' field, moved to the date of each visit.

CatWISE2020 gives infrared point source positions at epoch MJD 57170 (2015.4)
and proper motions in arcsec/year. Moving each source to the time of each SPHEREx visit
tells us where it should be in that frame.

    python -m backend.app.wise frontend/frames/barnard/d2
"""
import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from backend.app import archive
from backend.app.align import target_grid
from backend.app.config import CACHE_DIR, PIXEL_SCALE_ARCSEC
from backend.app.coords import mjd_to_year
from backend.app.motion import position_at, separation_arcsec

FORMAT = "spherex-blink-wise/1"
CATWISE_TABLE = "catwise_2020"
CATWISE_MJD = 57170.0
CATWISE_EPOCH = 2015.4018  # mjd_to_year(57170.0)
TARGET_MATCH_ARCSEC = 3.0  # half a SPHEREx pixel
MAX_MOTION_ARCSEC_PER_YEAR = 11.0  # Barnard's Star moves 10.4″/yr
MARGIN_PX = 1.0


def wise_sources(ra: float, dec: float, radius_deg: float) -> list[dict]:
    """CatWISE2020 sources within radius_deg of (ra, dec), cached on disk."""
    cache_file = CACHE_DIR / "catwise" / f"{ra:.5f}_{dec:+.5f}_{radius_deg:.4f}_catwise.json"
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text())
        except Exception:
            pass

    cols = ("source_name, ra, dec, sigra, sigdec, pmra, pmdec, sigpmra, sigpmdec, "
            "w1mpro, w1sigmpro, w2mpro, w2sigmpro, w1snr, w2snr")
    adql = f"""
        SELECT {cols} FROM {CATWISE_TABLE}
        WHERE CONTAINS(POINT('ICRS', ra, dec), CIRCLE('ICRS', {ra:.6f}, {dec:.6f}, {radius_deg:.5f})) = 1
    """
    table = archive.run_query(adql)

    def value(row, name):
        v = row[name]
        return None if np.ma.is_masked(v) or not np.isfinite(float(v)) else float(v)

    sources = []
    for row in table:
        pmra_asec = value(row, "pmra")
        pmdec_asec = value(row, "pmdec")
        sources.append({
            "source_name": str(row["source_name"]),
            "ra": float(row["ra"]),
            "dec": float(row["dec"]),
            "pmra": pmra_asec,      # in arcsec/yr (CatWISE unit)
            "pmdec": pmdec_asec,    # in arcsec/yr (CatWISE unit)
            "w1_mag": value(row, "w1mpro"),
            "w2_mag": value(row, "w2mpro"),
            "w1_snr": value(row, "w1snr"),
            "w2_snr": value(row, "w2snr"),
        })

    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(sources, indent=1))
    return sources


def search_radius_deg(fov_arcmin: float, years_from_epoch: float) -> float:
    """Half the frame diagonal plus maximum proper motion displacement."""
    half_diagonal = fov_arcmin / 60.0 / 2.0 * math.sqrt(2)
    motion_deg = (MAX_MOTION_ARCSEC_PER_YEAR * abs(years_from_epoch) + MARGIN_PX * PIXEL_SCALE_ARCSEC) / 3600.0
    return half_diagonal + motion_deg


def source_at(source: dict, year: float) -> tuple[float, float]:
    """Calculate position at `year` from CatWISE epoch (2015.4)."""
    if source["pmra"] is None or source["pmdec"] is None:
        return source["ra"], source["dec"]
    # CatWISE pmra and pmdec are in arcsec/year. position_at expects mas/year.
    pmra_mas = source["pmra"] * 1000.0
    pmdec_mas = source["pmdec"] * 1000.0
    return position_at(source["ra"], source["dec"], pmra_mas, pmdec_mas, CATWISE_EPOCH, year)


def markers(
    ra: float,
    dec: float,
    fov_arcmin: float,
    frames: list[dict],
    sources: list[dict],
    target_year: float | None = None,
) -> dict:
    """Project CatWISE sources onto the frame PNG pixels (x right, y down)."""
    grid, size = target_grid(ra, dec, fov_arcmin)
    years = [mjd_to_year(f["mjd"]) for f in frames]
    out, target = [], None

    for src in sources:
        xy = []
        for year in years:
            s_ra, s_dec = source_at(src, year)
            x, y = grid.world_to_pixel_values(s_ra, s_dec)
            xy.append([round(float(x), 3), round(float(size - 1 - y), 3)])

        if not any(
            -0.5 - MARGIN_PX <= x <= size - 0.5 + MARGIN_PX
            and -0.5 - MARGIN_PX <= y <= size - 0.5 + MARGIN_PX
            for x, y in xy
        ):
            continue

        entry = {
            "source_name": src["source_name"],
            "w1_mag": None if src["w1_mag"] is None else round(float(src["w1_mag"]), 2),
            "w2_mag": None if src["w2_mag"] is None else round(float(src["w2_mag"]), 2),
            "pmra": round(float(src["pmra"]), 3) if src["pmra"] is not None else None,
            "pmdec": round(float(src["pmdec"]), 3) if src["pmdec"] is not None else None,
            "has_motion": src["pmra"] is not None,
            "xy": xy,
        }
        out.append(entry)

        if target_year is not None:
            sep = separation_arcsec(*source_at(src, target_year), ra, dec)
            if sep <= TARGET_MATCH_ARCSEC and (target is None or sep < target[1]):
                target = (entry, sep)

    if target:
        target[0]["target"] = True

    out.sort(key=lambda s: (s["w1_mag"] is None, s["w1_mag"] if s["w1_mag"] is not None else 0))
    return {
        "sources": out,
        "target_match": {"source_name": target[0]["source_name"], "sep_arcsec": round(target[1], 3)} if target else None,
    }


def write_wise(folder: Path) -> dict:
    """wise.json for a frames folder."""
    manifest = json.loads((folder / "manifest.json").read_text())
    ra, dec, fov = manifest["ra"], manifest["dec"], manifest["fov_arcmin"]
    frames = manifest["frames"]
    years = [mjd_to_year(f["mjd"]) for f in frames]
    radius = search_radius_deg(fov, max(abs(y - CATWISE_EPOCH) for y in years))
    sources = wise_sources(ra, dec, radius)
    result = markers(ra, dec, fov, frames, sources, target_year=2026.0)

    wise = {
        "format": FORMAT,
        "catalogue": f"CatWISE2020 ({CATWISE_TABLE} at NASA/IPAC IRSA)",
        "catalogue_epoch": round(CATWISE_EPOCH, 4),
        "catalogue_mjd": CATWISE_MJD,
        "query": {
            "ra": ra,
            "dec": dec,
            "radius_deg": round(radius, 6),
            "n_returned": len(sources),
        },
        "method": (
            f"each CatWISE2020 position (epoch {round(CATWISE_EPOCH, 4)}) moved in a straight line with "
            "its proper motion (pmra/pmdec in arcsec/yr converted to mas/yr) to the frame's MJD; "
            f"sources without proper motion stay at their {round(CATWISE_EPOCH, 4)} position"
        ),
        "pixel_convention": "PNG pixels: x to the right (west), y down (south), 0 = centre of the first pixel",
        "target_match_rule": f"the CatWISE source nearest the grid centre at 2026.0, if within {TARGET_MATCH_ARCSEC}″",
        "target_match": result["target_match"],
        "frames": [{"epoch_id": f["epoch_id"], "mjd": f["mjd"], "year": round(y, 4)} for f, y in zip(frames, years)],
        "sources": result["sources"],
        "made_by": "backend/app/wise.py",
        "made_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "data_credit": "CatWISE2020 (Eisenhardt et al. 2020, Marocco et al. 2021), via NASA/IPAC IRSA",
    }
    (folder / "wise.json").write_text(json.dumps(wise, indent=1, ensure_ascii=False) + "\n")
    return wise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("folders", type=Path, nargs="+", help="e.g. frontend/frames/barnard/d2")
    args = parser.parse_args()
    for folder in args.folders:
        w = write_wise(folder)
        match = w["target_match"]
        target = next((s for s in w["sources"] if s.get("target")), None)
        moved = ""
        if target:
            (x0, y0), (x1, y1) = target["xy"][0], target["xy"][-1]
            moved = f", target moves {math.hypot(x1 - x0, y1 - y0):.2f} px first -> last visit"
        print(f"{folder}: {len(w['sources'])} CatWISE sources in the frame ({w['query']['n_returned']} returned), "
              f"target match {match}{moved}")


if __name__ == "__main__":
    main()

