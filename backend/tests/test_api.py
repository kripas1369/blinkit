"""The API base without the network: SIMBAD is replaced by fakes."""
from fastapi.testclient import TestClient

from backend.app import main
from backend.app.resolve import ResolverUnavailable

client = TestClient(main.app)

BARNARD = {"name": "Barnard's Star", "simbad_id": "BD+04 3561a", "ra": 269.452, "dec": 4.6934,
           "pmra": -801.551, "pmdec": 10362.394, "epoch": 2000.0, "server": "simbad.cds.unistra.fr"}


def test_health():
    assert client.get("/api/health").json() == {"ok": True}


def test_resolve_moves_the_star_to_2026(monkeypatch):
    monkeypatch.setattr(main, "resolve_name", lambda name: dict(BARNARD))
    answer = client.get("/api/resolve", params={"name": "Barnard's Star"}).json()
    assert answer["source"] == "SIMBAD (simbad.cds.unistra.fr)"
    assert answer["position_now"]["year"] == 2026.0
    assert abs(answer["position_now"]["moved_arcsec"] - 270.2) < 0.5


def test_resolve_without_proper_motion_is_not_moved(monkeypatch):
    monkeypatch.setattr(main, "resolve_name", lambda name: {**BARNARD, "pmra": None, "pmdec": None})
    assert client.get("/api/resolve", params={"name": "x"}).json()["position_now"] is None


def test_resolve_errors(monkeypatch):
    def unknown(name):
        raise LookupError(f"{name!r} was not found in SIMBAD")

    def down(name):
        raise ResolverUnavailable("No SIMBAD server answered")

    monkeypatch.setattr(main, "resolve_name", unknown)
    r = client.get("/api/resolve", params={"name": "notastar"})
    assert r.status_code == 404 and "not found" in r.json()["error"]
    monkeypatch.setattr(main, "resolve_name", down)
    assert client.get("/api/resolve", params={"name": "x"}).status_code == 503
    assert client.get("/api/resolve").status_code == 400


def test_unknown_endpoint_is_json_404():
    r = client.get("/api/nothing")
    assert r.status_code == 404 and "No such API endpoint" in r.json()["error"]
