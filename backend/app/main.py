"""The data API and the website, from one server.

    uvicorn backend.app.main:app --port 8000        # then open http://localhost:8000

SPHEREx images come from NASA IRSA (search) and IRSA's public AWS copy (pixels), not from api.nasa.gov.
    /api/health
    /api/resolve?name=                         SIMBAD position and proper motion
    /api/coverage?ra=&dec=[&band=]             SPHEREx images covering the point
    /api/releases                              SPHEREx collection counts and date span
    /api/frames?target=&band=                  manifest of the prepared frames (5 official targets)
    /api/frames?ra=&dec=&band=[&fov_arcmin=]   any position: starts a background job (HTTP 202 and
                                               {"status": "working", "message"} meanwhile), then the same manifest
"""
import importlib
import json
import math
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
from backend.app.motion import position_at, separation_arcsec
from backend.app.resolve import ResolverUnavailable, resolve_name
from backend.app.targets import OFFICIAL_TARGETS

FRONTEND_DIR = REPO_ROOT / "frontend"
PREPARED_DIR = FRONTEND_DIR / "frames"
JOBS_DIR = CACHE_DIR / "frames"
POSITION_YEAR = 2026.0   # SIMBAD positions are moved to this date, like the frames
PREPARED_FOV = 3.0
SAME_TARGET_ARCSEC = 5.0
JOB_EXPOSURES_PER_VISIT = 4   # fewer than the prepared frames (8): each cutout is ~5 MB
COVERAGE_CACHE_SECONDS = 3600
FAILED_JOB_RETRY_SECONDS = 600

app = FastAPI(title="Blinkit API", docs_url="/api/docs", openapi_url="/api/openapi.json")
_coverage_cache: dict[tuple, tuple[float, dict]] = {}


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        self.status, self.message = status, message


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
            prepared = sorted(int(p.name[1:]) for p in (PREPARED_DIR / target).glob("d*")
                              if (p / "manifest.json").exists())
            if len(prepared) >= 2:
                return {"kind": "official_prepare", "key": target, "band": band, "folder": folder,
                        "url": f"/frames/{target}/d{band}/"}
            raise ApiError(404, f"No prepared frames for {target} in D{band}; prepared detectors: "
                                + (", ".join(f"D{d}" for d in prepared) or "none")
                                + f". Make them with: python -m backend.app.render {target} {band}.")
        return {"kind": "prepared", "key": target, "folder": folder, "url": f"/frames/{target}/d{band}/"}
    if ra is None or dec is None:
        raise ApiError(400, "Give either target= or both ra= and dec=")
    if not (0 <= ra < 360 and -90 <= dec <= 90):
        raise ApiError(400, "ra must be 0-360 and dec -90..+90 degrees")
    if not 1 <= fov <= 15:
        raise ApiError(400, "fov_arcmin must be 1-15")
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
AFTER_RENDER_STEPS: list[tuple[str, Callable[[Path], object]]] = []


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
    job = _jobs[str(loc["folder"])]

    def run():
        job["stage"] = "downloading SPHEREx images and adding up each visit"
        render.render_frames(loc["ra"], loc["dec"], loc["key"], f"RA {loc['ra']:.4f}° Dec {loc['dec']:+.4f}°",
                             "typed position, rounded to 0.0001° (not moved for proper motion)", loc["band"],
                             "coadd", JOB_EXPOSURES_PER_VISIT, loc["fov"], JOBS_DIR)
        job["warnings"].extend(_pipeline_after_render(loc["folder"]))

    _finish(job, run, render)


def _run_official_prepare(loc: dict, render: ModuleType) -> None:
    """Download one missing detector for an official target from NASA IRSA into frontend/frames/."""
    job = _jobs[str(loc["folder"])]

    def run():
        job["stage"] = f"asking NASA IRSA for SPHEREx images ({loc['key']} D{loc['band']})"
        loc["folder"].parent.mkdir(parents=True, exist_ok=True)
        render.make_frames(loc["key"], loc["band"])
        job["warnings"].extend(_pipeline_after_render(loc["folder"]))
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
                return {"status": "ready", "warnings": []}
            render = _render()
            job = {"status": "working", "stage": "waiting for the previous job", "warnings": [],
                   "started_at": datetime.now(timezone.utc).strftime("%H:%M UTC")}
            _jobs[str(folder)] = job
            _pool.submit(_run_official_prepare if loc["kind"] == "official_prepare" else _run_job, loc, render)
        return job


def ensure_ready(loc: dict) -> list[str]:
    """Raise the right answer unless the folder is ready; returns warnings."""
    if loc["kind"] == "prepared":
        return []
    job = job_status(loc)
    if job["status"] == "working":
        raise Working(f"Preparing SPHEREx frames for this position (started {job['started_at']}): "
                      f"{job['stage']}. This takes a few minutes.")
    if job["status"] == "none":
        raise ApiError(404, job["error"])
    if job["status"] == "failed":
        raise ApiError(502, f"Could not prepare the frames: {job['error']}")
    return job["warnings"]


def _read(loc: dict, name: str, what: str) -> dict:
    path = loc["folder"] / name
    if not path.exists():
        raise ApiError(404, f"No {what} for this position and detector")
    return json.loads(path.read_text())


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
    try:
        return archive.releases()
    except archive.ArchiveError as exc:
        raise ApiError(502, f"IRSA did not answer: {exc}")


def location(target: str | None = Query(None, description="official target key, e.g. barnard"),
             ra: float | None = None, dec: float | None = None,
             band: int = Query(..., ge=1, le=6), fov_arcmin: float = PREPARED_FOV) -> dict:
    loc = locate(target, ra, dec, band, fov_arcmin)
    loc["warnings"] = ensure_ready(loc)
    return loc


@app.get("/api/frames")
def frames(loc: dict = Depends(location)):
    m = _read(loc, "manifest.json", "frames")
    for f in m["frames"]:
        f["png_url"] = loc["url"] + f["png"]
        if f.get("flags_png"):
            f["flags_png_url"] = loc["url"] + f["flags_png"]
    return {**m, "base_url": loc["url"], "source": loc["kind"], "warnings": loc["warnings"]}


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
