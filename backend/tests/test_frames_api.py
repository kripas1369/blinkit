"""/api/frames without the network: a prepared folder in tmp_path, and a fake render module for jobs."""
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.app import main

client = TestClient(main.app)

BARNARD_RA, BARNARD_DEC = 269.4486, 4.7398


def manifest(target="barnard", band=2, ra=BARNARD_RA, dec=BARNARD_DEC):
    return {
        "format": "spherex-blink-frames/1", "target": target, "label": "Barnard's Star", "ra": ra, "dec": dec,
        "fov_arcmin": 3, "pixel_arcsec": 6.15, "size_px": 29, "band": band, "mode": "coadd",
        "scale": {"vmin": 0.0, "vmax": 1.0},
        "frames": [{"png": "epoch0.png", "flags_png": "epoch0_flags.png", "mjd": 60913.5,
                    "date_iso": "2025-08-26 11:57 UTC", "band": band, "pct_flagged": 2.6, "n_images": 8},
                   {"png": "epoch1.png", "mjd": 61273.7, "date_iso": "2026-08-21 16:48 UTC", "band": band,
                    "pct_flagged": 1.9, "n_images": 8}],
    }


class NoImages(LookupError):
    pass


def fake_render(calls, error=None):
    def render_frames(*args):
        calls.append(args)
        if error:
            raise error

    return SimpleNamespace(NoImages=NoImages, render_frames=render_frames,
                           make_frames=lambda *a: calls.append(a), write_index=lambda *a: None)


@pytest.fixture
def prepared(monkeypatch, tmp_path):
    folder = tmp_path / "frames" / "barnard" / "d2"
    folder.mkdir(parents=True)
    (folder / "manifest.json").write_text(json.dumps(manifest()))
    monkeypatch.setattr(main, "PREPARED_DIR", tmp_path / "frames")
    monkeypatch.setattr(main, "JOBS_DIR", tmp_path / "jobs")
    monkeypatch.setattr(main, "_jobs", {})
    return folder


def run_now(monkeypatch):
    monkeypatch.setattr(main, "_pool", SimpleNamespace(submit=lambda f, *a: f(*a)))


def test_fov_30_is_allowed(prepared, monkeypatch):
    monkeypatch.setattr(main, "_render", lambda: fake_render([]))
    monkeypatch.setattr(main, "_pool", SimpleNamespace(submit=lambda f, *a: None))
    r = client.get("/api/frames", params={"ra": 10, "dec": 0, "band": 2, "fov_arcmin": 30})
    assert r.status_code == 202


def test_gaia_and_wise_sidecars(prepared):
    sidecar = {"format": "spherex-blink-gaia/1", "stars": [], "frames": []}
    (prepared / "gaia.json").write_text(json.dumps(sidecar))
    (prepared / "wise.json").write_text(json.dumps({**sidecar, "format": "spherex-blink-wise/1"}))
    assert client.get("/api/gaia", params={"target": "barnard", "band": 2}).json()["format"].startswith("spherex-blink-gaia")
    assert client.get("/api/wise", params={"target": "barnard", "band": 2}).json()["format"].startswith("spherex-blink-wise")
    assert client.get("/api/gaia", params={"target": "barnard", "band": 3}).status_code == 404


def test_prepared_target_has_image_urls(prepared):
    r = client.get("/api/frames", params={"target": "barnard", "band": 2})
    assert r.status_code == 200
    m = r.json()
    assert m["source"] == "prepared" and m["base_url"] == "/frames/barnard/d2/"
    assert m["frames"][0]["png_url"] == "/frames/barnard/d2/epoch0.png"
    assert m["frames"][0]["flags_png_url"] == "/frames/barnard/d2/epoch0_flags.png"
    assert "flags_png_url" not in m["frames"][1]


def test_position_within_5_arcsec_of_a_target_uses_its_prepared_frames(prepared):
    r = client.get("/api/frames", params={"ra": BARNARD_RA + 1 / 3600, "dec": BARNARD_DEC, "band": 2})
    assert r.status_code == 200 and r.json()["target"] == "barnard"


@pytest.mark.parametrize("params,status", [
    ({"target": "pluto", "band": 2}, 404),
    ({"target": "barnard", "band": 5}, 404),
    ({"target": "barnard", "band": 9}, 400),
    ({"band": 2}, 400),
    ({"ra": 400, "dec": 0, "band": 2}, 400),
    ({"ra": 10, "dec": 0, "band": 2, "fov_arcmin": 31}, 400),
])
def test_errors_are_plain_messages(prepared, params, status):
    r = client.get("/api/frames", params=params)
    assert r.status_code == status
    assert set(r.json()) == {"error"} and r.json()["error"]


def test_new_position_without_render_module_says_so(prepared, monkeypatch):
    def missing():
        raise main.ApiError(503, "Making frames for a new position needs backend/app/render.py")

    monkeypatch.setattr(main, "_render", missing)
    r = client.get("/api/frames", params={"ra": 10, "dec": 20, "band": 2})
    assert r.status_code == 503 and "render.py" in r.json()["error"]
    assert main._jobs == {}, "no job is recorded, so the next request tries again"


def test_working_job_answers_202(prepared, monkeypatch):
    monkeypatch.setattr(main, "_render", lambda: fake_render([]))
    monkeypatch.setattr(main, "_pool", SimpleNamespace(submit=lambda f, *a: None))
    r = client.get("/api/frames", params={"ra": 10, "dec": -20, "band": 2})
    assert r.status_code == 202 and r.json()["status"] == "working"


def test_job_with_no_images_is_404_and_runs_once(prepared, monkeypatch):
    calls = []
    monkeypatch.setattr(main, "_render", lambda: fake_render(calls, NoImages("No SPHEREx images here in D2")))
    run_now(monkeypatch)
    for _ in range(2):
        r = client.get("/api/frames", params={"ra": 10, "dec": 20, "band": 2})
        assert r.status_code == 404 and "No SPHEREx images" in r.json()["error"]
    assert len(calls) == 1
    assert calls[0][2] == "pos_10.0000_p20.0000_fov3" and calls[0][5] == 2


def test_failed_job_is_502(prepared, monkeypatch):
    monkeypatch.setattr(main, "_render", lambda: fake_render([], RuntimeError("IRSA busy")))
    run_now(monkeypatch)
    r = client.get("/api/frames", params={"ra": 10, "dec": 20, "band": 2})
    assert r.status_code == 502 and "IRSA busy" in r.json()["error"]


def test_finished_job_serves_its_folder(prepared, monkeypatch):
    key = main._job_key(10, -20, 5)
    folder = main.JOBS_DIR / key / "d3"
    folder.mkdir(parents=True)
    (folder / "manifest.json").write_text(json.dumps(manifest(target=key, band=3, ra=10, dec=-20)))
    r = client.get("/api/frames", params={"ra": 10, "dec": -20, "band": 3, "fov_arcmin": 5})
    assert r.status_code == 200
    assert r.json()["source"] == "job" and r.json()["base_url"] == f"/jobframes/{key}/d3/"


def test_missing_detector_of_a_target_with_two_prepared_starts_a_download(prepared, monkeypatch):
    other = prepared.parent / "d3"
    other.mkdir()
    (other / "manifest.json").write_text(json.dumps(manifest(band=3)))
    monkeypatch.setattr(main, "_render", lambda: fake_render([]))
    monkeypatch.setattr(main, "_pool", SimpleNamespace(submit=lambda f, *a: None))
    r = client.get("/api/frames", params={"target": "barnard", "band": 5})
    assert r.status_code == 202 and "preparing" in r.json()["message"].lower()
