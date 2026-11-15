"""The data API and the website, from one server.

    uvicorn backend.app.main:app --port 8000        # then open http://localhost:8000

SPHEREx images come from NASA IRSA (search) and IRSA's public AWS copy (pixels), not from api.nasa.gov.
    /api/health
    /api/resolve?name=                         SIMBAD position and proper motion
    /api/coverage?ra=&dec=[&band=]             SPHEREx images covering the point
    /api/releases                              SPHEREx collections at IRSA + which ones we search
    /api/gaia /api/wise                        marker sidecars for the current frames folder (when present)
    /api/diff                                  difference maps (diff.json)
    /api/proof                                 measured motion vs Gaia (proof.json)
    /api/stack[?visits=0,1,2]                  visit coadd (stack.json); visits= remakes for a subset
    /api/frames?target=&band=                  manifest of the prepared frames (5 official targets)
    /api/frames?ra=&dec=&band=[&fov_arcmin=]   any position: starts a background job (HTTP 202 and
                                               {"status": "working", "message"} meanwhile), then the same manifest
"""
import importlib
import json
import math
import os
import re
import threading
import time
import traceback
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType

from fastapi import Depends, FastAPI, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app import archive
from backend.app.config import CACHE_DIR, DETECTORS, REPO_ROOT
from backend.app.coverage import coverage_answer
from backend.app.diff import write_diff, write_minus_median
from backend.app.gaia import write_gaia
from backend.app.motion import position_at, separation_arcsec
from backend.app.proof import write_proof
from backend.app.resolve import ResolverUnavailable, resolve_name
from backend.app.stack import write_stack
from backend.app.targets import OFFICIAL_TARGETS
from backend.app.wise import write_wise

FRONTEND_DIR = REPO_ROOT / "frontend"
PREPARED_DIR = FRONTEND_DIR / "frames"
JOBS_DIR = CACHE_DIR / "frames"
POSITION_YEAR = 2026.0   # SIMBAD positions are moved to this date, like the frames
PREPARED_FOV = 3.0
SAME_TARGET_ARCSEC = 5.0
JOB_EXPOSURES_PER_VISIT = 3   # fewer than prepared (8): cutouts are ~5 MB; 3 keeps visits usable and faster
COVERAGE_CACHE_SECONDS = 3600
FAILED_JOB_RETRY_SECONDS = 600
PIPELINE_WARNINGS_FILE = "pipeline_warnings.txt"

_DOCS = None if os.environ.get("BLINKIT_DISABLE_DOCS", "").lower() in {"1", "true", "yes"} else "/api/docs"
app = FastAPI(
    title="Blinkit API",
    docs_url=_DOCS,
    openapi_url=None if _DOCS is None else "/api/openapi.json",
)
_coverage_cache: dict[tuple, tuple[float, dict]] = {}

_ARCHIVE_PUBLIC = (
    "NASA’s IRSA archive did not answer (or timed out). Blinkit is working — this is on IRSA’s side, "
    "not our server. Try again in a few minutes."
)
_OVERLAY_PUBLIC = (
    "Star-catalogue overlays (Gaia / WISE) could not be refreshed right now "
    "(IRSA and the backup catalogues did not answer). The flipbook still works; try overlays again later."
)


def public_message(raw: str, *, overlay: bool = False) -> str:
    """Rewrite raw TAP/502 archive failures into visitor-safe copy; leave other errors alone."""
    text = str(raw or "").strip()
    if not text:
        return ""
    low = text.lower()
    if any(k in low for k in ("irsa", "tap", "502", "proxy error", "timed out", "timeout",
                              "esa gaia", "catwise", "archiveerror")):
        return _OVERLAY_PUBLIC if overlay else _ARCHIVE_PUBLIC
    return text


def public_warnings(raw: list[str]) -> list[str]:
    out: list[str] = []
    for item in raw or []:
        overlay = bool(re.search(r"gaia|wise|catwise|marker", str(item), re.I))
        msg = public_message(item, overlay=overlay)
        if msg and msg not in out:
            out.append(msg)
    return out


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        self.status, self.message = status, public_message(message)


class Working(Exception):
    """A background job is still preparing this answer (HTTP 202; the website asks again)."""


@app.exception_handler(ApiError)
async def _api_error(_, exc: ApiError):
    return JSONResponse({"error": exc.message}, status_code=exc.status)


@app.exception_handler(Working)
async def _working(_, exc: Working):
    return JSONResponse({"status": "working", "message": str(exc)}, status_code=202)


@app.exception_handler(RequestValidationError)
async def _bad_request(_, exc: RequestValidationError):
    problems = "; ".join(f"{'.'.join(str(p) for p in e['loc'][1:])}: {e['msg']}" for e in exc.errors())
    return JSONResponse({"error": f"Bad request ({problems})"}, status_code=400)


def _official_positions() -> dict[str, tuple[float, float]]:
    """Grid centres of the prepared frames (from their manifests, so they match exactly)."""
    positions = {}
    for path in PREPARED_DIR.glob("*/d*/manifest.json"):
        m = json.loads(path.read_text())
        positions[m["target"]] = (m["ra"], m["dec"])
    return positions


def _job_key(ra: float, dec: float, fov: float) -> str:
    return f"pos_{ra:.4f}_{'p' if dec >= 0 else 'm'}{abs(dec):.4f}_fov{fov:g}"


def locate(target: str | None, ra: float | None, dec: float | None, band: int, fov: float) -> dict:
    """Which folder answers this request: a prepared official target, or a job folder for a position."""
    if band not in DETECTORS:
        raise ApiError(400, f"band must be 1-6, got {band}")
    if target is not None:
        if target not in {t["key"] for t in OFFICIAL_TARGETS}:
            raise ApiError(404, f"Unknown target {target!r}; official targets: "
                                + ", ".join(t["key"] for t in OFFICIAL_TARGETS))
        folder = PREPARED_DIR / target / f"d{band}"
        if not (folder / "manifest.json").exists():
            return {"kind": "official_prepare", "key": target, "band": band, "folder": folder,
                    "url": f"/frames/{target}/d{band}/"}
        return {"kind": "prepared", "key": target, "folder": folder, "url": f"/frames/{target}/d{band}/"}
    if ra is None or dec is None:
        raise ApiError(400, "Give either target= or both ra= and dec=")
    if not (0 <= ra < 360 and -90 <= dec <= 90):
        raise ApiError(400, "ra must be 0-360 and dec -90..+90 degrees")
    if not 1 <= fov <= 30:
        raise ApiError(400, "fov_arcmin must be 1-30")
    if math.isclose(fov, PREPARED_FOV):
        for key, (tra, tdec) in _official_positions().items():
            if (separation_arcsec(ra, dec, tra, tdec) < SAME_TARGET_ARCSEC
                    and (PREPARED_DIR / key / f"d{band}" / "manifest.json").exists()):
                return locate(key, None, None, band, fov)
    key = _job_key(ra, dec, fov)
    return {"kind": "job", "key": key, "folder": JOBS_DIR / key / f"d{band}", "url": f"/jobframes/{key}/d{band}/",
            "ra": round(ra, 4), "dec": round(dec, 4), "fov": fov, "band": band}


_pool = ThreadPoolExecutor(max_workers=1)   # one job at a time: IRSA answers "503 busy" to more
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()

# Run on every new frames folder after render, as (stage, step(folder)); a failed step is a warning, not a failure.
AFTER_RENDER_STEPS: list[tuple[str, Callable[[Path], object]]] = [
    ("Gaia DR3 markers", write_gaia),
    ("CatWISE2020 markers", write_wise),
    ("difference maps", write_diff),
    ("minus-median frames", write_minus_median),
    ("visit stack", write_stack),
    ("proof panel", write_proof),
]


def _render() -> ModuleType:
    """The frame maker (backend/app/render.py), imported when a job starts: it pulls in astropy and
    reproject, and the API must keep serving prepared folders where it is not installed."""
    try:
        return importlib.import_module("backend.app.render")
    except ModuleNotFoundError as exc:
        if exc.name != "backend.app.render":
            raise
        raise ApiError(503, "Making frames for a new position needs backend/app/render.py, which is not in this "
                            "build yet. The prepared targets in frontend/frames/ still work.")


def _pipeline_after_render(folder: Path) -> list[str]:
    warnings: list[str] = []
    for stage, step in AFTER_RENDER_STEPS:
        try:
            step(folder)
        except Exception as exc:
            warnings.append(f"{stage} failed: {exc}")
    return warnings


def _save_pipeline_warnings(folder: Path, warnings: list[str]) -> None:
    path = folder / PIPELINE_WARNINGS_FILE
    if warnings:
        path.write_text("\n".join(warnings) + "\n")
    elif path.exists():
        path.unlink()


def _load_pipeline_warnings(folder: Path) -> list[str]:
    path = folder / PIPELINE_WARNINGS_FILE
    if not path.exists():
        return []
    return [line for line in path.read_text().splitlines() if line.strip()]


def _finish(job: dict, run: Callable[[], None], render: ModuleType) -> None:
    try:
        run()
        job.update(status="ready", stage="done")
    except render.NoImages as exc:
        job.update(status="none", error=str(exc))
    except Exception as exc:
        job.update(status="failed", error=f"{exc.__class__.__name__}: {exc}", failed_at=time.time())
        traceback.print_exc()


def _run_job(loc: dict, render: ModuleType) -> None:
    """Build SPHEREx frames, open the flipbook as soon as they exist, then finish overlays."""
    job = _jobs[str(loc["folder"])]
    try:
        job["stage"] = "downloading SPHEREx images and adding up each visit"
        render.render_frames(
            loc["ra"], loc["dec"], loc["key"], f"RA {loc['ra']:.4f}° Dec {loc['dec']:+.4f}°",
            "typed position, rounded to 0.0001° (not moved for proper motion)", loc["band"],
            "coadd", JOB_EXPOSURES_PER_VISIT, loc["fov"], JOBS_DIR,
            write_sidecars=False,
        )
        # Flipbook only needs the visit PNGs + manifest — do not wait on Gaia/WISE/proof.
        job.update(status="ready", stage="frames ready; finishing overlays")
        job["stage"] = "building difference maps and overlays"
        job["warnings"].extend(_pipeline_after_render(loc["folder"]))
        _save_pipeline_warnings(loc["folder"], job["warnings"])
        job["stage"] = "done"
    except render.NoImages as exc:
        job.update(status="none", error=str(exc))
    except Exception as exc:
        job.update(status="failed", error=f"{exc.__class__.__name__}: {exc}", failed_at=time.time())
        traceback.print_exc()


def _run_official_prepare(loc: dict, render: ModuleType) -> None:
    """Download one missing detector for an official target from NASA IRSA into frontend/frames/."""
    job = _jobs[str(loc["folder"])]

    def run():
        job["stage"] = f"asking NASA IRSA for SPHEREx images ({loc['key']} D{loc['band']})"
        loc["folder"].parent.mkdir(parents=True, exist_ok=True)
        render.make_frames(loc["key"], loc["band"])
        job["warnings"].extend(_pipeline_after_render(loc["folder"]))
        _save_pipeline_warnings(loc["folder"], job["warnings"])
        render.write_index(PREPARED_DIR)

    _finish(job, run, render)


def job_status(loc: dict) -> dict:
    """Start the job if needed; returns its state."""
    folder = loc["folder"]
    with _jobs_lock:
        job = _jobs.get(str(folder))
        if job and job["status"] == "failed" and time.time() - job["failed_at"] > FAILED_JOB_RETRY_SECONDS:
            job = None
        if job is None:
            if (folder / "manifest.json").exists():
                return {"status": "ready", "warnings": public_warnings(_load_pipeline_warnings(folder))}
            render = _render()
            job = {"status": "working", "stage": "waiting for the previous job", "warnings": [],
                   "started_at": datetime.now(timezone.utc).strftime("%H:%M UTC")}
            _jobs[str(folder)] = job
            _pool.submit(_run_official_prepare if loc["kind"] == "official_prepare" else _run_job, loc, render)
        return job


def ensure_ready(loc: dict) -> list[str]:
    """Raise the right answer unless the folder is ready; returns visitor-safe warnings."""
    if loc["kind"] == "prepared":
        return public_warnings(_load_pipeline_warnings(loc["folder"]))
    job = job_status(loc)
    if job["status"] == "working":
        raise Working(f"Preparing SPHEREx frames for this position (started {job['started_at']}): "
                      f"{job['stage']}. Flipbook opens as soon as the visit images are ready.")
    if job["status"] == "none":
        raise ApiError(404, job["error"])
    if job["status"] == "failed":
        raise ApiError(502, f"Could not prepare the frames: {job['error']}")
    return public_warnings(job.get("warnings") or [])


def _read(loc: dict, name: str, what: str) -> dict:
    path = loc["folder"] / name
    if not path.exists():
        raise ApiError(404, f"No {what} for this position and detector")
    return json.loads(path.read_text())


def _sidecar_incomplete(data: dict | None, items_key: str) -> bool:
    if not data:
        return True
    if (data.get("query") or {}).get("unavailable"):
        return True
    return not (data.get(items_key) or [])


def _refresh_overlay(loc: dict, name: str, items_key: str, writer) -> dict:
    """Rebuild gaia.json / wise.json when the on-disk copy is empty or marked unavailable."""
    path = loc["folder"] / name
    data = json.loads(path.read_text()) if path.exists() else None
    if not _sidecar_incomplete(data, items_key):
        return data
    if not (loc["folder"] / "manifest.json").exists():
        raise ApiError(404, f"No {name} for this position and detector")
    try:
        data = writer(loc["folder"])
    except Exception as exc:
        if data is not None:
            return data
        raise ApiError(502, f"Catalogue overlay unavailable: {exc}") from exc
    if not _sidecar_incomplete(data, items_key):
        # Drop stale IRSA-overlay lines so /api/frames stops alarming visitors.
        warns = [
            line for line in _load_pipeline_warnings(loc["folder"])
            if not re.search(r"gaia|wise|catwise|marker", line, re.I)
        ]
        _save_pipeline_warnings(loc["folder"], warns)
    return data


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/resolve")
def resolve(name: str = Query(..., min_length=1, max_length=100)):
    try:
        star = resolve_name(name)
    except LookupError as exc:
        raise ApiError(404, str(exc))
    except ResolverUnavailable as exc:
        raise ApiError(503, str(exc))
    moved = None
    if star["pmra"] is not None and star["pmdec"] is not None:
        ra, dec = position_at(star["ra"], star["dec"], star["pmra"], star["pmdec"], star["epoch"], POSITION_YEAR)
        moved = {"ra": ra, "dec": dec, "year": POSITION_YEAR,
                 "moved_arcsec": round(separation_arcsec(star["ra"], star["dec"], ra, dec), 2)}
    return {**star, "source": f"SIMBAD ({star['server']})", "position_now": moved}


@app.get("/api/coverage")
def coverage(
    ra: float = Query(..., ge=0, lt=360),
    dec: float = Query(..., ge=-90, le=90),
    band: int | None = Query(None, ge=1, le=6),
):
    key = (round(ra, 5), round(dec, 5), band)
    cached = _coverage_cache.get(key)
    if cached and time.time() - cached[0] < COVERAGE_CACHE_SECONDS:
        return cached[1]
    try:
        answer = coverage_answer(ra, dec, band)
    except archive.ArchiveError as exc:
        raise ApiError(502, f"IRSA did not answer: {exc}")
    _coverage_cache[key] = (time.time(), answer)
    return answer


@app.get("/api/releases")
def releases():
    """Active IRSA SPHEREx collections, what we search, and any new ones not yet enabled."""
    try:
        return archive.releases_report()
    except archive.ArchiveError as exc:
        raise ApiError(502, f"IRSA did not answer: {exc}")


def location(target: str | None = Query(None, description="official target key, e.g. barnard"),
             ra: float | None = None, dec: float | None = None,
             band: int = Query(..., ge=1, le=6), fov_arcmin: float = PREPARED_FOV) -> dict:
    loc = locate(target, ra, dec, band, fov_arcmin)
    loc["warnings"] = ensure_ready(loc)
    return loc


def _overlay_warnings_still_needed(folder: Path, warnings: list[str]) -> list[str]:
    """Drop Gaia/WISE IRSA complaints once on-disk sidecars have real markers again."""
    gaia_path, wise_path = folder / "gaia.json", folder / "wise.json"
    gaia = json.loads(gaia_path.read_text()) if gaia_path.exists() else None
    wise = json.loads(wise_path.read_text()) if wise_path.exists() else None
    if not _sidecar_incomplete(gaia, "stars") and not _sidecar_incomplete(wise, "sources"):
        return [
            w for w in warnings
            if not re.search(r"gaia|wise|catwise|marker", str(w), re.I)
        ]
    return warnings


@app.get("/api/frames")
def frames(loc: dict = Depends(location)):
    m = _read(loc, "manifest.json", "frames")
    for f in m["frames"]:
        f["png_url"] = loc["url"] + f["png"]
        if f.get("flags_png"):
            f["flags_png_url"] = loc["url"] + f["flags_png"]
    warnings = _overlay_warnings_still_needed(loc["folder"], loc["warnings"])
    return {**m, "base_url": loc["url"], "source": loc["kind"], "warnings": warnings}


@app.get("/api/gaia")
def gaia(loc: dict = Depends(location)):
    return _refresh_overlay(loc, "gaia.json", "stars", write_gaia)


@app.get("/api/wise")
def wise(loc: dict = Depends(location)):
    return _refresh_overlay(loc, "wise.json", "sources", write_wise)


@app.get("/api/diff")
def diff(loc: dict = Depends(location)):
    d = _read(loc, "diff.json", "difference maps")
    for p in d.get("pairs", []):
        p["png_url"] = loc["url"] + p["png"]
    for f in d.get("minus_median", {}).get("frames", []):
        f["png_url"] = loc["url"] + f["png"]
    if d.get("minus_median", {}).get("median_png"):
        d["minus_median"]["median_png_url"] = loc["url"] + d["minus_median"]["median_png"]
    return {**d, "base_url": loc["url"]}


@app.get("/api/proof")
def proof(loc: dict = Depends(location)):
    return _read(loc, "proof.json", "proof panel data")


def _parse_visits(text: str | None) -> list[int] | None:
    if text is None or text.strip() == "":
        return None
    parts = [p.strip() for p in text.split(",") if p.strip() != ""]
    if not parts or not all(p.isdigit() for p in parts):
        raise ApiError(400, "visits must be a comma-separated list of visit numbers, e.g. visits=0,1,2")
    return [int(p) for p in parts]


@app.get("/api/stack")
def stack(loc: dict = Depends(location), visits: str | None = Query(None, description="comma-separated visit ids")):
    wanted = _parse_visits(visits)
    manifest_path = loc["folder"] / "manifest.json"
    if not manifest_path.exists():
        raise ApiError(404, "No frames for this position and detector")
    all_ids = [f["epoch_id"] for f in json.loads(manifest_path.read_text())["frames"]]
    from backend.app.stack import stack_names
    fits_name, png_name, json_name = stack_names(wanted, all_ids)
    path = loc["folder"] / json_name
    if path.exists() and (wanted is None or json.loads(path.read_text()).get("visits") == wanted):
        data = json.loads(path.read_text())
    else:
        try:
            data = write_stack(loc["folder"], visits=wanted)
        except FileNotFoundError as exc:
            raise ApiError(404, str(exc))
        except ValueError as exc:
            raise ApiError(400, str(exc))
    png = data.get("png", png_name)
    fits = data.get("fits", fits_name)
    return {**data, "base_url": loc["url"], "png_url": loc["url"] + png, "fits_url": loc["url"] + fits}


@app.get("/api/{rest:path}")
def unknown(rest: str):
    raise ApiError(404, f"No such API endpoint: /api/{rest}")


class RevalidatedFiles(StaticFiles):
    """Browsers must check the ETag before reusing a file: otherwise a cached app.js keeps running after an
    update while its new modules and data are already served."""

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response


JOBS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/jobframes", RevalidatedFiles(directory=JOBS_DIR), name="jobframes")
app.mount("/", RevalidatedFiles(directory=FRONTEND_DIR, html=True), name="site")
