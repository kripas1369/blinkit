import pytest

from backend.app import archive


@pytest.fixture(autouse=True)
def _private_image_lists(tmp_path, monkeypatch):
    """Saved image lists go to a temp folder, so tests never read each other's (or real) searches."""
    monkeypatch.setattr(archive, "IMAGE_LIST_DIR", tmp_path / "image_lists")
    monkeypatch.setattr(archive, "_tap_down", {"until": 0.0, "reason": ""})
