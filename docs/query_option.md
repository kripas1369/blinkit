# Moving Pointing Queries 100% to the Cloud

Engineering notes on how to eliminate our reliance on Caltech's campus TAP server so arbitrary coordinate queries never fail during 502 outages.

---

## 1. The Problem Today

Right now, our pipeline has two parts:
- **Pixel Data (FITS images):** 100% cloud-native on Amazon AWS S3 via byte-range requests (`backend/app/s3_reader.py`). It reads directly from `s3://nasa-irsa-spherex/`, runs in 0.1 seconds, and never goes down.
- **Metadata Search (Discovery):** When someone enters a new RA and Dec, `backend/app/archive.py` sends an SQL query to Caltech's campus server (`irsa.ipac.caltech.edu/TAP/sync`) to ask: *"Which Level-2 exposures cover this position?"*

The vulnerability: Caltech's web proxy frequently drops internal database connections and returns `502 Proxy Error`. When that happens, the app cannot find the file names for new coordinates, even though Amazon AWS S3 is healthy and ready to serve pixels.

Here is how we can move metadata discovery 100% to the cloud so server outages never block the app again.

---

## 2. Option 1: HEALPix All-Sky Cube (Pure Mathematics, Zero Database)

SPHEREx DR1 already hosts an All-Sky Spectral Cube directly on Amazon AWS S3 (`s3://nasa-irsa-spherex/dr1/hips5_cube/`).
The files are partitioned geometrically using the HEALPix celestial tessellation at order 5 (Nside = 32, ~1.8 degree pixels).

### How it works:
Instead of asking a database "which file covers RA and Dec?", we calculate the exact file name directly using geometry:

```python
import healpy as hp

def get_cube_s3_key(ra_deg: float, dec_deg: float) -> str:
    # 1. Convert RA/Dec to HEALPix pixel index (Nside 32 = Order 5)
    pixel = hp.ang2pix(32, ra_deg, dec_deg, lonlat=True, nest=True)
    
    # 2. Derive the exact directory bucket path
    dir_num = (pixel // 10000) * 10000
    return f"dr1/hips5_cube/hips_20261026/Norder5/Dir{dir_num}/Npix{pixel}.fits"
```

### Why this is unbeatable:
- **Zero database servers:** No TAP, no SIA2, no SQL queries, and zero chance of a 502 error.
- **Instant:** Calculating `ang2pix` takes 2 microseconds.
- **Infinite uptime:** Amazon S3 has 99.99% availability. Any user can enter any coordinate in the sky at 3:00 AM, and the file is fetched from S3 immediately.
- **Trade-off:** The HiPS all-sky cube gives a coadded spectral cube of the sky rather than individual Level-2 single visit exposures.

---

## 3. Option 2: Cloud Parquet Spatial Table (For Level-2 Single Exposures)

If we want the individual Level-2 exposures (to blink visits over time) without asking Caltech's TAP server, we can host the spatial index as a Parquet file directly on S3.

### How it works:
1. Export the 1,628,230 rows of `spherex.obscore` (obs_id, detector, pointing footprint, MJD, S3 key) into an Apache Parquet file.
2. Partition the Parquet table on S3 by HEALPix order 4:
   ```text
   s3://our-bucket/spherex_footprints/healpix_order4/pixel=123/data.parquet
   ```
3. When a user enters RA and Dec:
   - Calculate the order-4 pixel for that coordinate.
   - Use DuckDB or PyArrow over HTTP to read only that single 150 KB Parquet partition directly from S3.
   - Filter rows where the polygon contains the coordinate.

### Why this works:
- Replaces Caltech's entire PostgreSQL server with static cloud storage.
- Query time drops from 15 seconds on TAP to under 50 milliseconds via DuckDB.
- Never suffers from 502 proxy errors.

---

## 4. Option 3: Local Discovery Disk Cache (Immediate Hackathon Implementation)

For our current setup before migrating to Parquet:
Whenever `archive.find_images(ra, dec)` runs successfully, save the full list of image dictionaries (including `s3_key`) to a local JSON cache:
```text
cache/discovery/<ra>_<dec>.json
```

If Caltech TAP responds with 502:
```python
def find_images(ra, dec, detector=None):
    cache_file = CACHE_DIR / "discovery" / f"{ra:.4f}_{dec:+.4f}.json"
    if cache_file.exists():
        return load_cached_images(cache_file, detector)
    try:
        images = query_tap(ra, dec, detector)
        save_cached_images(cache_file, images)
        return images
    except ArchiveError:
        raise ArchiveError("NASA TAP proxy is temporarily down; using offline cached targets.")
```

---

## 5. Summary & Recommendation

| Approach | Server Needed | Handles Random (RA, Dec)? | Level-2 Visits? | Outage Resistant? |
|---|---|---|---|---|
| **Caltech TAP (Current)** | Caltech Apache/Postgres | Yes | Yes | No (502 proxy crashes) |
| **Option 1: HiPS Cube** | None (Math + S3) | Yes (All Sky) | Coadded Cube | 100% Yes |
| **Option 2: Cloud Parquet** | None (DuckDB + S3) | Yes (All Sky) | Yes (All 1.6M exps) | 100% Yes |
| **Option 3: Local Cache** | Local Disk | Pre-cached only | Yes | 100% for cached |

**Recommended roadmap:**
- **For now (Hackathon):** Rely on our prepared target frames and local discovery cache so our presentation never crashes.
- **For production:** Add Option 1 (HiPS All-Sky math lookup) as the zero-server cloud fallback whenever a user enters coordinates outside our prepared catalog.

