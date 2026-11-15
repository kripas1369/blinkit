"""When IRSA TAP is down, Gaia falls back to ESA's archive (astroquery)."""
import pytest
from astropy.table import Table

from backend.app import archive, gaia


def test_gaia_stars_uses_esa_when_irsa_is_down(monkeypatch, tmp_path):
    monkeypatch.setattr(gaia, "CACHE_DIR", tmp_path)

    def irsa_down(adql):
        raise archive.ArchiveError("IRSA TAP did not answer after 1 tries: 502")

    monkeypatch.setattr(archive, "run_query", irsa_down)

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
    monkeypatch.setattr(gaia, "_gaia_from_esa", lambda ra, dec, radius: fake)

    stars = gaia.gaia_stars(269.45, 4.77, 0.05)
    assert len(stars) == 1
    assert stars[0]["source_id"] == "1"
    assert stars[0]["pmra"] == -800.0


def test_gaia_stars_raises_when_both_fail(monkeypatch, tmp_path):
    monkeypatch.setattr(gaia, "CACHE_DIR", tmp_path)

    def irsa_down(adql):
        raise archive.ArchiveError("IRSA down")

    def esa_down(*_a, **_k):
        raise RuntimeError("ESA down")

    monkeypatch.setattr(archive, "run_query", irsa_down)
    monkeypatch.setattr(gaia, "_gaia_from_esa", esa_down)
    with pytest.raises(archive.ArchiveError, match="ESA"):
        gaia.gaia_stars(1.0, 2.0, 0.01)
