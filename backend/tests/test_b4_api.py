"""/api/diff, /api/proof and /api/stack without the network."""
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.app import main

client = TestClient(main.app)


@pytest.fixture
def prepared(monkeypatch, tmp_path):
    folder = tmp_path / "frames" / "barnard" / "d2"
    folder.mkdir(parents=True)
    (folder / "manifest.json").write_text(json.dumps({
        "format": "spherex-blink-frames/1", "target": "barnard", "label": "Barnard's Star",
        "ra": 269.45, "dec": 4.77, "fov_arcmin": 3, "pixel_arcsec": 6.15, "size_px": 29,
        "band": 2, "mode": "coadd", "scale": {"vmin": 0, "vmax": 1},
        "frames": [
            {"epoch_id": 0, "png": "epoch0.png", "fits": "epoch0.fits", "mjd": 60913.5,
             "date_iso": "2025-08-26 11:57 UTC", "band": 2, "n_images": 8},
            {"epoch_id": 1, "png": "epoch1.png", "fits": "epoch1.fits", "mjd": 61100.0,
             "date_iso": "2026-03-16 10:39 UTC", "band": 2, "n_images": 8},
            {"epoch_id": 2, "png": "epoch2.png", "fits": "epoch2.fits", "mjd": 61273.7,
             "date_iso": "2026-08-21 17:06 UTC", "band": 2, "n_images": 8},
        ],
    }))
    monkeypatch.setattr(main, "PREPARED_DIR", tmp_path / "frames")
    monkeypatch.setattr(main, "JOBS_DIR", tmp_path / "jobs")
    monkeypatch.setattr(main, "_jobs", {})
    monkeypatch.setattr(main, "_pool", SimpleNamespace(submit=lambda f, *a: None))
    return folder


def test_diff_and_proof_endpoints(prepared):
    (prepared / "diff.json").write_text(json.dumps({
        "format": "spherex-blink-diff/1",
        "pairs": [{"a": 0, "b": 2, "png": "diff_0_2.png"}],
        "minus_median": {"median_png": "median.png", "frames": [{"epoch_id": 0, "png": "minus_median0.png"}]},
        "default_pair": {"a": 0, "b": 2, "reason": "closest wavelengths"},
    }))
    (prepared / "proof.json").write_text(json.dumps({
        "format": "spherex-blink-proof/1", "target": "barnard", "band": 2,
        "motion": {"status": "agrees", "measured_size_px": 1.61, "expected_size_px": 1.67},
    }))
    d = client.get("/api/diff", params={"target": "barnard", "band": 2}).json()
    assert d["pairs"][0]["png_url"] == "/frames/barnard/d2/diff_0_2.png"
    assert d["minus_median"]["frames"][0]["png_url"].endswith("minus_median0.png")
    assert d["minus_median"]["median_png_url"].endswith("median.png")
    p = client.get("/api/proof", params={"target": "barnard", "band": 2}).json()
    assert p["motion"]["status"] == "agrees"
    assert client.get("/api/diff", params={"target": "barnard", "band": 3}).status_code == 202


def test_stack_returns_saved_file_and_remakes_for_a_subset(prepared, monkeypatch):
    saved = {
        "format": "spherex-blink-stack/1", "target": "barnard", "band": 2,
        "visits": [0, 1, 2], "n_visits": 3, "n_images": 24,
        "noise_per_pixel": 0.0062, "single_visit_noise": 0.0108,
        "noise_ratio_vs_single_visit": 1.73, "unit": "MJy/sr",
    }
    (prepared / "stack.json").write_text(json.dumps(saved))
    r = client.get("/api/stack", params={"target": "barnard", "band": 2})
    assert r.status_code == 200
    body = r.json()
    assert body["png_url"] == "/frames/barnard/d2/stack.png" and body["n_visits"] == 3

    calls = []

    def fake_write(folder, visits=None):
        calls.append(visits)
        return {**saved, "visits": visits, "n_visits": len(visits), "png": "stack_0_2.png", "fits": "stack_0_2.fits"}

    monkeypatch.setattr(main, "write_stack", fake_write)
    r = client.get("/api/stack", params={"target": "barnard", "band": 2, "visits": "0,2"})
    assert r.status_code == 200 and calls == [[0, 2]] and r.json()["visits"] == [0, 2]
    assert r.json()["png_url"].endswith("stack_0_2.png")
    # The default all-visits stack.json is still the full one.
    assert json.loads((prepared / "stack.json").read_text())["visits"] == [0, 1, 2]
    assert client.get("/api/stack", params={"target": "barnard", "band": 2, "visits": "x"}).status_code == 400


def test_after_render_steps_include_b4(prepared):
    names = [stage for stage, _ in main.AFTER_RENDER_STEPS]
    for needed in ("Gaia DR3 markers", "CatWISE2020 markers", "difference maps",
                   "minus-median frames", "visit stack", "proof panel"):
        assert needed in names
