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
ALLWISE_EPOCH = 2010.5589  # approximate AllWISE mid-mission epoch
TARGET_MATCH_ARCSEC = 3.0  # half a SPHEREx pixel
MAX_MOTION_ARCSEC_PER_YEAR = 11.0  # Barnard's Star moves 10.4″/yr
MARGIN_PX = 1.0


def _value(row, name):
    v = row[name]
    return None if np.ma.is_masked(v) or not np.isfinite(float(v)) else float(v)


def _catwise_from_irsa(ra: float, dec: float, radius_deg: float) -> list[dict]:
    cols = ("source_name, ra, dec, sigra, sigdec, pmra, pmdec, sigpmra, sigpmdec, "
            "w1mpro, w1sigmpro, w2mpro, w2sigmpro, w1snr, w2snr")
    adql = f"""
        SELECT {cols} FROM {CATWISE_TABLE}
        WHERE CONTAINS(POINT('ICRS', ra, dec), CIRCLE('ICRS', {ra:.6f}, {dec:.6f}, {radius_deg:.5f})) = 1
    """
    table = archive.run_query(adql)
    sources = []
    for row in table:
        sources.append({
            "source_name": str(row["source_name"]),
            "ra": float(row["ra"]),
            "dec": float(row["dec"]),
            "pmra": _value(row, "pmra"),      # arcsec/yr
            "pmdec": _value(row, "pmdec"),
            "w1_mag": _value(row, "w1mpro"),
            "w2_mag": _value(row, "w2mpro"),
            "w1_snr": _value(row, "w1snr"),
            "w2_snr": _value(row, "w2snr"),
            "catalog": "catwise2020",
            "epoch": CATWISE_EPOCH,
        })
    return sources


def _allwise_from_vizier(ra: float, dec: float, radius_deg: float) -> list[dict]:
    """AllWISE via CDS VizieR — used when IRSA CatWISE TAP is down."""
    from backend.app.vizier_conesearch import cell, cone_search

    table = cone_search("II/328/allwise", ra, dec, radius_deg)
    sources = []
    for row in table:
        name = cell(row, "AllWISE", "Name", "source_name")
        s_ra = cell(row, "RAJ2000", "_RAJ2000", "ra")
        s_dec = cell(row, "DEJ2000", "_DEJ2000", "dec")
        if name is None or s_ra is None or s_dec is None:
            continue
        pmra_mas = cell(row, "pmRA", "pmra")
        pmdec_mas = cell(row, "pmDE", "pmdec")
        sources.append({
            "source_name": str(name),
            "ra": float(s_ra),
            "dec": float(s_dec),
            # Match CatWISE storage: arcsec/yr (AllWISE Vizier pm is mas/yr).
            "pmra": None if pmra_mas is None else float(pmra_mas) / 1000.0,
            "pmdec": None if pmdec_mas is None else float(pmdec_mas) / 1000.0,
            "w1_mag": cell(row, "W1mag", "w1mpro"),
            "w2_mag": cell(row, "W2mag", "w2mpro"),
            "w1_snr": None,
            "w2_snr": None,
            "catalog": "allwise",
            "epoch": ALLWISE_EPOCH,
        })
    return sources


def wise_sources(ra: float, dec: float, radius_deg: float) -> list[dict]:
    """Infrared point sources within radius_deg of (ra, dec), cached on disk.

    Prefer CatWISE2020 at NASA IRSA; if IRSA TAP is down, use AllWISE from CDS VizieR
    so WISE overlays still appear.
    """
    cache_file = CACHE_DIR / "catwise" / f"{ra:.5f}_{dec:+.5f}_{radius_deg:.4f}_wise_overlay.json"
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text())
        except Exception:
            pass

    errors: list[str] = []
    try:
        sources = _catwise_from_irsa(ra, dec, radius_deg)
        print(f"  WISE: {len(sources)} CatWISE2020 sources from IRSA")
    except Exception as irsa_error:
        errors.append(f"IRSA CatWISE: {irsa_error}")
        try:
            sources = _allwise_from_vizier(ra, dec, radius_deg)
            print(f"  WISE: {len(sources)} AllWISE sources from VizieR (IRSA CatWISE unavailable)")
        except Exception as vizier_error:
            errors.append(f"VizieR AllWISE: {vizier_error}")
            raise archive.ArchiveError(
                "WISE catalogue unavailable (" + "; ".join(errors) + ")"
            ) from vizier_error

    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(sources, indent=1))
    return sources


def search_radius_deg(fov_arcmin: float, years_from_epoch: float) -> float:
    """Half the frame diagonal plus maximum proper motion displacement."""
    half_diagonal = fov_arcmin / 60.0 / 2.0 * math.sqrt(2)
    motion_deg = (MAX_MOTION_ARCSEC_PER_YEAR * abs(years_from_epoch) + MARGIN_PX * PIXEL_SCALE_ARCSEC) / 3600.0
    return half_diagonal + motion_deg


def source_at(source: dict, year: float) -> tuple[float, float]:
    """Calculate position at `year` from the catalogue epoch (CatWISE 2015.4 or AllWISE ~2010.6)."""
    if source["pmra"] is None or source["pmdec"] is None:
        return source["ra"], source["dec"]
    # Stored pmra/pmdec are arcsec/year. position_at expects mas/year.
    pmra_mas = source["pmra"] * 1000.0
    pmdec_mas = source["pmdec"] * 1000.0
    epoch = float(source.get("epoch") or CATWISE_EPOCH)
    return position_at(source["ra"], source["dec"], pmra_mas, pmdec_mas, epoch, year)


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
    """wise.json for a frames folder.

    When IRSA TAP is down, still write an empty CatWISE sidecar so the flipbook and
    check_frames can proceed; re-run this module once TAP answers again.
    """
    from backend.app import archive

    manifest = json.loads((folder / "manifest.json").read_text())
    ra, dec, fov = manifest["ra"], manifest["dec"], manifest["fov_arcmin"]
    frames = manifest["frames"]
    years = [mjd_to_year(f["mjd"]) for f in frames]
    radius = search_radius_deg(fov, max(abs(y - CATWISE_EPOCH) for y in years))
    unavailable = None
    try:
        sources = wise_sources(ra, dec, radius)
    except archive.ArchiveError as exc:
        print(f"  warning: WISE catalogue failed ({exc}); writing empty wise.json")
        sources = []
        unavailable = str(exc)

    result = markers(ra, dec, fov, frames, sources, target_year=2026.0)
    catalogs = {s.get("catalog") or "catwise2020" for s in sources}
    used_allwise = catalogs == {"allwise"}
    catalogue = (
        "AllWISE (CDS VizieR II/328/allwise; IRSA CatWISE TAP was unavailable)"
        if used_allwise
        else f"CatWISE2020 ({CATWISE_TABLE} at NASA/IPAC IRSA; AllWISE VizieR backup)"
    )
    epoch_used = ALLWISE_EPOCH if used_allwise else CATWISE_EPOCH

    wise = {
        "format": FORMAT,
        "catalogue": catalogue,
        "catalogue_epoch": round(epoch_used, 4),
        "catalogue_mjd": None if used_allwise else CATWISE_MJD,
        "query": {
            "ra": ra,
            "dec": dec,
            "radius_deg": round(radius, 6),
            "n_returned": len(sources),
            **({"unavailable": unavailable} if unavailable else {}),
        },
        "method": (
            f"each catalogue position (epoch {round(epoch_used, 4)}) moved in a straight line with "
            "its proper motion (stored as arcsec/yr, applied as mas/yr) to the frame's MJD; "
            f"sources without proper motion stay at their {round(epoch_used, 4)} position"
        ),
        "pixel_convention": "PNG pixels: x to the right (west), y down (south), 0 = centre of the first pixel",
        "target_match_rule": f"the IR source nearest the grid centre at 2026.0, if within {TARGET_MATCH_ARCSEC}″",
        "target_match": result["target_match"],
        "frames": [{"epoch_id": f["epoch_id"], "mjd": f["mjd"], "year": round(y, 4)} for f, y in zip(frames, years)],
        "sources": result["sources"],
        "made_by": "backend/app/wise.py",
        "made_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "data_credit": (
            "AllWISE (Cutri et al.), via CDS VizieR"
            if used_allwise
            else "CatWISE2020 (Eisenhardt et al. 2020, Marocco et al. 2021), via NASA/IPAC IRSA"
        ),
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

