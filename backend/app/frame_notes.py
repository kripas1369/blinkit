"""Observer caveats and scientific notes for the flipbook, per (target, detector).

Human blink observers need context on saturation, LVF wavelength, and alignment so
instrumental effects are not mistaken for moving or variable objects. Notes are
measured from the Nov 2026 DR1/QR3 renders where folders exist.
"""
import json
import sys
from pathlib import Path

NOTES: dict[tuple[str, int], list[str]] = {
    ("barnard", 1): [
        "D1 (~0.94 µm): saturated point source; Gaia motion agrees (1.57 px vs 1.66 px). 2.5–3.9% flagged."
    ],
    ("barnard", 2): [
        "D2 (~1.43 µm): best motion proof (1.61 px vs Gaia 1.67 px). Three visits, DR1+QR3, 0.31–0.36 px alignment."
    ],
    ("barnard", 3): [
        "D3 (~1.85 µm): motion agrees; slightly more LVF slope across the 3 arcmin field than D2."
    ],
    ("barnard", 4): [
        "D4 (~3.15 µm): motion agrees; highest flagged fraction of Barnard bands (~5.8%) on visit 0."
    ],
    ("barnard", 5): [
        "D5 (~4.2 µm): motion agrees; low flagged fraction; still saturated at centre."
    ],
    ("barnard", 6): [
        "D6 (~4.6 µm): motion not measurable in proof.json (centroid/saturated-core failed); use D2 for the walk demo."
    ],
    ("eps_ind_b", 1): [
        "D1: brown dwarf faint at 0.97 µm; motion proof disagrees — use D2+ for astrometry."
    ],
    ("eps_ind_b", 2): [
        "D2 (~1.42 µm): five visits, motion agrees (0.98 px vs 1.09 px); best stack S/N (2.18× vs one visit)."
    ],
    ("eps_ind_b", 3): [
        "D3 (~1.95 µm): four visits; motion agrees; minus-median visit 4 needed sky offset fix (QR3 ZODI step)."
    ],
    ("eps_ind_b", 4): [
        "D4 (~3.28 µm): three visits; motion agrees (0.65 px vs 0.75 px)."
    ],
    ("eps_ind_b", 5): ["Not rendered yet (IRSA TAP down 15 Nov 2026)."],
    ("eps_ind_b", 6): ["Not rendered yet (IRSA TAP down 15 Nov 2026)."],
    ("wise0855", 2): ["Not rendered yet; WISE 0855 needs D5–D6 when IRSA is back."],
    ("rw_aur", 2): ["Not rendered yet; check variable brightness at matched wavelengths between visits."],
    ("r_dra", 2): ["Not rendered yet; crowded field — read wl_target_um before calling a brightness change."],
}


def update_manifest_notes(frames_dir: Path) -> int:
    """Inject updated notes into existing manifest.json files without re-rendering."""
    updated = 0
    for manifest_path in frames_dir.glob("*/*/manifest.json"):
        target = manifest_path.parent.parent.name
        detector_str = manifest_path.parent.name
        if not detector_str.startswith("d"):
            continue
        try:
            detector = int(detector_str[1:])
        except ValueError:
            continue
        notes = NOTES.get((target, detector))
        if notes is None:
            continue
        manifest = json.loads(manifest_path.read_text())
        manifest["notes"] = notes
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        updated += 1
    return updated


if __name__ == "__main__":
    target_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("frontend/frames")
    count = update_manifest_notes(target_dir)
    print(f"Updated notes in {count} manifest(s)")