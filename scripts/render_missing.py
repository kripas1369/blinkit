"""Render every official target/detector folder that is still missing, then run B4 writers.

Uses SIA-first image search (archive.find_images). Gaia/CatWISE need IRSA TAP; if TAP is
down those steps are recorded as warnings and can be re-run later with --sidecars-only.

    python -m scripts.render_missing              # render + sidecars for all missing
    python -m scripts.render_missing --list       # print missing only
    python -m scripts.render_missing --sidecars-only
    python -m scripts.render_missing --only wise0855:6,eps_ind_b:5
"""
from __future__ import annotations

import argparse
import sys
import time
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FRAMES = REPO / "frontend" / "frames"
OFFICIAL = ("barnard", "eps_ind_b", "wise0855", "rw_aur", "r_dra")
DETECTORS = range(1, 7)


def missing_folders() -> list[tuple[str, int]]:
    out = []
    for t in OFFICIAL:
        for d in DETECTORS:
            if not (FRAMES / t / f"d{d}" / "manifest.json").is_file():
                out.append((t, d))
    return out


def parse_only(text: str | None) -> list[tuple[str, int]] | None:
    if not text:
        return None
    pairs = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        key, det = part.split(":")
        pairs.append((key.strip(), int(det)))
    return pairs


def run_sidecars(folder: Path) -> list[str]:
    """B4 products + Gaia/CatWISE. Failures become warnings, not hard stops."""
    from backend.app.diff import write_diff, write_minus_median
    from backend.app.gaia import write_gaia
    from backend.app.proof import write_proof
    from backend.app.stack import write_stack
    from backend.app.wise import write_wise

    warnings: list[str] = []
    for name, fn in [
        ("Gaia DR3 markers", write_gaia),
        ("CatWISE2020 markers", write_wise),
        ("difference maps", write_diff),
        ("minus-median frames", write_minus_median),
        ("visit stack", write_stack),
        ("proof panel", write_proof),
    ]:
        try:
            fn(folder)
            print(f"    ok  {name}")
        except Exception as exc:
            msg = f"{name} failed: {exc}"
            warnings.append(msg)
            print(f"    WARN {msg}")
    warn_path = folder / "pipeline_warnings.txt"
    if warnings:
        warn_path.write_text("\n".join(warnings) + "\n")
    elif warn_path.exists():
        warn_path.unlink()
    return warnings


def render_one(target: str, detector: int) -> None:
    from backend.app import archive
    from backend.app.render import make_frames, write_index

    # Do not sit behind an old TAP cooldown from a previous failed job.
    archive._tap_down.update(until=0.0, reason="")

    folder = FRAMES / target / f"d{detector}"
    print(f"\n=== {target} D{detector} ===")
    t0 = time.monotonic()
    make_frames(target, detector, out_root=FRAMES)
    print(f"  render finished in {time.monotonic() - t0:.0f}s -> {folder}")
    # make_frames already tries gaia/wise; re-run full sidecar set for B4 products.
    run_sidecars(folder)
    write_index(FRAMES)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="List missing folders and exit")
    parser.add_argument("--sidecars-only", action="store_true",
                        help="Only (re)run Gaia/WISE/diff/stack/proof on existing folders")
    parser.add_argument("--only", type=str, default=None,
                        help="Comma list like wise0855:6,eps_ind_b:5")
    parser.add_argument("--all-existing", action="store_true",
                        help="With --sidecars-only, touch every rendered folder (not just incomplete)")
    args = parser.parse_args()

    only = parse_only(args.only)
    missing = only if only is not None else missing_folders()

    if args.list:
        for t, d in missing:
            print(f"{t}/d{d}")
        print(f"{len(missing)} missing of 30")
        return 0

    if args.sidecars_only:
        from backend.app import archive
        from backend.app.render import write_index

        # Skip waiting on a dead IRSA TAP: Gaia will use ESA; CatWISE writes empty if needed.
        archive._tap_down.update(until=time.monotonic() + 3600, reason="sidecar pass prefers ESA Gaia")

        folders = []
        if args.all_existing or only is not None:
            keys = only if only is not None else [
                (t, d) for t in OFFICIAL for d in DETECTORS
                if (FRAMES / t / f"d{d}" / "manifest.json").is_file()
            ]
            folders = [FRAMES / t / f"d{d}" for t, d in keys]
        else:
            # Folders that exist but lack gaia.json or proof.json.
            for t in OFFICIAL:
                for d in DETECTORS:
                    p = FRAMES / t / f"d{d}"
                    if (p / "manifest.json").is_file() and (
                        not (p / "gaia.json").is_file() or not (p / "proof.json").is_file()
                    ):
                        folders.append(p)
        for folder in folders:
            print(f"\n=== sidecars {folder.relative_to(FRAMES)} ===")
            run_sidecars(folder)
        write_index(FRAMES)
        return 0

    if not missing:
        print("Nothing missing — all 30 folders have a manifest.")
        return 0

    print(f"Will render {len(missing)} folder(s):")
    for t, d in missing:
        print(f"  {t}/d{d}")

    failed: list[str] = []
    for t, d in missing:
        try:
            render_one(t, d)
        except Exception as exc:
            failed.append(f"{t}/d{d}: {exc}")
            print(f"  FAIL {t}/d{d}: {exc}")
            traceback.print_exc()

    print("\n=== summary ===")
    still = missing_folders()
    print(f"still missing: {len(still)} / 30")
    for t, d in still:
        print(f"  {t}/d{d}")
    if failed:
        print("failures:")
        for line in failed:
            print(f"  {line}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())