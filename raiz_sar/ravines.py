"""Ravine (quebrada) corridors, huayco start-point decisions and zone hydrology on real terrain and mapped data.

Decisions for a requested huayco start point (NV-03), checked by the API before any playback/job:
- "accepted": a mapped waterway lies within the tolerance AND the DEM steepest-descent path from the point
  follows that waterway (mean distance of the first ``AGREE_CELLS`` path cells within the tolerance).
- "rejected": no mapped waterway within the tolerance, the area's waterway mapping was read, and the DEM shows
  no flow convergence at the point (upslope area below ``CONVERGENCE_CELLS`` cells): a hillslope or flat, not a
  channel.
- "insufficient": anything else (DEM convergence without a mapped waterway, mapped line the DEM disagrees with,
  or data unavailable). Playback stays blocked; the point is not called "not a ravine".
Tolerance = one DEM cell diagonal (30 m * sqrt 2), the coarser of the two sources' scales.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from . import hydro

RES_M = 30.0
TOL_M = RES_M * math.sqrt(2)
AGREE_CELLS = 10           # first 300 m of the downhill path must follow the mapped waterway
CONVERGENCE_CELLS = 10     # < 10 upslope cells (0.009 km2): no channel at the point
WINDOW_M = 3000.0
NATURAL = {"stream", "river"}            # OpenMapTiles waterway classes for natural channels
ARTIFICIAL = {"drain", "canal", "ditch"}  # engineered channels: not ravines


def _waterways(bbox) -> tuple[list, bool]:
    ways, _water, ok = _water_features(bbox)
    return ways, ok


def _water_features(bbox) -> tuple[list, list, bool]:
    """(waterway lines, water-body polygons, mapping read)."""
    from . import osm_features

    try:
        f = osm_features.features(bbox, {"waterway", "water"})
    except Exception:  # noqa: BLE001 - reported as unavailable mapping, never as "no ravine"
        return [], [], False
    return f.get("waterway", []), f.get("water", []), True


def analyse_point(lon: float, lat: float) -> dict[str, Any]:
    from shapely.geometry import LineString, Point

    from .geo import metric_to_lonlat, to_metric
    from .terrain import TerrainUnavailable, metric_dem

    if not (-180 <= lon <= 180 and -60 <= lat <= 60):
        raise ValueError("invalid point")
    pt = Point(lon, lat)
    try:
        dem, tf, crs, gm = metric_dem(pt.buffer(WINDOW_M / 111_000), margin_m=0, res_m=RES_M)
    except (TerrainUnavailable, OSError, ValueError) as exc:
        return {"decision": "insufficient", "reason": f"Terrain unavailable: {exc}", "message": "Ravine evidence is insufficient here. Verify the location before starting the view."}
    filled = hydro.priority_flood(dem)
    rec = hydro.d8_receivers(filled, RES_M)
    acc = hydro.accumulation(filled, rec)
    pm = to_metric(pt, crs)
    px, py = pm.x, pm.y
    c = int((px - tf.c) / tf.a)
    r = int((py - tf.f) / tf.e)
    h, w = dem.shape
    if not (0 <= r < h and 0 <= c < w) or not np.isfinite(dem[r, c]):
        return {"decision": "insufficient", "reason": "Point outside the DEM window.", "message": "Ravine evidence is insufficient here. Verify the location before starting the view."}
    # Downhill path on the receiver graph (first AGREE_CELLS cells).
    path_rc = [(r, c)]
    k = r * w + c
    for _ in range(AGREE_CELLS):
        k2 = int(rec.ravel()[k])
        if k2 < 0:
            break
        path_rc.append(divmod(k2, w))
        k = k2
    path_xy = [(tf.c + (cc + 0.5) * tf.a, tf.f + (rr + 0.5) * tf.e) for rr, cc in path_rc]
    # Mapped waterways near the point (lon/lat bbox of the window).
    lw, ls, le, ln = pt.buffer(1500 / 111_000).bounds
    ways, water, mapped_read = _water_features((lw, ls, le, ln))
    ways_m = [(to_metric(f["geometry"], crs), f["props"]) for f in ways if f["geometry"].geom_type in ("LineString", "MultiLineString")]
    # A click on a mapped river surface (OSM water polygon) counts as on the river.
    on_river_surface = any(f["geometry"].geom_type in ("Polygon", "MultiPolygon") and f["geometry"].contains(pt) for f in water)
    near = sorted(((g.distance(pm), g, p) for g, p in ways_m), key=lambda t: t[0])
    upslope_cells = float(acc[r, c])
    basin = hydro.upstream_mask(rec, r * w + c)
    truncated = bool(basin[0, :].any() or basin[-1, :].any() or basin[:, 0].any() or basin[:, -1].any())
    if truncated:
        # The basin continues beyond the analysed DEM window: its area/relief are lower bounds, so no class is given.
        geomorph = {"basin_area_km2_lower_bound": round(float(basin.sum()) * RES_M * RES_M / 1e6, 4), "melton_ratio": None, "class": "unknown",
                    "truncated": True, "note": f"The upslope basin extends beyond the {WINDOW_M / 1000:.0f} km analysis window; Melton ratio not computed."}
    else:
        geomorph = {**hydro.melton(dem, basin, RES_M, (r, c)), "truncated": False}
    corridor = None
    decision, reason = "insufficient", ""
    natural_near = [t for t in near if t[2].get("class") in NATURAL]
    artificial_near = [t for t in near if t[2].get("class") in ARTIFICIAL]
    rivers_near = [t for t in near if t[2].get("class") == "river"]
    if rivers_near and (rivers_near[0][0] <= TOL_M or (on_river_surface and rivers_near[0][0] <= 1000)):
        # Large rivers: the DEM (surface model) does not resolve a channel on the flat floodplain, so the corridor is
        # the mapped river itself and the event is a flood that follows its centre line downstream.
        dist, g, props = rivers_near[0]
        corridor = {"name": props.get("name"), "class": "river", "kind": "flood", "intermittent": bool(props.get("intermittent")),
                    "distance_m": round(dist, 1), "on_mapped_water_surface": on_river_surface}
        decision, reason = "accepted", "Mapped river: the event follows the river centre line downstream (flood corridor)."
    elif natural_near and natural_near[0][0] <= TOL_M:
        dist, g, props = natural_near[0]
        mean_dev = float(np.mean([g.distance(Point(x, y)) for x, y in path_xy]))
        corridor = {"name": props.get("name"), "class": props.get("class"), "kind": "debris_flow", "intermittent": bool(props.get("intermittent")),
                    "distance_m": round(dist, 1), "path_mean_deviation_m": round(mean_dev, 1)}
        if mean_dev <= TOL_M and len(path_xy) > 1 and upslope_cells >= CONVERGENCE_CELLS:
            decision, reason = "accepted", "Natural mapped waterway within one DEM cell, the DEM downhill path follows it and flow converges."
        elif upslope_cells < CONVERGENCE_CELLS:
            reason = "A natural waterway is mapped here but the DEM shows no flow convergence at this cell (flat or DEM resolution)."
        else:
            reason = "A natural waterway is mapped here but the DEM downhill path leaves it (resolution or mapping disagreement)."
    elif artificial_near and artificial_near[0][0] <= TOL_M:
        corridor = {"name": artificial_near[0][2].get("name"), "class": artificial_near[0][2].get("class"), "distance_m": round(artificial_near[0][0], 1)}
        decision, reason = "rejected", f"Engineered channel ({artificial_near[0][2].get('class')}), not a natural ravine."
    elif mapped_read and upslope_cells < CONVERGENCE_CELLS:
        decision, reason = "rejected", "No mapped waterway within one DEM cell and no flow convergence on the DEM (hillslope or flat)."
    elif not mapped_read:
        reason = "Waterway mapping could not be read for this area."
    else:
        reason = "The DEM shows converging flow but no waterway is mapped here."
    messages = {"accepted": "Start point accepted in the mapped ravine corridor.",
                "rejected": "This point is outside a mapped ravine. Choose a highlighted corridor.",
                "insufficient": "Ravine evidence is insufficient here. Verify the location before starting the view."}
    corridors = [{"type": "Feature", "geometry": _mapping(f["geometry"]), "properties": {"name": f["props"].get("name"), "class": f["props"].get("class"),
                  "intermittent": bool(f["props"].get("intermittent"))}} for f in ways if f["props"].get("class") in NATURAL]
    return {"decision": decision, "message": messages[decision], "reason": reason, "point": [lon, lat],
            "nearest_mapped_waterway_m": round(near[0][0], 1) if near else None,
            "tolerance_m": round(TOL_M, 1), "upslope_cells": int(upslope_cells), "upslope_area_km2": round(upslope_cells * RES_M * RES_M / 1e6, 4),
            "corridor": corridor, "catchment": geomorph, "eligible_corridors": {"type": "FeatureCollection", "features": corridors},
            "sources": ["Copernicus DEM GLO-30 (surface model)", "OpenStreetMap waterways via OpenFreeMap (ODbL)"],
            "method": "priority-flood + D8 on the DEM; agreement with mapped waterways within one DEM cell diagonal"}


def _mapping(g):
    from shapely.geometry import mapping

    m = mapping(g)
    def rd(c):
        return [round(c[0], 6), round(c[1], 6)] if isinstance(c[0], (int, float)) else [rd(x) for x in c]
    return {"type": m["type"], "coordinates": rd(m["coordinates"])}


def zone_hydrology(geom_lonlat) -> dict[str, Any]:
    """Per-zone wetness and ponding potential from the DEM (TWI, closed depressions, upslope area)."""
    from rasterio.features import geometry_mask
    from shapely.geometry import mapping

    from .terrain import metric_dem

    dem, tf, crs, gm = metric_dem(geom_lonlat, margin_m=600, res_m=RES_M)
    filled = hydro.priority_flood(dem)
    rec = hydro.d8_receivers(filled, RES_M)
    acc = hydro.accumulation(filled, rec)
    sl = hydro.slope_rad(dem, RES_M)
    t = hydro.twi(acc, sl, RES_M)
    inside = geometry_mask([mapping(gm)], out_shape=dem.shape, transform=tf, invert=True)
    dep = hydro.depressions(dem, filled, RES_M)
    depth = dep["depth"]
    zone_depth = depth[inside & (depth > 0.01)]
    tv = t[inside & np.isfinite(t)]
    return {"twi": {"median": round(float(np.median(tv)), 2) if tv.size else None, "p90": round(float(np.percentile(tv, 90)), 2) if tv.size else None,
                    "method": "ln(a / tan(slope)), Beven & Kirkby (1979); relative index, higher = wetter"},
            "depressions": {"cells_in_zone": int((inside & (depth > 0.01)).sum()), "area_ha": round(float((inside & (depth > 0.01)).sum()) * RES_M * RES_M / 1e4, 3),
                            "max_depth_m": round(float(zone_depth.max()), 2) if zone_depth.size else 0.0,
                            "stored_volume_m3": round(float(zone_depth.sum()) * RES_M * RES_M, 1),
                            "within_dem_uncertainty": bool(zone_depth.size == 0 or zone_depth.max() < hydro.DEM_VERTICAL_LE90_M),
                            "method": "priority-flood fill depth (Barnes et al. 2014)"},
            "max_upslope_area_km2": round(float(acc[inside].max()) * RES_M * RES_M / 1e6, 4) if inside.any() else None,
            "dem_vertical_accuracy_le90_m": hydro.DEM_VERTICAL_LE90_M, "source": "Copernicus DEM GLO-30 (surface model)"}


def _elevation(lon: float, lat: float) -> float | None:
    """Median DEM elevation in a 90 m box around a point (Copernicus GLO-30)."""
    from .terrain import read_dem

    try:
        dem, _tf, covered = read_dem(lon - 0.0005, lat - 0.0005, lon + 0.0005, lat + 0.0005)
    except Exception:  # noqa: BLE001
        return None
    v = dem[np.isfinite(dem)]
    return float(np.median(v)) if covered and v.size else None


def river_path(lon: float, lat: float, max_km: float = 6.0) -> dict[str, Any]:
    """Flood path along a mapped river: its centre line from the point downstream (direction = lower DEM end)."""
    from shapely.geometry import LineString, MultiLineString, Point
    from shapely.ops import linemerge, substring, unary_union

    from .geo import to_metric, to_wgs84, utm_epsg_for

    pt = Point(lon, lat)
    crs = utm_epsg_for(lon, lat)
    deg = (max_km * 1000 + 500) / 111_000
    ways, _water, ok = _water_features((lon - deg, lat - deg, lon + deg, lat + deg))
    lines = [to_metric(f["geometry"], crs) for f in ways if f["props"].get("class") == "river" and f["geometry"].geom_type in ("LineString", "MultiLineString")]
    if not lines:
        raise ValueError("No mapped river near this point.")
    parts = []
    for g in lines:
        parts.extend(g.geoms if isinstance(g, MultiLineString) else [g])
    # Vector-tile pieces of one river leave small gaps at tile borders (generalisation). Chain them greedily from the
    # piece nearest the point: at each end, attach the unused piece whose end point is closest within GAP_M (declared).
    GAP_M = 200.0
    pm = to_metric(pt, crs)
    pieces = [list(g.coords) for g in parts if g.length > 0]
    used = [False] * len(pieces)
    k0 = min(range(len(pieces)), key=lambda i: LineString(pieces[i]).distance(pm))
    used[k0] = True
    chain = pieces[k0][:]

    def extend(at_end: bool) -> bool:
        tip = Point(chain[-1] if at_end else chain[0])
        best = None
        for i, c in enumerate(pieces):
            if used[i]:
                continue
            for rev, q in ((False, c[0]), (True, c[-1])):
                d = tip.distance(Point(q))
                if d <= GAP_M and (best is None or d < best[0]):
                    best = (d, i, rev)
        if best is None:
            return False
        _, i, rev = best
        used[i] = True
        seq = pieces[i][::-1] if rev else pieces[i]
        if at_end:
            chain.extend(seq)
        else:
            chain[:0] = seq[::-1]
        return True

    while extend(True):
        pass
    while extend(False):
        pass
    line = LineString(chain)
    s0 = line.project(pm)
    a = to_wgs84(Point(line.coords[0]), crs)
    b = to_wgs84(Point(line.coords[-1]), crs)
    za, zb = _elevation(a.x, a.y), _elevation(b.x, b.y)
    if za is None or zb is None or abs(za - zb) < 1e-6:
        raise ValueError("The river's downstream direction cannot be determined from the DEM here.")
    downstream_to_end = zb < za
    end = min(line.length, s0 + max_km * 1000) if downstream_to_end else max(0.0, s0 - max_km * 1000)
    seg = substring(line, s0, end)
    if seg.length < 30:
        raise ValueError("The mapped river ends here: no downstream reach to follow.")
    n = max(2, int(seg.length // 30) + 1)
    pts = [seg.interpolate(i / (n - 1), normalized=True) for i in range(n)]
    coords = [to_wgs84(p, crs) for p in pts]
    z0, z1 = _elevation(coords[0].x, coords[0].y), _elevation(coords[-1].x, coords[-1].y)
    return {"type": "Feature",
            "geometry": {"type": "LineString", "coordinates": [[round(p.x, 6), round(p.y, 6)] for p in coords]},
            "properties": {"kind": "flood", "length_m": round(seg.length, 1), "start_elevation_m": z0, "end_elevation_m": z1,
                           "drop_m": round((z0 or 0) - (z1 or 0), 1), "river_end_elevations_m": [round(za, 1), round(zb, 1)],
                           "method": "Mapped OSM river centre line, followed downstream; direction from Copernicus DEM elevations at both ends",
                           "source": "OpenStreetMap (ODbL) via OpenFreeMap; Copernicus DEM GLO-30",
                           "note": "Flood corridor along the river. Extent, depth and timing are not modeled."}}
