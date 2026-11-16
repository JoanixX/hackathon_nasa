"""Mapped features for an area from the OpenFreeMap vector tiles the map already uses (OpenMapTiles schema, OSM data).

Used server-side for: mapped waterways (ravine/quebrada references), infrastructure exclusions (buildings, roads,
paths, pedestrian areas) and parks. Tiles are fetched at z14 (OpenFreeMap's maximum detail), cached on disk and
decoded with raiz_sar.mvt. OSM coverage is incomplete in places (e.g. building footprints in Piura): absence of a
mapped feature is reported as "unmapped", never as "free space".
"""

from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path
from typing import Any

from . import mvt, perf, upstream
from .config import get_settings

TILEJSON = "https://tiles.openfreemap.org/planet"
Z = 14
ATTRIBUTION = "© OpenStreetMap contributors (ODbL) via OpenFreeMap / OpenMapTiles schema"


def _cache(name: str) -> Path:
    p = get_settings().runtime_dir / "cache" / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def tile_template() -> dict[str, Any]:
    path = _cache("ofm") / "tilejson.json"
    if path.exists() and time.time() - path.stat().st_mtime < 86400:
        return json.loads(path.read_text())
    from .sources import http

    r = upstream.get(http(), TILEJSON, timeout=20)
    if r.status_code != 200:
        if path.exists():
            return json.loads(path.read_text())
        raise upstream.UpstreamError(f"OpenFreeMap TileJSON HTTP {r.status_code}")
    tj = r.json()
    out = {"template": tj["tiles"][0], "maxzoom": tj.get("maxzoom", 14)}
    path.write_text(json.dumps(out))
    return out


def tiles_for(bbox, z: int = Z) -> list[tuple[int, int, int]]:
    w, s, e, n = bbox
    nz = 2 ** z

    def tx(lon):
        return min(nz - 1, max(0, int((lon + 180) / 360 * nz)))

    def ty(lat):
        return min(nz - 1, max(0, int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * nz)))

    xs, ys = range(tx(w), tx(e) + 1), range(ty(n), ty(s) + 1)
    if len(xs) * len(ys) > 400:
        raise ValueError("area too large for detailed features (max 400 tiles at z14)")
    return [(z, x, y) for x in xs for y in ys]


def fetch_tile(z: int, x: int, y: int) -> bytes:
    tj = tile_template()
    version = tj["template"].split("/")[-4]
    path = _cache("ofm") / version / str(z) / str(x) / f"{y}.pbf"
    if path.exists():
        return path.read_bytes()
    from .sources import http

    with perf.span("ofm.fetch"):
        r = upstream.get(http(), tj["template"].replace("{z}", str(z)).replace("{x}", str(x)).replace("{y}", str(y)), timeout=30)
    if r.status_code == 404:
        data = b""
    elif r.status_code != 200:
        raise upstream.UpstreamError(f"OpenFreeMap tile HTTP {r.status_code}")
    else:
        data = r.content
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{y}.{os.getpid()}.tmp")
    tmp.write_bytes(data)
    tmp.replace(path)
    return data


def features(bbox, layers: set[str], z: int = Z) -> dict[str, list[dict[str, Any]]]:
    """GeoJSON-like features (lon/lat) per layer for the bbox, clipped to it, deduplicated across tiles."""
    from shapely.geometry import LineString, Point, Polygon, box, mapping
    from shapely.ops import unary_union

    clip = box(*bbox)
    out: dict[str, list[dict[str, Any]]] = {L: [] for L in layers}
    for z, x, y in tiles_for(bbox, z):
        data = fetch_tile(z, x, y)
        if not data:
            continue
        dec = mvt.decode(data, layers)
        for L, layer in dec.items():
            ext = layer["extent"]
            for f in layer["features"]:
                parts = [[mvt.to_lonlat(px, py, z, x, y, ext) for px, py in p] for p in f["parts"]]
                geoms = []
                if f["type"] == "Point":
                    geoms = [Point(p[0]) for p in parts if p]
                elif f["type"] == "LineString":
                    geoms = [LineString(p) for p in parts if len(p) >= 2]
                else:
                    # Exterior rings (positive area in tile space) start polygons; following negative rings are holes.
                    polys, cur = [], None
                    for raw, ll in zip(f["parts"], parts):
                        if len(ll) < 4:
                            continue
                        if mvt.ring_area(raw) > 0 or cur is None:
                            cur = [ll, []]
                            polys.append(cur)
                        else:
                            cur[1].append(ll)
                    for ext_ring, holes in polys:
                        g = Polygon(ext_ring, holes).buffer(0)
                        if not g.is_empty:
                            geoms.append(g)
                for g in geoms:
                    gi = g.intersection(clip)
                    if not gi.is_empty:
                        out[L].append({"geometry": gi, "props": f["props"]})
    # Polygons split at tile borders are merged per layer and identical properties.
    for L, feats in out.items():
        polys = [f for f in feats if f["geometry"].geom_type in ("Polygon", "MultiPolygon")]
        if len(polys) > 1:
            groups: dict[str, list] = {}
            for f in polys:
                groups.setdefault(json.dumps(f["props"], sort_keys=True, default=str), []).append(f)
            merged = []
            for key, fs in groups.items():
                u = unary_union([f["geometry"] for f in fs])
                for g in (u.geoms if hasattr(u, "geoms") else [u]):
                    merged.append({"geometry": g, "props": fs[0]["props"]})
            out[L] = [f for f in feats if f not in polys] + merged
    return out


def as_geojson(feats: list[dict[str, Any]], **extra) -> dict[str, Any]:
    from shapely.geometry import mapping

    return {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": mapping(f["geometry"]), "properties": {**f["props"], **extra}} for f in feats]}
