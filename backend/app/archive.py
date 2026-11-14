"""Ask NASA's IRSA archive which SPHEREx images cover a position, and download small cutouts."""
import concurrent.futures as cf
import io
import json
import threading
import time
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import pyvo
import requests
from astropy.io import fits, votable

from backend.app.config import (
    CACHE_DIR, COLLECTIONS, CUTOUT_CACHE_MAX_GB, CUTOUT_URL, DETECTORS, DROP_PSF_FROM_CUTOUTS,
    MAX_PARALLEL_DOWNLOADS, RETRIES, SPHEREX_PIXELS, TAP_URL,
)
from backend.app.coords import mjd_to_date
from backend.app.flags import bad_pixel_bitmask, flag_bits


class ArchiveError(RuntimeError):
    """The archive did not answer, or answered with something we cannot use."""


class NotInImage(ArchiveError):
    """The requested position is outside this image (the cutout service says 404)."""


@dataclass
class SpherexImage:
    obs_id: str          # one exposure; each exposure gives two images (paired detectors)
    did: str             # unique id of this image (exposure + detector)
    detector: int        # 1..6
    mjd_start: float     # t_min from the archive (MJD)
    mjd_end: float       # t_max from the archive (MJD)
    wl_min_um: float
    wl_max_um: float
    release_date: str
    collection: str = ""     # e.g. "spherex_qr3" (data release) or "spherex_qr2_deep" (deep field)
    path: str | None = None  # file path for the cutout service, filled by attach_paths()
    s3_key: str | None = None  # AWS S3 key, e.g. dr1/level2/...fits

    @property
    def mjd(self) -> float:
        return (self.mjd_start + self.mjd_end) / 2


TAP_TIMEOUT_SECONDS = 300
_IRSA_CUTOUT_SEMAPHORE = threading.Semaphore(MAX_PARALLEL_DOWNLOADS)


class _TimedSession(requests.Session):
    """pyvo sets no timeout, so a silently dropped connection would wait forever."""

    def request(self, *args, **kwargs):
        kwargs.setdefault("timeout", TAP_TIMEOUT_SECONDS)
        return super().request(*args, **kwargs)


@lru_cache(maxsize=1)
def _tap() -> pyvo.dal.TAPService:
    return pyvo.dal.TAPService(TAP_URL, session=_TimedSession())


def _run(adql: str):
    """Run an ADQL query, retrying when IRSA drops the connection or times out."""
    last = None
    for attempt in range(RETRIES):
        try:
            return _tap().run_sync(adql, maxrec=200_000).to_table()
        except (pyvo.dal.DALFormatError, pyvo.dal.DALServiceError, requests.ConnectionError,
                requests.Timeout) as exc:
            last = exc
            time.sleep(2 ** attempt)
    raise ArchiveError(f"IRSA TAP did not answer after {RETRIES} tries: {last}")


def run_query(adql: str):
    """Any ADQL query on IRSA TAP (e.g. Gaia DR3), with the same retries and timeout."""
    return _run(adql)


@lru_cache(maxsize=1)
def _discover_collections_cached(ttl_hour: int) -> list[str]:
    table = _run("SELECT DISTINCT obs_collection FROM spherex.obscore ORDER BY obs_collection")
    return [
        str(row["obs_collection"])
        for row in table
        if str(row["obs_collection"]).startswith("spherex_")
        and not str(row["obs_collection"]).endswith("_cal")
    ]


def discover_collections() -> list[str]:
    """Active science collections in spherex.obscore (excludes _cal tables; cached 1 hour)."""
    return _discover_collections_cached(int(time.time() // 3600))


@lru_cache(maxsize=1)
def _releases_cached(ttl_hour: int) -> list[dict]:
    cols = discover_collections()
    out = []
    for col in cols:
        adql = f"""
            SELECT COUNT(*) as n_images, MIN(t_min) as min_mjd, MAX(t_max) as max_mjd
            FROM spherex.obscore
            WHERE obs_collection = '{col}'
        """
        table = _run(adql)
        row = table[0]
        min_mjd = float(row["min_mjd"])
        max_mjd = float(row["max_mjd"])
        out.append({
            "collection": col,
            "n_images": int(row["n_images"]),
            "min_mjd": min_mjd,
            "max_mjd": max_mjd,
            "first": mjd_to_date(min_mjd)[:10],
            "last": mjd_to_date(max_mjd)[:10],
        })
    return out


def releases() -> list[dict]:
    """For each active collection, image count and first/last observation dates (cached 1 hour)."""
    return _releases_cached(int(time.time() // 3600))


def _fetch_s3_keys_sia(ra: float, dec: float, collections: tuple[str, ...]) -> dict[str, str]:
    """Query IRSA SIA2 to retrieve AWS S3 keys when obscore cloud_access is empty."""
    s3_keys = {}
    SIA_URL = "https://irsa.ipac.caltech.edu/SIA"
    for col in collections:
        try:
            resp = requests.get(
                SIA_URL,
                params={"COLLECTION": col, "POS": f"CIRCLE {ra:.8f} {dec:.8f} 0.0005", "RESPONSEFORMAT": "VOTABLE"},
                timeout=60,
            )
            if resp.status_code == 200:
                table = votable.parse_single_table(io.BytesIO(resp.content)).to_table(use_names_over_ids=True)
                for row in table:
                    ca_raw = str(row["cloud_access"]).strip() if "cloud_access" in row.colnames else ""
                    if ca_raw:
                        try:
                            ca_json = json.loads(ca_raw)
                            key = ca_json["aws"]["key"]
                            det = _detector_number(str(row["energy_bandpassname"]))
                            s3_keys[f"{row['obs_id']}_{det}"] = key
                            if "obs_publisher_did" in row.colnames:
                                s3_keys[str(row["obs_publisher_did"])] = key
                        except Exception:
                            pass
        except Exception:
            pass
    return s3_keys


def _detector_number(bandpass: str) -> int:
    """"SPHEREx-D3" -> 3."""
    return int(str(bandpass).rsplit("D", 1)[-1])


def find_images(
    ra: float, dec: float, collections: tuple[str, ...] = COLLECTIONS, detector: int | None = None
) -> list[SpherexImage]:
    """Every SPHEREx image whose footprint (s_region) contains the point, sorted by time.

    `detector` limits the search to one detector; for crowded deep fields (R Dra: 2,483 images)
    the full search timed out on 31 Oct while the one-detector search answered in 13 s.
    """
    in_list = ",".join(f"'{c}'" for c in collections)
    one_detector = f"AND energy_bandpassname = 'SPHEREx-D{int(detector)}'" if detector else ""
    adql = f"""
        SELECT obs_id, obs_publisher_did, obs_collection, energy_bandpassname, t_min, t_max,
               em_min, em_max, obs_release_date, cloud_access
        FROM spherex.obscore
        WHERE CONTAINS(POINT('ICRS', {ra:.8f}, {dec:.8f}), s_region) = 1
          AND obs_collection IN ({in_list})
          {one_detector}
    """
    table = _run(adql)
    images = []
    for row in table:
        s3_key = None
        if "cloud_access" in row.colnames:
            ca_raw = str(row["cloud_access"]).strip()
            if ca_raw and ca_raw != "None":
                try:
                    s3_key = json.loads(ca_raw).get("aws", {}).get("key")
                except Exception:
                    pass
        images.append(
            SpherexImage(
                obs_id=str(row["obs_id"]),
                did=str(row["obs_publisher_did"]),
                detector=_detector_number(row["energy_bandpassname"]),
                mjd_start=float(row["t_min"]),
                mjd_end=float(row["t_max"]),
                wl_min_um=float(row["em_min"]) * 1e6,
                wl_max_um=float(row["em_max"]) * 1e6,
                release_date=str(row["obs_release_date"]),
                collection=str(row["obs_collection"]),
                s3_key=s3_key,
            )
        )
    if images and all(im.s3_key is None for im in images):
        s3_map = _fetch_s3_keys_sia(ra, dec, collections)
        for im in images:
            im.s3_key = s3_map.get(im.did) or s3_map.get(f"{im.obs_id}_{im.detector}")

    return sorted(images, key=lambda im: (im.mjd, im.detector))


def attach_paths(images: list[SpherexImage], chunk: int = 200) -> list[SpherexImage]:
    """Fill `path` for each image from the archive's file table, in a few batched queries.

    (The archive cannot join the file table inside a position search, so this is a second step.)
    """
    by_did = {im.did: im for im in images}
    dids = list(by_did)
    for i in range(0, len(dids), chunk):
        in_list = ",".join(f"'{d}'" for d in dids[i:i + chunk])
        table = _run(f"""
            SELECT p.obs_publisher_did, a.uri
            FROM spherex.plane p JOIN spherex.artifact a ON a.planeid = p.planeid
            WHERE a.producttype = 'science' AND p.obs_publisher_did IN ({in_list})
        """)
        for row in table:
            by_did[str(row["obs_publisher_did"])].path = str(row["uri"]).removeprefix("ibe/data/")
    missing = [d for d, im in by_did.items() if im.path is None]
    if missing:
        raise ArchiveError(f"No file path found for {len(missing)} images, e.g. {missing[0]}")
    return images


EPOCH_GAP_DAYS = 30.0
EPOCH_MAX_SPAN_DAYS = 60.0


def group_epochs(
    images: list[SpherexImage], gap_days: float = EPOCH_GAP_DAYS, max_span_days: float = EPOCH_MAX_SPAN_DAYS
) -> list[dict]:
    """Group images into epochs (visits).

    A new epoch starts after a gap longer than `gap_days`, or when the current epoch would last
    longer than `max_span_days`. Most of the sky gets one 2-7 week visit every ~6 months; fields near
    the ecliptic poles (e.g. R Draconis) are observed almost continuously and get split into
    ~2-month epochs instead of one year-long "epoch".
    """
    epochs: list[dict] = []
    for im in sorted(images, key=lambda im: im.mjd):
        if (
            not epochs
            or im.mjd - epochs[-1]["mjd_max"] > gap_days
            or im.mjd - epochs[-1]["mjd_min"] > max_span_days
        ):
            epochs.append({"mjd_min": im.mjd, "mjd_max": im.mjd, "images": []})
        epochs[-1]["mjd_max"] = im.mjd
        epochs[-1]["images"].append(im)
    for i, ep in enumerate(epochs):
        ep["id"] = i
        ep["mjd_mean"] = float(np.mean([im.mjd for im in ep["images"]]))
        ep["date"] = mjd_to_date(ep["mjd_mean"])[:10]
        ep["n_images"] = len(ep["images"])
        ep["per_detector"] = {d: sum(im.detector == d for im in ep["images"]) for d in DETECTORS}
    return epochs


def summarize(images: list[SpherexImage]) -> dict:
    """Counts, dates and epochs for a list of images (used for the coverage table)."""
    if not images:
        return {"n_images": 0}
    epochs = group_epochs(images)
    mjds = [im.mjd for im in images]
    return {
        "n_images": len(images),
        "n_exposures": len({im.obs_id for im in images}),
        "first": mjd_to_date(min(mjds))[:10],
        "last": mjd_to_date(max(mjds))[:10],
        "span_days": round(max(mjds) - min(mjds), 1),
        "per_detector": {d: sum(im.detector == d for im in images) for d in DETECTORS},
        "per_collection": {
            c: n for c in COLLECTIONS if (n := sum(im.collection == c for im in images))
        },
        "n_epochs": len(epochs),
        "epochs": [
            {k: ep[k] for k in ("id", "date", "mjd_min", "mjd_max", "n_images", "per_detector")}
            for ep in epochs
        ],
        "latest_release": max(im.release_date for im in images),
    }


def cutout_file(image: SpherexImage, ra: float, dec: float, size_deg: float) -> Path:
    """Cache location for one cutout (keyed by release collection and obs_id)."""
    col = (image.collection or "unknown").strip().lower()
    name = f"{image.obs_id}_D{image.detector}_{ra:.5f}_{dec:+.5f}_{size_deg:.4f}.fits"
    return CACHE_DIR / "cutouts" / col / name


def download_cutout(image: SpherexImage, ra: float, dec: float, size_deg: float = 0.05) -> Path:
    """Download a small square (size_deg wide) of one image around (ra, dec); cached on disk.

    The service sends every extension (IMAGE, FLAGS, VARIANCE, ZODI, PSF, WCS-WAVE); the full PSF cube
    makes each about 5 MB however small the picture is. With DROP_PSF_FROM_CUTOUTS the PSF is left out
    of the saved file; the other extensions and all headers are kept byte for byte.
    """
    target = cutout_file(image, ra, dec, size_deg)
    if target.exists():
        return target

    # Read bounding box rows directly from S3 when enabled and key is present
    if SPHEREX_PIXELS == "s3" and image.s3_key:
        try:
            from backend.app.s3_reader import S3NotInImage, read_box
            read_box(image.s3_key, ra, dec, size_deg, target_path=target)
            return target
        except S3NotInImage as exc:
            raise NotInImage(str(exc)) from exc
        except Exception as exc:
            print(f"  warning: S3 read failed for {image.did} ({exc}), falling back to IRSA cutout")

    if image.path is None:
        raise ArchiveError("Call attach_paths() before downloading")
    target.parent.mkdir(parents=True, exist_ok=True)

    params = {"ra": ra, "dec": dec, "size": size_deg, "path": image.path}
    last = None
    with _IRSA_CUTOUT_SEMAPHORE:
        for attempt in range(RETRIES):
            try:
                resp = requests.get(CUTOUT_URL, params=params, timeout=180)
            except requests.RequestException as exc:
                last = exc
            else:
                if resp.status_code == 200 and resp.content[:6] == b"SIMPLE":
                    tmp = target.with_suffix(".part")
                    _save_cutout(resp.content, tmp)
                    tmp.rename(target)
                    return target
                if resp.status_code == 404:
                    raise NotInImage(f"{image.did} does not contain RA={ra:.5f} Dec={dec:.5f}")
                last = f"HTTP {resp.status_code}: {resp.text[:100]!r}"
            time.sleep(2 ** attempt)
        raise ArchiveError(f"Cutout failed after {RETRIES} tries for {image.did}: {last}")


def _save_cutout(content: bytes, path: Path) -> None:
    with fits.open(io.BytesIO(content)) as hdul:
        hdul[0].header["PIXSRC"] = ("irsa-cutout", "Pixel source: NASA IRSA cutout service")
        if DROP_PSF_FROM_CUTOUTS:
            kept = fits.HDUList([h for h in hdul if h.name != "PSF"])
        else:
            kept = fits.HDUList(list(hdul))
        kept.writeto(path, overwrite=True, output_verify="silentfix")


def trim_cutout_cache(max_gb: float = CUTOUT_CACHE_MAX_GB) -> int:
    """Delete the least recently used cutouts until the cache is under max_gb; returns files removed."""
    folder = CACHE_DIR / "cutouts"
    if not folder.exists():
        return 0
    files = [(p, p.stat()) for p in folder.rglob("*.fits")]
    total = sum(s.st_size for _, s in files)
    removed = 0
    for path, st in sorted(files, key=lambda f: max(f[1].st_atime, f[1].st_mtime)):
        if total <= max_gb * 1e9:
            break
        path.unlink(missing_ok=True)
        total -= st.st_size
        removed += 1
    return removed


def download_cutouts(
    images: list[SpherexImage], ra: float, dec: float, size_deg: float = 0.05
) -> dict[str, Path | Exception]:
    """Download several cutouts, a few at a time (IRSA says 503 when asked for too many at once)."""
    results: dict[str, Path | Exception] = {}
    workers = 8 if SPHEREX_PIXELS == "s3" else MAX_PARALLEL_DOWNLOADS
    with cf.ThreadPoolExecutor(workers) as pool:
        futures = {pool.submit(download_cutout, im, ra, dec, size_deg): im for im in images}
        for fut in cf.as_completed(futures):
            im = futures[fut]
            try:
                results[im.did] = fut.result()
            except ArchiveError as exc:
                results[im.did] = exc
    return results


def describe_cutout(path: Path) -> dict:
    """What is inside a cutout: extensions, sizes, time keywords, flag bits and % bad pixels."""
    with fits.open(path) as hdul:
        image_header = hdul["IMAGE"].header
        flags_header = hdul["FLAGS"].header
        flags = hdul["FLAGS"].data
        bad = (flags & bad_pixel_bitmask(flags_header)) != 0
        source_bit = flag_bits(flags_header).get("SOURCE")
        return {
            "extensions": [(h.name, tuple(h.data.shape) if h.data is not None else ()) for h in hdul],
            "MJD-AVG": image_header.get("MJD-AVG"),
            "DATE (processing, do not use)": image_header.get("DATE"),
            "DETECTOR": image_header.get("DETECTOR"),
            "BUNIT": image_header.get("BUNIT"),
            "flag_bits": flag_bits(flags_header),
            "pct_bad": round(100 * float(bad.mean()), 1),
            "pct_source": (
                round(100 * float(((flags >> source_bit) & 1).mean()), 1)
                if source_bit is not None else None
            ),
        }


def image_to_dict(image: SpherexImage) -> dict:
    return {**asdict(image), "mjd": image.mjd}
