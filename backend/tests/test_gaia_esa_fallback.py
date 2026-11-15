"""Gaia overlays prefer CDS VizieR; ESA and IRSA are backups when VizieR fails."""
import pytest
from astropy.table import Table

from backend.app import archive, gaia


def test_gaia_stars_uses_vizier_first(monkeypatch, tmp_path):
    monkeypatch.setattr(gaia, "CACHE_DIR", tmp_path)

    def no_irsa(_adql):
        raise AssertionError("IRSA should not be called when VizieR works")

    monkeypatch.setattr(archive, "run_query", no_irsa)
    monkeypatch.setattr(
        gaia,
        "_gaia_from_vizier",
        lambda ra, dec, radius: [{
            "source_id": "1",
            "ra": 269.45,
            "dec": 4.77,
            "pmra": -800.0,
            "pmdec": 10300.0,
            "parallax": 500.0,
            "g_mag": 9.5,
        }],
    )

    stars = gaia.gaia_stars(269.45, 4.77, 0.05)
    assert len(stars) == 1
    assert stars[0]["source_id"] == "1"
    assert stars[0]["pmra"] == -800.0


def test_gaia_stars_uses_esa_when_vizier_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(gaia, "CACHE_DIR", tmp_path)

    def vizier_down(*_a, **_k):
        raise RuntimeError("VizieR down")

    fake = Table({
        "source_id": [1],
        "ra": [269.45],
        "dec": [4.77],
        "pmra": [-800.0],
        "pmdec": [10300.0],
        "parallax": [500.0],
        "phot_g_mean_mag": [9.5],
        "ref_epoch": [2016.0],
    })
    monkeypatch.setattr(gaia, "_gaia_from_vizier", vizier_down)
    monkeypatch.setattr(gaia, "_gaia_from_esa_timed", lambda *a, **k: fake)

    def no_irsa(_adql):
        raise AssertionError("IRSA should not be called when ESA works")

    monkeypatch.setattr(archive, "run_query", no_irsa)

    stars = gaia.gaia_stars(269.45, 4.77, 0.05)
    assert len(stars) == 1
    assert stars[0]["pmra"] == -800.0


def test_gaia_stars_raises_when_all_fail(monkeypatch, tmp_path):
    monkeypatch.setattr(gaia, "CACHE_DIR", tmp_path)

    monkeypatch.setattr(gaia, "_gaia_from_vizier", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("VizieR down")))
    monkeypatch.setattr(gaia, "_gaia_from_esa_timed", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("ESA down")))
    monkeypatch.setattr(archive, "run_query", lambda *_: (_ for _ in ()).throw(archive.ArchiveError("IRSA down")))

    with pytest.raises(archive.ArchiveError, match="Gaia DR3 unavailable"):
        gaia.gaia_stars(1.0, 2.0, 0.01)
