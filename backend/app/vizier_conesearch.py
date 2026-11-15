"""CDS VizieR cone search via public mirrors — overlays when NASA IRSA TAP is down.

Harvard's Vizier mirror answers quickly for Gaia DR3 and AllWISE. The main CDS host
often 404s the conesearch path from this network, so we try several mirrors.
"""
from __future__ import annotations

from io import BytesIO

import numpy as np
import requests
from astropy.io.votable import parse
from astropy.table import Table

VIZIER_MIRRORS = (
    "https://vizier.cfa.harvard.edu",
    "https://vizier.cds.unistra.fr",
)

TIMEOUT_SECONDS = 25


def cone_search(catalog: str, ra: float, dec: float, radius_deg: float) -> Table:
    """VOTable rows from a VizieR conesearch, or raise RuntimeError if every mirror fails."""
    last = "no mirror tried"
    for base in VIZIER_MIRRORS:
        url = (
            f"{base}/viz-bin/conesearch/{catalog}"
            f"?RA={ra:.8f}&DEC={dec:.8f}&SR={radius_deg:.6f}"
        )
        try:
            resp = requests.get(url, timeout=TIMEOUT_SECONDS)
        except requests.RequestException as exc:
            last = f"{base}: {exc}"
            continue
        if resp.status_code != 200 or not resp.content:
            last = f"{base}: HTTP {resp.status_code}"
            continue
        try:
            return parse(BytesIO(resp.content)).get_first_table().to_table()
        except Exception as exc:
            last = f"{base}: {exc}"
            continue
    raise RuntimeError(f"VizieR conesearch failed for {catalog}: {last}")


def cell(row, *names):
    """First present column as float (or str for identifiers), else None."""
    for name in names:
        try:
            v = row[name]
        except Exception:
            continue
        if v is None:
            continue
        if np.ma.is_masked(v):
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            text = str(v).strip()
            return text or None
    return None
