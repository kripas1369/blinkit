"""Observer caveats for the flipbook, per (target, detector).

Notes are measured from the Nov 2026 DR1/QR3 renders (30 folders). Catalogue overlays
need IRSA TAP (or ESA Gaia); when TAP was down some folders got empty gaia/wise.json —
those notes say so honestly.
"""
import json
import sys
from pathlib import Path

NOTES: dict[tuple[str, int], list[str]] = {
    ("barnard", 1): ["D1 (~0.94 µm): saturated; Gaia motion agrees (1.57 vs 1.66 px)."],
    ("barnard", 2): ["D2 (~1.43 µm): best motion proof (1.61 vs Gaia 1.67 px). Three visits, DR1+QR3."],
    ("barnard", 3): ["D3 (~1.85 µm): motion agrees (1.60 vs 1.68 px)."],
    ("barnard", 4): ["D4 (~3.15 µm): motion agrees; highest Barnard flagged share (~5.8%)."],
    ("barnard", 5): ["D5 (~4.2 µm): motion agrees (1.51 vs 1.67 px); still saturated at centre."],
    ("barnard", 6): ["D6 (~4.6 µm): proof not measurable; use D2 for the walk demo."],
    ("eps_ind_b", 1): ["D1: too faint at 0.97 µm; motion disagrees — prefer D2+."],
    ("eps_ind_b", 2): ["D2: five visits; motion agrees (0.98 vs 1.09 px); best stack S/N."],
    ("eps_ind_b", 3): ["D3: four visits; motion agrees (1.02 vs 1.06 px)."],
    ("eps_ind_b", 4): ["D4: motion agrees (0.65 vs 0.75 px) at ~3.3 µm."],
    ("eps_ind_b", 5): ["D5 (~4.1 µm): five visits rendered; Gaia overlay empty (TAP/ESA down at render)."],
    ("eps_ind_b", 6): ["D6 (~4.7 µm): four visits rendered; Gaia overlay empty (TAP/ESA down at render)."],
    ("wise0855", 1): ["D1 (~1.0 µm): three visits; Y-dwarf expected invisible here."],
    ("wise0855", 2): ["D2: four visits; still short of 4–5 µm — treat as non-detection band."],
    ("wise0855", 3): ["D3: three visits; plan: still faint until D5–D6."],
    ("wise0855", 4): ["D4: three visits; approaching mid-IR."],
    ("wise0855", 5): ["D5 (~4 µm): four visits, 30 exposures; best short of D6 for the cold dwarf."],
    ("wise0855", 6): ["D6 (~4.5–5 µm): three visits; preferred band for WISE 0855 (blink here)."],
    ("rw_aur", 1): ["D1: three visits (24 exposures); check brightness only at matched wl_target_um."],
    ("rw_aur", 2): ["D2 (~1.3–1.5 µm): three visits; default for variability blink."],
    ("rw_aur", 3): ["D3: three visits; LVF wavelengths differ between visits — read the label."],
    ("rw_aur", 4): ["D4: three visits; may saturate — check pct_flagged before a light curve."],
    ("rw_aur", 5): ["D5 (~4.0–4.3 µm): three visits rendered for multi-band compare."],
    ("rw_aur", 6): ["D6 (~4.6–4.7 µm): three visits rendered."],
    ("r_dra", 1): ["D1: five visits in a crowded deep field; 3–8% flagged."],
    ("r_dra", 2): ["D2: three visits; Mira — wavelength range first, then brightness."],
    ("r_dra", 3): ["D3: four visits; crowded field, higher flag rates."],
    ("r_dra", 4): ["D4: five visits; 13–19% flagged — expect defect stripes."],
    ("r_dra", 5): ["D5: three visits; 8–13% flagged."],
    ("r_dra", 6): ["D6: four visits; visit 2 had hundreds of exposures available (capped at 8)."],
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
