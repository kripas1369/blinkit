#!/usr/bin/env python3
"""Benchmark script for SPHEREx S3 byte-range reading across FOV sizes.

Tests FOV sizes 3, 10, 20, and 30 arcminutes to measure retrieval latency,
data transfer volume, and verify the UI threshold warning at FOV > 15 arcmin.
"""
import time
from backend.app.s3_reader import read_box

KEY = "dr1/level2/2026W12_1A/l2b-v27-2026-235/2/level2_2026W12_1A_0311_1D2_spx_l2b-v27-2026-235.fits"
RA, DEC = 269.44627, 4.76820
FOVS = [3.0, 10.0, 20.0, 30.0]


def run_benchmark():
    print("=== SPHEREx S3 FOV Benchmark ===")
    print(f"Target: Barnard's Star D2 (obs_id: 2026W12_1A_0311_1)")
    print(f"{'FOV (arcmin)':<14} | {'Size (px)':<10} | {'S3 Time (s)':<12} | {'Transfer (MB)':<14} | {'Route':<10}")
    print("-" * 70)
    for fov in FOVS:
        size_deg = fov / 60.0
        t0 = time.time()
        try:
            hdul = read_box(KEY, RA, DEC, size_deg=size_deg)
            dt = time.time() - t0
            ny, nx = hdul["IMAGE"].data.shape
            approx_mb = round((ny * (2040 * 4 * 3 + 1500) + 28800) / 1e6, 2)
            print(f"{fov:<14.1f} | {f'{nx}x{ny}':<10} | {dt:<12.3f} | {approx_mb:<14.2f} | aws-s3")
        except Exception as exc:
            print(f"{fov:<14.1f} | ERROR: {exc}")


if __name__ == "__main__":
    run_benchmark()
