"""Unit tests for CatWISE2020 overlay generator (backend/app/wise.py)."""
from backend.app.motion import separation_arcsec
from backend.app.wise import CATWISE_EPOCH, markers, search_radius_deg, source_at
import pytest


def test_source_at_stationary():
    """A source without proper motion remains at its catalog position."""
    src = {"source_name": "J000000.00+000000.0", "ra": 10.0, "dec": 20.0, "pmra": None, "pmdec": None}
    ra, dec = source_at(src, 2026.0)
    assert ra == 10.0
    assert dec == 20.0


def test_source_at_moving():
    """A moving source has its position shifted by its proper motion from CatWISE epoch."""
    # Move 1.0 arcsec/yr North, 0 arcsec/yr East
    src = {"source_name": "J123456.78+123456.7", "ra": 180.0, "dec": 0.0, "pmra": 0.0, "pmdec": 1.0}
    # After 10 years, it should have moved ~10 arcseconds north
    target_year = CATWISE_EPOCH + 10.0
    ra, dec = source_at(src, target_year)
    assert ra == pytest.approx(180.0, abs=1e-6)
    sep = separation_arcsec(180.0, 0.0, ra, dec)
    assert sep == pytest.approx(10.0, abs=0.01)


def test_search_radius():
    """Search radius accommodates both FOV diagonal and maximum star motion."""
    r = search_radius_deg(fov_arcmin=3.0, years_from_epoch=11.0)
    assert 0.05 < r < 0.10


def test_markers_projection():
    """Verify that markers projects sources to PNG pixel coordinates."""
    ra_center, dec_center = 269.45, 4.75
    frames = [
        {"epoch_id": 0, "mjd": 60913.5},
        {"epoch_id": 1, "mjd": 61273.7},
    ]
    sources = [
        {
            "source_name": "J175748.00+044500.0",
            "ra": ra_center,
            "dec": dec_center,
            "pmra": 0.0,
            "pmdec": 0.1,  # 0.1 arcsec/yr North
            "w1_mag": 12.5,
            "w2_mag": 12.0,
            "w1_snr": 50.0,
            "w2_snr": 40.0,
        }
    ]
    res = markers(ra_center, dec_center, fov_arcmin=3.0, frames=frames, sources=sources, target_year=2026.0)
    assert len(res["sources"]) == 1
    src_marker = res["sources"][0]
    assert src_marker["has_motion"] is True
    assert src_marker["target"] is True
    assert len(src_marker["xy"]) == 2

    (x0, y0), (x1, y1) = src_marker["xy"][0], src_marker["xy"][1]
    assert x0 == pytest.approx(x1, abs=0.1)
    assert y1 < y0  # Moved north -> smaller PNG y

