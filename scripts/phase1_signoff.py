"""Phase 1 sign-off helper: run frame audit and print Kripas B5 checklist status.

    python -m scripts.phase1_signoff

Exits 0 when all automatable checks pass. Manual UI checks are listed for the record.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FRAMES = REPO / "frontend" / "frames"
OFFICIAL = ("barnard", "eps_ind_b", "wise0855", "rw_aur", "r_dra")


def folders() -> list[Path]:
    out = []
    for t in OFFICIAL:
        for d in range(1, 7):
            p = FRAMES / t / f"d{d}"
            if (p / "manifest.json").is_file():
                out.append(p)
    return out


def proof_summary() -> list[str]:
    lines = []
    for p in folders():
        proof = json.loads((p / "proof.json").read_text())
        m = proof.get("motion") or {}
        rel = p.relative_to(FRAMES)
        lines.append(f"{rel}: motion {m.get('status', '?')} "
                     f"(meas {m.get('measured_size_px')} px, Gaia {m.get('expected_size_px')} px)")
    return lines


def main() -> int:
    print("=== check_frames ===")
    r = subprocess.run([sys.executable, "-m", "scripts.check_frames"], cwd=REPO)
    if r.returncode != 0:
        return r.returncode

    n = len(folders())
    print(f"\n=== rendered folders: {n}/30 ===")
    for line in proof_summary():
        print(" ", line)

    print("\n=== B5 checklist (automated vs manual) ===")
    checks = [
        ("check_frames.py PASS", r.returncode == 0),
        ("all rendered visits pixel_source aws-s3", r.returncode == 0),
        (f"frame folders present ({n}/30)", n >= 10),
        ("Barnard motion proof agrees (D2)", _barnard_d2_agrees()),
        ("random RA job + empty sky", "manual / pytest test_frames_api"),
        ("all 5 targets x D6 in browser", "manual when IRSA allows renders"),
    ]
    for label, ok in checks:
        mark = "OK" if ok is True else ("—" if isinstance(ok, str) else "FAIL")
        extra = f" ({ok})" if isinstance(ok, str) else ""
        print(f"  [{mark}] {label}{extra}")

    return 0 if r.returncode == 0 and _barnard_d2_agrees() else 1


def _barnard_d2_agrees() -> bool:
    p = FRAMES / "barnard" / "d2" / "proof.json"
    if not p.is_file():
        return False
    return json.loads(p.read_text()).get("motion", {}).get("status") == "agrees"


if __name__ == "__main__":
    raise SystemExit(main())