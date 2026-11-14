#!/usr/bin/env python3
"""Time the SPHEREx S3 byte-range reader for one exposure at several field-of-view sizes.

Bytes and requests are counted from the HTTP range reads themselves. Timings depend on the network
between this machine and AWS us-east-1, so record where the run was made.

Run from the repository root:  python -m scripts.bench_s3
"""
import time

from backend.app import s3_reader

KEY = "dr1/level2/2026W12_1A/l2b-v27-2026-235/2/level2_2026W12_1A_0311_1D2_spx_l2b-v27-2026-235.fits"
RA, DEC = 269.44627, 4.76820
FOVS = [3.0, 10.0, 20.0, 30.0]

_counts = {"bytes": 0, "requests": 0}
_get_range = s3_reader.get_range


def _counting_get_range(*args, **kwargs):
    data = _get_range(*args, **kwargs)
    _counts["bytes"] += len(data)
    _counts["requests"] += 1
    return data


def run_benchmark():
    s3_reader.get_range = _counting_get_range
    print("=== SPHEREx S3 byte-range reader, one exposure per FOV ===")
    print("Target: Barnard's Star D2, obs_id 2026W12_1A_0311_1 (full file 62.7 MB)")
    print(f"Run: {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}")
    print(f"{'FOV (arcmin)':<13} | {'Size (px)':<10} | {'Time (s)':<9} | {'Downloaded (MB)':<16} | Requests")
    print("-" * 66)
    for fov in FOVS:
        _counts.update(bytes=0, requests=0)
        t0 = time.time()
        try:
            hdul = s3_reader.read_box(KEY, RA, DEC, size_deg=fov / 60.0)
        except Exception as exc:
            print(f"{fov:<13.1f} | ERROR: {exc}")
            continue
        dt = time.time() - t0
        ny, nx = hdul["IMAGE"].data.shape
        print(f"{fov:<13.1f} | {f'{nx}x{ny}':<10} | {dt:<9.2f} | {_counts['bytes'] / 1e6:<16.2f} | {_counts['requests']}")


if __name__ == "__main__":
    run_benchmark()
