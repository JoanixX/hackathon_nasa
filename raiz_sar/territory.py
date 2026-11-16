"""Small, source-aware DEM point inspection and bounded offline tile preparation contracts."""
from __future__ import annotations

import math

import numpy as np

from .terrain import NATIVE_DEG, SOURCE, TERRAIN_MAX_ZOOM, TerrainUnavailable, _in_regions, read_dem, tile_bounds


def nearest_sample(dem, transform, lon: float, lat: float) -> float | None:
    """Return the containing cell, never coerce missing or out-of-grid values to sea level."""
    col, row = ~transform * (lon, lat)
    if not (math.isfinite(row) and math.isfinite(col) and 0 <= row < dem.shape[0] and 0 <= col < dem.shape[1]):
        return None
    value = float(dem[math.floor(row), math.floor(col)])
    return round(value, 2) if math.isfinite(value) else None


def inspect_point(lon: float, lat: float) -> dict:
    if not (math.isfinite(lon) and math.isfinite(lat) and -180 <= lon <= 180 and -85 < lat < 85):
        raise ValueError("Invalid WGS84 position.")
    if not _in_regions((lon - 1e-7, lat - 1e-7, lon + 1e-7, lat + 1e-7)):
        raise ValueError("The point lies outside the study region.")
    dem, transform, covered = read_dem(lon - 2 * NATIVE_DEG, lat - 2 * NATIVE_DEG,
                                       lon + 2 * NATIVE_DEG, lat + 2 * NATIVE_DEG)
    value = nearest_sample(dem, transform, lon, lat) if covered else None
    return {"lon": lon, "lat": lat, "elevation_m": value, "evidence_class": "derived" if value is not None else "unknown",
            "source": SOURCE, "horizontal_crs": "EPSG:4326", "vertical_crs": "EPSG:3855",
            "grid_arcseconds": 1, "acquisition_date": None,
            "note": "Nearest resampled DSM cell, not surveyed ground. The source includes vegetation and structures; per-cell acquisition date is unknown."}


def tile_plan(bbox, min_zoom: int, max_zoom: int, max_tiles: int = 64) -> list[tuple[int, int, int]]:
    """Validate the complete bounded work plan before doing any I/O. No silent truncation."""
    from .sources import lonlat_to_tile

    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4 or not all(type(v) in (int, float) and math.isfinite(v) for v in bbox):
        raise ValueError("Expected four finite WGS84 bounds.")
    w, s, e, n = bbox
    if not (-180 <= w < e <= 180 and -85 < s < n < 85):
        raise ValueError("Invalid WGS84 bounds.")
    if not (type(min_zoom) is int and type(max_zoom) is int and 7 <= min_zoom <= max_zoom <= TERRAIN_MAX_ZOOM):
        raise ValueError("Supported terrain zoom range is 7 through 12.")
    if type(max_tiles) is not int or not 1 <= max_tiles <= 256:
        raise ValueError("Tile budget must be 1 through 256.")
    tiles = []
    for z in range(min_zoom, max_zoom + 1):
        x0, y0 = lonlat_to_tile(w, n, z)
        x1, y1 = lonlat_to_tile(math.nextafter(e, w), math.nextafter(s, n), z)
        if (x1 - x0 + 1) * (y1 - y0 + 1) + len(tiles) > max_tiles:
            raise ValueError("Tile budget exceeded; reduce bounds or maximum zoom.")
        tiles.extend((z, x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1))
    return tiles
