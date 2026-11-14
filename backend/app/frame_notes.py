"""Observer caveats and scientific notes for the flipbook, per (target, detector).

In the WiseView flipbook model, human blink observers need immediate context on
instrument artifacts (saturation holes, LVF filter gradients, blended companions)
so they don't mistake instrumental effects for moving or variable objects.
"""
import json
import sys
from pathlib import Path

NOTES: dict[tuple[str, int], list[str]] = {
    ("barnard", 1): ["Not yet re-measured on DR1/QR3 data."],
    ("barnard", 2): ["Not yet re-measured on DR1/QR3 data."],
    ("barnard", 3): ["Not yet re-measured on DR1/QR3 data."],
    ("barnard", 4): ["Not yet re-measured on DR1/QR3 data."],
    ("barnard", 5): ["Not yet re-measured on DR1/QR3 data."],
    ("barnard", 6): ["Not yet re-measured on DR1/QR3 data."],
    ("eps_ind_b", 2): ["Not yet re-measured on DR1/QR3 data."],
    ("rw_aur", 2): ["Not yet re-measured on DR1/QR3 data."],
    ("r_dra", 2): ["Not yet re-measured on DR1/QR3 data."],
    ("wise0855", 2): ["Not yet re-measured on DR1/QR3 data."],
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

