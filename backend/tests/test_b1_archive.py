import importlib
import os
import pytest
from astropy.table import Table

from backend.app import config, archive
from backend.app.archive import SpherexImage, discover_collections, find_images


def test_config_spherex_collections_override(monkeypatch):
    monkeypatch.setenv("SPHEREX_COLLECTIONS", "spherex_dr1, spherex_test_collection")
    importlib.reload(config)
    assert config.COLLECTIONS == ("spherex_dr1", "spherex_test_collection")
    monkeypatch.delenv("SPHEREX_COLLECTIONS", raising=False)
    importlib.reload(config)
    assert config.COLLECTIONS == ("spherex_qr3", "spherex_qr3_deep", "spherex_dr1", "spherex_dr1_deep")


def test_discover_collections_filters_cal_and_non_spherex(monkeypatch):
    fake_table = Table({
        "obs_collection": [
            "spherex_dr1",
            "spherex_dr1_cal",
            "spherex_qr3",
            "spherex_qr3_deep",
            "wise_allwise",
            "spherex_qr3_cal",
            "twomass",
        ]
    })
    monkeypatch.setattr(archive, "_run", lambda query: fake_table)
    archive._discover_collections_cached.cache_clear()
    cols = discover_collections()
    assert cols == ["spherex_dr1", "spherex_qr3", "spherex_qr3_deep"]
    assert "spherex_dr1_cal" not in cols
    assert "spherex_qr3_cal" not in cols
    assert "wise_allwise" not in cols


def test_find_images_returns_s3_key_from_cloud_access(monkeypatch):
    fake_cloud_access = '{"aws": {"bucket_name": "nasa-irsa-spherex", "key": "dr1/level2/test_epoch.fits"}}'
    fake_table = Table({
        "obs_id": ["2025W33_1A_0001_1"],
        "obs_publisher_did": ["ivo://irsa.ipac/spherex?dr1/level2/test_epoch.fits"],
        "obs_collection": ["spherex_dr1"],
        "energy_bandpassname": ["SPHEREx-D2"],
        "t_min": [60900.0],
        "t_max": [60900.001],
        "em_min": [1.1e-6],
        "em_max": [1.62e-6],
        "obs_release_date": ["2026-04-21 00:00:00"],
        "cloud_access": [fake_cloud_access],
    })
    monkeypatch.setattr(archive, "_run", lambda query: fake_table)
    images = find_images(269.452, 4.693, collections=("spherex_dr1",))
    assert len(images) == 1
    im = images[0]
    assert im.s3_key == "dr1/level2/test_epoch.fits"
    assert im.detector == 2
    assert im.collection == "spherex_dr1"


def test_find_images_falls_back_to_sia2_when_cloud_access_empty(monkeypatch):
    fake_table = Table({
        "obs_id": ["2025W33_1A_0001_1"],
        "obs_publisher_did": ["ivo://irsa.ipac/spherex?dr1/level2/test_epoch.fits"],
        "obs_collection": ["spherex_dr1"],
        "energy_bandpassname": ["SPHEREx-D6"],
        "t_min": [60900.0],
        "t_max": [60900.001],
        "em_min": [4.42e-6],
        "em_max": [5.00e-6],
        "obs_release_date": ["2026-04-21 00:00:00"],
        "cloud_access": [""],
    })
    monkeypatch.setattr(archive, "_run", lambda query: fake_table)
    monkeypatch.setattr(
        archive,
        "_fetch_s3_keys_sia",
        lambda ra, dec, collections: {"2025W33_1A_0001_1_6": "dr1/level2/sia_resolved_D6.fits"},
    )
    images = find_images(269.452, 4.693, collections=("spherex_dr1",))
    assert len(images) == 1
    im = images[0]
    assert im.s3_key == "dr1/level2/sia_resolved_D6.fits"

