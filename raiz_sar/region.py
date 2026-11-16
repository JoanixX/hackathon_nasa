"""Study-region boundaries (exact polygons) used to limit zones, tiles and map navigation.

Piura: OpenStreetMap administrative boundary (relation 1986151, ODbL), stored with provenance in
raiz_sar/boundaries/piura_department.source.json and fetched by tools/fetch_piura_boundary.py.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

BOUNDARY_DIR = Path(__file__).resolve().parent / "boundaries"


@lru_cache(maxsize=8)
def boundary(name: str):
    """(shapely geometry, prepared geometry, provenance dict) for a stored boundary."""
    from shapely.geometry import shape
    from shapely.prepared import prep

    fc = json.loads((BOUNDARY_DIR / f"{name}.geojson").read_text(encoding="utf-8"))
    g = shape(fc["features"][0]["geometry"]).buffer(0)
    meta = json.loads((BOUNDARY_DIR / f"{name}.source.json").read_text(encoding="utf-8"))
    return g, prep(g), meta


def geojson(name: str) -> dict[str, Any]:
    g, _p, meta = boundary(name)
    from shapely.geometry import mapping

    return {"type": "Feature", "geometry": mapping(g), "properties": {k: meta[k] for k in ("name", "source", "osm_id", "licence", "retrieved_utc", "area_km2", "sha256")}}
