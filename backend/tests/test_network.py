"""Live tests against SIMBAD. Run with:  RUN_NETWORK=1 python -m pytest backend/tests/test_network.py"""
import os

import pytest

from backend.app.resolve import resolve_name

pytestmark = pytest.mark.skipif(not os.environ.get("RUN_NETWORK"), reason="set RUN_NETWORK=1")


def test_resolve_barnard():
    star = resolve_name("Barnard's Star")
    assert star["ra"] == pytest.approx(269.452, abs=0.01)
    assert star["pmdec"] > 10000


def test_unknown_name_raises():
    with pytest.raises(LookupError):
        resolve_name("notastar123xyz")
