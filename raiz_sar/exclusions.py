"""Human-infrastructure exclusions for planting (NV-04): buildings, roads, paths and pedestrian areas.

One exclusion geometry per zone is computed when the zone is confirmed and stored in the versioned dataset, so the
plan, drone deposition nodes, 3D scene, AR and exports all use the same geometry (validated on the server).

Sources: OpenStreetMap via OpenFreeMap vector tiles (OpenMapTiles schema). Footprints and pedestrian areas are
polygons. Roads and paths are centre lines without width in this schema, so each class gets a *declared clearance
from the centre line* (listed below and returned with every result); it is not a measured width, and placements
near it are flagged for field review. OSM coverage is incomplete (e.g. many Piura buildings are not mapped):
unmapped ground is never reported as cleared.
"""

from __future__ import annotations

import os
from typing import Any

# Declared clearance from the mapped centre line, metres (not measured widths; see module docstring).
ROAD_CLEARANCE_M = {"motorway": 12.0, "trunk": 12.0, "primary": 10.0, "secondary": 8.0, "tertiary": 7.0, "minor": 5.0,
                    "service": 4.0, "track": 3.0, "path": 1.5, "rail": 5.0, "transit": 5.0, "busway": 6.0, "raceway": 5.0}
DEFAULT_ROAD_CLEARANCE_M = 5.0


def source_enabled() -> bool:
    return os.environ.get("RAIZ_INFRA_SOURCE", "osm").lower() != "none"


def zone_infrastructure(geom_lonlat) -> dict[str, Any] | None:
    """Exclusion polygon (lon/lat GeoJSON) and counts for a zone; None when the source is disabled (tests)."""
    if not source_enabled():
        return None
    from shapely.geometry import mapping
    from shapely.ops import unary_union

    from . import osm_features
    from .geo import to_metric, to_wgs84, utm_epsg_for

    c = geom_lonlat.centroid
    crs = utm_epsg_for(c.x, c.y)
    bbox = geom_lonlat.buffer(0.002).bounds
    try:
        f = osm_features.features(bbox, {"transportation", "park"})
        from . import overture

        f["building"] = overture.buildings(bbox)  # OSM + Google Open Buildings + Microsoft ML footprints
    except Exception as exc:  # noqa: BLE001
        return {"status": "unavailable", "reason": f"Infrastructure mapping could not be read: {type(exc).__name__}",
                "geometry": None, "counts": {}, "field_review": True}
    parts, counts = [], {"buildings": 0, "road_segments": 0, "paths": 0, "pedestrian_areas": 0}
    by_source: dict[str, int] = {}
    for b in f.get("building", []):
        parts.append(to_metric(b["geometry"], crs))
        counts["buildings"] += 1
        src = str(b["props"].get("source") or "unknown")
        by_source[src] = by_source.get(src, 0) + 1
    counts["buildings_by_source"] = by_source
    for t in f.get("transportation", []):
        g = to_metric(t["geometry"], crs)
        cls = t["props"].get("class")
        if g.geom_type in ("Polygon", "MultiPolygon"):  # pedestrian squares/areas mapped as surfaces
            parts.append(g)
            counts["pedestrian_areas"] += 1
            continue
        parts.append(g.buffer(ROAD_CLEARANCE_M.get(cls, DEFAULT_ROAD_CLEARANCE_M)))
        counts["paths" if cls == "path" else "road_segments"] += 1
    excl = unary_union(parts) if parts else None
    zone_m = to_metric(geom_lonlat, crs)
    inside = excl.intersection(zone_m) if excl is not None else None
    parks = [p for p in f.get("park", [])]
    return {"status": "ok", "geometry": mapping(to_wgs84(excl, crs)) if excl is not None and not excl.is_empty else None,
            "excluded_share_of_zone": round(inside.area / zone_m.area, 4) if inside is not None and zone_m.area else 0.0,
            "counts": counts, "parks_mapped": len(parks), "metric_crs": crs,
            "declared_road_clearance_m": ROAD_CLEARANCE_M,
            "source": "Buildings: Overture Maps (OSM, Google Open Buildings, Microsoft ML footprints); roads/paths: OpenStreetMap via OpenFreeMap (ODbL)",
            "field_review": True,
            "note": "Buildings are Overture footprints (mapped or ML-detected) and pedestrian areas are mapped surfaces; road/path "
                    "clearances are declared from centre lines, not measured widths. Structures missing from every source are not "
                    "excluded: verify in the field."}


def exclusion_metric(feature: dict[str, Any], crs: str):
    """The zone's stored exclusion polygon in the metric CRS, or None."""
    from shapely.geometry import shape

    from .geo import to_metric

    infra = (feature.get("properties") or {}).get("infrastructure") or {}
    g = infra.get("geometry")
    return to_metric(shape(g), crs) if g else None
