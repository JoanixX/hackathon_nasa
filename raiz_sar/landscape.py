"""Area overview of huayco-relevant terrain: mapped quebradas with basin geomorphometry, and steep terrain.

For a map area (at most 0.3 x 0.3 degrees):
- Quebradas: natural OpenStreetMap waterways (stream / river). Each is classified by the Melton ruggedness number of the
  basin draining to its lowest-accumulation outlet inside the analysis window (Melton 1965; classes after Wilford et al.
  2004: debris-flow prone R > 0.6, debris flood 0.3-0.6, flood < 0.3). Basins that reach the window edge are truncated
  and left "unknown" rather than misclassified.
- Steep terrain: slope classes of FAO (2006) Guidelines for soil description: 0-2 flat, 2-5 gently sloping, 5-10
  sloping, 10-15 strongly sloping, 15-30 moderately steep, 30-60 steep, > 60 % very steep. Steep and very steep areas
  are returned as polygons (where debris can be mobilised) with their areas.
DEM: Copernicus GLO-30 resampled to ``RES_M`` for the area (a surface model; vertical accuracy < 4 m LE90).
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from . import hydro, perf

RES_M = 90.0
FAO_CLASSES = [(0, 2, "flat"), (2, 5, "gently_sloping"), (5, 10, "sloping"), (10, 15, "strongly_sloping"),
               (15, 30, "moderately_steep"), (30, 60, "steep"), (60, 1e9, "very_steep")]


def snap(bbox) -> tuple[float, float, float, float]:
    w, s, e, n = bbox
    w, s = math.floor(w * 20) / 20, math.floor(s * 20) / 20
    e, n = math.ceil(e * 20) / 20, math.ceil(n * 20) / 20
    if e - w > 0.3 or n - s > 0.3:
        cx, cy = (w + e) / 2, (s + n) / 2
        w, e, s, n = cx - 0.15, cx + 0.15, cy - 0.15, cy + 0.15
    return (round(w, 3), round(s, 3), round(e, 3), round(n, 3))


def analyse(bbox) -> dict[str, Any]:
    from rasterio.features import shapes
    from shapely.geometry import box, mapping, shape

    from . import osm_features
    from .geo import to_metric, to_wgs84
    from .terrain import metric_dem

    aoi = snap(bbox)
    with perf.span("landscape.dem"):
        dem, tf, crs, gm = metric_dem(box(*aoi), margin_m=0, res_m=RES_M)
    with perf.span("landscape.hydro"):
        filled = hydro.priority_flood(dem, epsilon=1e-3)
        rec = hydro.d8_receivers(filled, RES_M)
        acc = hydro.accumulation(filled, rec)
        zmax_up, reaches_edge = hydro.upstream_stats(dem, filled, rec)
    h, w = dem.shape
    slope_pct = np.tan(hydro.slope_rad(dem, RES_M)) * 100
    valid = np.isfinite(dem)
    cell_ha = RES_M * RES_M / 1e4
    classes = {name: round(float(((slope_pct >= lo) & (slope_pct < hi) & valid).sum()) * cell_ha, 1) for lo, hi, name in FAO_CLASSES}
    # Steep (30-60 %) and very steep (> 60 %) polygons.
    steep_code = np.zeros(dem.shape, dtype="uint8")
    steep_code[(slope_pct >= 30) & valid] = 1
    steep_code[(slope_pct >= 60) & valid] = 2
    steep_feats = []
    for geom, val in shapes(steep_code, mask=steep_code > 0, transform=tf):
        g = shape(geom)
        if g.area < 4 * RES_M * RES_M:
            continue
        g84 = to_wgs84(g.simplify(RES_M / 2), crs)
        steep_feats.append({"type": "Feature", "geometry": _round(mapping(g84)), "properties": {"class": "very_steep" if val == 2 else "steep",
                                                                                                "area_ha": round(g.area / 1e4, 2)}})
    steep_feats.sort(key=lambda f: -f["properties"]["area_ha"])
    # Mapped natural waterways and their basins.
    with perf.span("landscape.waterways"):
        ways = osm_features.features(aoi, {"waterway"}, z=13).get("waterway", [])  # z13 carries streams; ~4x fewer tiles
    quebradas = []
    counts = {"debris_flow_prone": 0, "debris_flood": 0, "flood": 0, "unknown": 0}
    for f in ways:
        cls = f["props"].get("class")
        if cls not in ("stream", "river") or f["geometry"].geom_type not in ("LineString", "MultiLineString"):
            continue
        gm_line = to_metric(f["geometry"], crs)
        pts = [gm_line.interpolate(d) for d in np.arange(0, gm_line.length + 1, RES_M)]
        cells = []
        for p in pts:
            c = int((p.x - tf.c) / tf.a)
            r = int((p.y - tf.f) / tf.e)
            if 0 <= r < h and 0 <= c < w and valid[r, c]:
                cells.append((r, c))
        if not cells:
            continue
        r0, c0 = max(cells, key=lambda rc: acc[rc])  # outlet = highest upslope area along the mapped line
        area_km2 = float(acc[r0, c0]) * RES_M * RES_M / 1e6
        truncated = bool(reaches_edge[r0, c0])
        if truncated or cls == "river" or area_km2 <= 0:
            m = {"melton_ratio": None, "class": "unknown", "basin_area_km2": round(area_km2, 3),
                 "note": "Basin extends beyond the analysed area" if truncated else "Large river: flood corridor, not a debris-flow basin"}
        else:
            relief = float(zmax_up[r0, c0] - dem[r0, c0])
            R = (relief / 1000.0) / math.sqrt(area_km2)
            m = {"melton_ratio": round(R, 3), "relief_m": round(relief, 1), "basin_area_km2": round(area_km2, 3),
                 "class": "debris_flow_prone" if R > hydro.WILFORD["debris_flow"] else "debris_flood" if R > hydro.WILFORD["debris_flood"] else "flood"}
        key = m["class"] if m["class"] in counts else "unknown"
        counts[key] += 1
        quebradas.append({"type": "Feature", "geometry": _round(mapping(f["geometry"])),
                          "properties": {"name": f["props"].get("name"), "waterway": cls, "intermittent": bool(f["props"].get("intermittent")),
                                         "hazard_class": key, "melton_ratio": m.get("melton_ratio"), "basin_area_km2": m.get("basin_area_km2"),
                                         "relief_m": m.get("relief_m")}})
    z = dem[valid]
    return {"aoi": list(aoi), "grid": f"{crs} at {RES_M:g} m", "source": "Copernicus DEM GLO-30; OpenStreetMap waterways (ODbL)",
            "elevation_m": {"min": round(float(z.min()), 1), "max": round(float(z.max()), 1)} if z.size else None,
            "slope_classes_ha": classes, "steep": {"type": "FeatureCollection", "features": steep_feats[:800]},
            "steep_ha": round(classes["steep"] + classes["very_steep"], 1),
            "quebradas": {"type": "FeatureCollection", "features": quebradas}, "quebrada_counts": counts,
            "methods": {"slope_classes": "FAO (2006) Guidelines for soil description",
                        "basins": "priority-flood + epsilon, D8; Melton (1965) ruggedness with Wilford et al. (2004) classes"},
            "limits": ["Only mapped natural waterways are classified; unmapped quebradas are not counted.",
                       f"DEM resampled to {RES_M:g} m for the area overview; zone-level checks use 30 m.",
                       "Melton classes indicate basin type susceptibility, not the probability or timing of a huayco."]}


def _round(g):
    def r(c):
        return [round(c[0], 5), round(c[1], 5)] if isinstance(c[0], (int, float)) else [r(x) for x in c]
    return {"type": g["type"], "coordinates": r(g["coordinates"])}
