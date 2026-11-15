"""When IRSA CatWISE is down, WISE overlays fall back to AllWISE on CDS VizieR."""
import pytest

from backend.app import archive, wise


def test_wise_sources_uses_vizier_when_irsa_is_down(monkeypatch, tmp_path):
    monkeypatch.setattr(wise, "CACHE_DIR", tmp_path)

    def irsa_down(*_a, **_k):
        raise archive.ArchiveError("IRSA TAP is down (not retried for a few minutes): 502")

    monkeypatch.setattr(wise, "_catwise_from_irsa", irsa_down)
    monkeypatch.setattr(
        wise,
        "_allwise_from_vizier",
        lambda ra, dec, radius: [{
            "source_name": "J175746.02+044444.1",
            "ra": 269.44,
            "dec": 4.75,
            "pmra": 0.084,
            "pmdec": -0.071,
            "w1_mag": 14.8,
            "w2_mag": 14.9,
            "w1_snr": None,
            "w2_snr": None,
            "catalog": "allwise",
            "epoch": wise.ALLWISE_EPOCH,
        }],
    )

    sources = wise.wise_sources(269.45, 4.77, 0.05)
    assert len(sources) == 1
    assert sources[0]["catalog"] == "allwise"
    assert sources[0]["pmra"] == pytest.approx(0.084)


def test_wise_sources_raises_when_both_fail(monkeypatch, tmp_path):
    monkeypatch.setattr(wise, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(wise, "_catwise_from_irsa", lambda *a, **k: (_ for _ in ()).throw(archive.ArchiveError("IRSA")))
    monkeypatch.setattr(wise, "_allwise_from_vizier", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("VizieR")))
    with pytest.raises(archive.ArchiveError, match="WISE catalogue unavailable"):
        wise.wise_sources(1.0, 2.0, 0.01)
