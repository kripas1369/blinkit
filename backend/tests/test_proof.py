"""Tests for astrometric motion proof against Gaia DR3 ground truth (backend/app/proof.py)."""
from pathlib import Path
import pytest

from backend.app.proof import MAX_MOTION_ERROR_PX, build_proof

FRAMES_DIR = Path("frontend/frames")


def test_barnard_and_eps_ind_b_agree_with_gaia():
    """Verify that measured motion matches Gaia DR3 within 0.5 px tolerance."""
    barnard_d2 = FRAMES_DIR / "barnard" / "d2"
    if barnard_d2.exists():
        barnard = build_proof(barnard_d2)["motion"]
        assert barnard["status"] == "agrees"
        # Barnard D2 core is saturated, measured using saturated-core centre
        assert barnard["method"] == "saturated-core centre"
        assert barnard["difference_px"] <= MAX_MOTION_ERROR_PX

    eps_d2 = FRAMES_DIR / "eps_ind_b" / "d2"
    if eps_d2.exists():
        eps = build_proof(eps_d2)["motion"]
        assert eps["status"] == "agrees"
        assert eps["method"] == "centroid"
        assert eps["direction_difference_deg"] <= 30.0
        assert eps["difference_px"] <= MAX_MOTION_ERROR_PX

