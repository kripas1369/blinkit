"""When IRSA TAP is down: the image search falls back to IRSA SIA, then to the last saved list."""
import io
import json
import time
from types import SimpleNamespace

import pytest
import requests
from astropy.io import votable
from astropy.table import Table

from backend.app import archive
from backend.app.archive import ArchiveError, SpherexImage, attach_paths, find_images

RA, DEC = 269.4462685, 4.7682045


def sia_votable(collection: str, detectors: list[int]) -> bytes:
    rows = []
    for i, det in enumerate(detectors):
        key = f"{collection[8:]}/level2/2026W33_2A/l2b-v27/{det}/level2_2026W33_2A_000{i}_1D{det}_spx.fits"
        rows.append({
            "obs_id": f"2026W33_2A_000{i}_1",
            "obs_publisher_did": f"ivo://irsa.ipac/spherex/{collection}?{key}",
            "obs_collection": collection,
            "energy_bandpassname": f"SPHEREx-D{det}",
            "t_min": 61268.63 + i, "t_max": 61268.631 + i,
            "em_min": 1.1e-6, "em_max": 1.6e-6,
            "obs_release_date": "2026-11-12 00:00:00",
            "access_url": f"https://irsa.ipac.caltech.edu/ibe/data/spherex/{key}",
            "cloud_access": json.dumps({"aws": {"bucket_name": "nasa-irsa-spherex", "key": key}}),
        })
    buf = io.BytesIO()
    votable.from_table(Table(rows=rows)).to_xml(buf)
    return buf.getvalue()


def tap_down(query):
    raise ArchiveError("IRSA TAP did not answer after 4 tries: 502")


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr(archive.time, "sleep", lambda s: None)


def fake_sia(answers: dict, calls: list | None = None):
    """answers: collection -> list of (status, body) returned in turn (the last one repeats)."""
    def get(url, params=None, timeout=None):
        col = params["COLLECTION"]
        if calls is not None:
            calls.append(col)
        queue = answers[col]
        status, body = queue.pop(0) if len(queue) > 1 else queue[0]
        return SimpleNamespace(status_code=status, content=body)
    return get


def test_tap_down_uses_sia_and_keeps_paths_and_s3_keys(monkeypatch, no_sleep):
    monkeypatch.setattr(archive, "_run", tap_down)
    monkeypatch.setattr(archive.requests, "get", fake_sia({
        "spherex_dr1": [(502, b"Proxy Error"), (200, sia_votable("spherex_dr1", [2, 3]))],
        "spherex_qr3": [(200, sia_votable("spherex_qr3", [2]))],
    }))
    images = find_images(RA, DEC, collections=("spherex_dr1", "spherex_qr3"), detector=2)
    assert [im.collection for im in images] == ["spherex_dr1", "spherex_qr3"]
    assert all(im.detector == 2 for im in images)
    assert images[0].s3_key == "dr1/level2/2026W33_2A/l2b-v27/2/level2_2026W33_2A_0000_1D2_spx.fits"
    assert images[0].path == "spherex/dr1/level2/2026W33_2A/l2b-v27/2/level2_2026W33_2A_0000_1D2_spx.fits"
    saved = json.loads(next(archive.IMAGE_LIST_DIR.glob("*.json")).read_text())
    assert saved["source"] == "sia" and saved["complete"] is True


def tap_answer(collection: str, detector: int):
    table = Table({
        "obs_id": ["2025W33_1A_0001_1"], "obs_publisher_did": [f"ivo://irsa.ipac/spherex/{collection}?tap.fits"],
        "obs_collection": [collection], "energy_bandpassname": [f"SPHEREx-D{detector}"],
        "t_min": [60900.0], "t_max": [60900.001], "em_min": [1.1e-6], "em_max": [1.6e-6],
        "obs_release_date": ["2026-04-21 00:00:00"],
        "cloud_access": ['{"aws": {"bucket_name": "nasa-irsa-spherex", "key": "dr1/tap.fits"}}'],
    })
    return lambda query: table


def test_tap_is_the_main_source_and_sia_is_not_asked(monkeypatch):
    monkeypatch.setattr(archive, "_run", tap_answer("spherex_dr1", 2))

    def sia_called(*a, **k):
        raise AssertionError("SIA is only the fallback")
    monkeypatch.setattr(archive.requests, "get", sia_called)
    images = find_images(RA, DEC, collections=("spherex_dr1",))
    assert [im.s3_key for im in images] == ["dr1/tap.fits"]
    saved = json.loads(next(archive.IMAGE_LIST_DIR.glob("*.json")).read_text())
    assert saved["source"] == "tap" and saved["complete"] is True


def test_tap_is_asked_first_even_with_a_saved_list(monkeypatch, no_sleep):
    monkeypatch.setattr(archive, "_run", tap_down)
    monkeypatch.setattr(archive.requests, "get", fake_sia({"spherex_dr1": [(200, sia_votable("spherex_dr1", [2]))]}))
    find_images(RA, DEC, collections=("spherex_dr1",))

    monkeypatch.setattr(archive, "_run", tap_answer("spherex_dr1", 2))
    images = find_images(RA, DEC, collections=("spherex_dr1",))
    assert [im.s3_key for im in images] == ["dr1/tap.fits"]


def test_sia_answer_missing_a_release_is_used_and_marked_incomplete(monkeypatch, no_sleep):
    monkeypatch.setattr(archive, "_run", tap_down)
    calls = []
    monkeypatch.setattr(archive.requests, "get", fake_sia({
        "spherex_dr1": [(502, b"Proxy Error")],
        "spherex_qr3": [(200, sia_votable("spherex_qr3", [2]))],
    }, calls))
    images = find_images(RA, DEC, collections=("spherex_dr1", "spherex_qr3"))
    assert [im.collection for im in images] == ["spherex_qr3"]
    assert calls.count("spherex_dr1") == archive.SIA_TRIES
    saved = json.loads(next(archive.IMAGE_LIST_DIR.glob("*.json")).read_text())
    assert saved["complete"] is False


def test_everything_down_uses_old_saved_list(monkeypatch, no_sleep):
    monkeypatch.setattr(archive, "_run", tap_down)
    monkeypatch.setattr(archive.requests, "get", fake_sia({"spherex_dr1": [(200, sia_votable("spherex_dr1", [4]))]}))
    first = find_images(RA, DEC, collections=("spherex_dr1",))
    path = next(archive.IMAGE_LIST_DIR.glob("*.json"))
    saved = json.loads(path.read_text())
    saved["saved_at"] = time.time() - 30 * 24 * 3600
    path.write_text(json.dumps(saved))

    monkeypatch.setattr(archive.requests, "get", fake_sia({"spherex_dr1": [(502, b"Proxy Error")]}))
    assert find_images(RA, DEC, collections=("spherex_dr1",)) == first


def test_everything_down_and_nothing_saved_raises(monkeypatch, no_sleep):
    monkeypatch.setattr(archive, "_run", tap_down)
    monkeypatch.setattr(archive.requests, "get", fake_sia({"spherex_dr1": [(502, b"Proxy Error")]}))
    with pytest.raises(ArchiveError, match="TAP.*SIA"):
        find_images(RA, DEC, collections=("spherex_dr1",))


def test_tap_failing_every_try_is_not_retried_during_cooldown(monkeypatch, no_sleep):
    asked = []

    class DownTap:
        def run_sync(self, adql, maxrec):
            asked.append(adql)
            raise requests.ConnectionError("502 Proxy Error")

    monkeypatch.setattr(archive, "_tap", lambda: DownTap())
    monkeypatch.setattr(archive, "_tap_down", {"until": 0.0, "reason": ""})
    with pytest.raises(ArchiveError, match="after"):
        archive._run("SELECT 1")
    assert len(asked) == archive.RETRIES
    with pytest.raises(ArchiveError, match="down"):
        archive._run("SELECT 2")
    assert len(asked) == archive.RETRIES

    archive._tap_down["until"] = 0.0
    with pytest.raises(ArchiveError, match="after"):
        archive._run("SELECT 3")
    assert len(asked) == 2 * archive.RETRIES


@pytest.mark.parametrize("error", [
    requests.ReadTimeout("Read timed out. (read timeout=90)"),
    archive.pyvo.dal.DALServiceError("Read timed out", cause=requests.ReadTimeout("Read timed out")),
])
def test_tap_timeout_is_not_retried(monkeypatch, no_sleep, error):
    asked = []

    class HangingTap:
        def run_sync(self, adql, maxrec):
            asked.append(adql)
            raise error

    monkeypatch.setattr(archive, "_tap", lambda: HangingTap())
    with pytest.raises(ArchiveError, match="after 1 tries"):
        archive._run("SELECT 1")
    assert len(asked) == 1
    with pytest.raises(ArchiveError, match="down"):
        archive._run("SELECT 2")
    assert len(asked) == 1


def image(did: str, s3_key: str | None, path: str | None = None) -> SpherexImage:
    return SpherexImage(obs_id=did, did=did, detector=2, mjd_start=1.0, mjd_end=1.0, wl_min_um=1.1,
                        wl_max_um=1.6, release_date="", collection="spherex_dr1", path=path, s3_key=s3_key)


def test_attach_paths_skips_images_that_have_a_path(monkeypatch):
    def must_not_run(query):
        raise AssertionError("no TAP query needed")
    monkeypatch.setattr(archive, "_run", must_not_run)
    images = [image("a", "dr1/a.fits", path="spherex/dr1/a.fits")]
    assert attach_paths(images) == images


def test_attach_paths_with_tap_down_reads_from_s3(monkeypatch):
    monkeypatch.setattr(archive, "_run", tap_down)
    monkeypatch.setattr(archive, "SPHEREX_PIXELS", "s3")
    images = [image("a", "dr1/a.fits")]
    assert attach_paths(images) == images
    assert images[0].path is None


def test_attach_paths_with_tap_down_and_no_s3_key_raises(monkeypatch):
    monkeypatch.setattr(archive, "_run", tap_down)
    monkeypatch.setattr(archive, "SPHEREX_PIXELS", "s3")
    with pytest.raises(ArchiveError):
        attach_paths([image("a", None)])
