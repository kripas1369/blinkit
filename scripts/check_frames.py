"""Audit rendered flipbook folders in frontend/frames against FRAMES_FORMAT.md.

For every frontend/frames/<target>/d<det>/ folder:
- checks presence of all required files: manifest.json, gaia.json, wise.json, diff.json,
  stack.json, stack.fits, stack.png, proof.json, median.fits, median.png,
  epoch<i>.png, epoch<i>.fits, minus_median<i>.png, and diff_<a>_<b>.png.
- checks that pixel_source == "aws-s3" for every frame.
- prints a summary table: target, detector, visits, n_images, pixel_source, release,
  align_offset_px range, and pct_flagged range.
- exits with code 1 if any file is missing or pixel_source != "aws-s3".

Run from repository root:
    python -m scripts.check_frames
"""
import argparse
import json
import sys
from pathlib import Path


def check_folder(folder: Path) -> dict:
    errors = []
    manifest_path = folder / "manifest.json"
    if not manifest_path.exists():
        return {"folder": folder, "errors": ["missing manifest.json"]}

    manifest = json.loads(manifest_path.read_text())
    frames = manifest.get("frames", [])
    n_visits = len(frames)
    if n_visits == 0:
        return {"folder": folder, "errors": ["manifest has 0 visits"]}

    # Required JSON and Stack files
    required_files = [
        "manifest.json",
        "gaia.json",
        "wise.json",
        "diff.json",
        "stack.json",
        "stack.fits",
        "stack.png",
        "proof.json",
    ]
    if n_visits >= 2:
        required_files.extend(["median.fits", "median.png"])

    for req in required_files:
        if not (folder / req).exists():
            errors.append(f"missing {req}")

    # Per-visit files
    for f in frames:
        eid = f.get("epoch_id")
        if not (folder / f"epoch{eid}.png").exists():
            errors.append(f"missing epoch{eid}.png")
        if not (folder / f"epoch{eid}.fits").exists():
            errors.append(f"missing epoch{eid}.fits")
        if n_visits >= 2 and not (folder / f"minus_median{eid}.png").exists():
            errors.append(f"missing minus_median{eid}.png")

    # Difference pairs
    diff_path = folder / "diff.json"
    if diff_path.exists():
        diff_data = json.loads(diff_path.read_text())
        for pair in diff_data.get("pairs", []):
            png = pair.get("png")
            if png and not (folder / png).exists():
                errors.append(f"missing {png}")

    # Provenance and values check
    pix_sources = {f.get("pixel_source") for f in frames}
    if pix_sources != {"aws-s3"}:
        errors.append(f"pixel_source is {pix_sources}, expected {{'aws-s3'}}")

    total_images = sum(f.get("n_images", 0) for f in frames)
    releases = sorted({f.get("release", "unknown") for f in frames})
    align_offsets = [f.get("align_offset_px") for f in frames if f.get("align_offset_px") is not None]
    pct_flagged = [f.get("pct_flagged", 0.0) for f in frames]

    align_str = (
        f"{min(align_offsets):.2f}-{max(align_offsets):.2f}"
        if align_offsets
        else "none"
    )
    flagged_str = (
        f"{min(pct_flagged):.1f}%-{max(pct_flagged):.1f}%"
        if pct_flagged
        else "0.0%"
    )

    return {
        "folder": folder,
        "target": manifest.get("target"),
        "band": manifest.get("band"),
        "visits": n_visits,
        "n_images": total_images,
        "pixel_source": ",".join(sorted(str(s) for s in pix_sources)),
        "release": "+".join(releases),
        "align_offset_px": align_str,
        "pct_flagged": flagged_str,
        "errors": errors,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--frames-dir", type=Path, default=Path("frontend/frames"))
    args = parser.parse_args()

    folders = sorted(args.frames_dir.glob("*/d*"))
    if not folders:
        print(f"No target folders found under {args.frames_dir}")
        sys.exit(1)

    print(f"Auditing {len(folders)} rendered target/detector folders under {args.frames_dir}:\n")
    print(
        f"{'Target':<12} {'Det':<4} {'Visits':<8} {'Images':<8} {'Pixel Source':<14} {'Release':<12} {'Align Offset (px)':<20} {'Pct Flagged':<14} {'Status':<10}"
    )
    print("-" * 106)

    all_passed = True
    for folder in folders:
        res = check_folder(folder)
        target = res.get("target", folder.parent.name)
        band = f"D{res.get('band', folder.name.replace('d', ''))}"
        status = "PASS" if not res["errors"] else f"FAIL ({len(res['errors'])} errors)"
        if res["errors"]:
            all_passed = False

        print(
            f"{target:<12} {band:<4} {res['visits']:<8} {res['n_images']:<8} {res['pixel_source']:<14} "
            f"{res['release']:<12} {res['align_offset_px']:<20} {res['pct_flagged']:<14} {status:<10}"
        )
        for err in res["errors"]:
            print(f"    ERROR: {err}")

    print("-" * 106)
    if all_passed:
        print(f"ALL CHECKS PASSED: {len(folders)} folders verified compliant with FRAMES_FORMAT.md (all pixel_source = aws-s3).")
        sys.exit(0)
    else:
        print("AUDIT FAILED: one or more folders have errors or non-S3 pixel sources.")
        sys.exit(1)


if __name__ == "__main__":
    main()

