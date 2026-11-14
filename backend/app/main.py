"""The data API and the website, from one server.

    uvicorn backend.app.main:app --port 8000        # then open http://localhost:8000

SPHEREx images come from NASA IRSA (search) and IRSA's public AWS copy (pixels), not from api.nasa.gov.
    /api/health
    /api/resolve?name=                         SIMBAD position and proper motion
    /api/coverage?ra=&dec=[&band=]             SPHEREx images covering the point
    /api/releases                              SPHEREx collection counts and date span
"""
import time
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app import archive
from backend.app.coverage import coverage_answer
from backend.app.motion import position_at, separation_arcsec
from backend.app.resolve import ResolverUnavailable, resolve_name

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = REPO_ROOT / "frontend"
POSITION_YEAR = 2026.0   # SIMBAD positions are moved to this date, like the frames
COVERAGE_CACHE_SECONDS = 3600

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


# ---------- endpoints ----------

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


app.mount("/", RevalidatedFiles(directory=FRONTEND_DIR, html=True), name="site")
