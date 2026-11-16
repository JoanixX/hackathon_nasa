"""Building footprints from Overture Maps (OSM + Google Open Buildings + Microsoft ML footprints), read by range requests.

OpenStreetMap alone maps only a small share of Piura's buildings (13 footprints vs. 12,816 in one central z14 tile).
Overture's buildings theme merges OSM with Google Open Buildings and Microsoft ML Building Footprints; each feature
keeps its source (``@geometry_source``) and, for detections, a confidence. Tiles are served to the map through the API
(cached on disk) and decoded server-side for planting exclusions.

Licences: buildings theme ODbL; Google Open Buildings CC BY 4.0; Microsoft ML Building Footprints ODbL.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from . import mvt, perf, pmtiles
from .config import get_settings

RELEASE = os.environ.get("RAIZ_OVERTURE_RELEASE", "2026-10-21.0")
URL = f"https://overturemaps-extras-us-west-2.s3.us-west-2.amazonaws.com/tiles/{RELEASE}/buildings.pmtiles"
ATTRIBUTION = "Buildings: © OpenStreetMap contributors, Overture Maps Foundation (ODbL); Google Open Buildings (CC BY 4.0); Microsoft ML Building Footprints (ODbL)"
MIN_ZOOM, MAX_ZOOM = 13, 14


def _cache(z: int, x: int, y: int) -> Path:
    return get_settings().runtime_dir / "cache" / "overture" / RELEASE / str(z) / str(x) / f"{y}.pbf"


def tile_gzip(z: int, x: int, y: int) -> bytes:
    """Gzip-compressed MVT bytes as stored in the archive (empty when absent); cached on disk per release.
    Served to the browser with Content-Encoding: gzip (about 10x smaller than the decoded tile)."""
    path = _cache(z, x, y).with_suffix(".pbf.gz")
    if path.exists():
        with perf.span("overture.cache_hit"):
            return path.read_bytes()
    with perf.span("overture.fetch", z=z):
        data = pmtiles.get_tile(URL, z, x, y, decompress=False) or b""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{y}.{os.getpid()}.tmp")
    tmp.write_bytes(data)
    tmp.replace(path)
    return data


def tile(z: int, x: int, y: int) -> bytes:
    """Decoded (uncompressed) MVT bytes for server-side use."""
    import gzip

    data = tile_gzip(z, x, y)
    return gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data


def buildings(bbox) -> list[dict[str, Any]]:
    """Building polygons (lon/lat shapely) with source/height properties for a bbox, at z14."""
    from shapely.geometry import Polygon, box

    from .osm_features import tiles_for

    clip = box(*bbox)
    out = []
    seen: set[str] = set()
    for z, x, y in tiles_for(bbox, MAX_ZOOM):
        data = tile(z, x, y)
        if not data:
            continue
        layer = mvt.decode(data, {"building"}).get("building")
        if not layer:
            continue
        ext = layer["extent"]
        for f in layer["features"]:
            fid = f["props"].get("id")
            if fid and fid in seen:
                continue  # the same building appears in neighbouring tiles' buffers
            polys, cur = [], None
            for raw in f["parts"]:
                ll = [mvt.to_lonlat(px, py, z, x, y, ext) for px, py in raw]
                if len(ll) < 4:
                    continue
                if mvt.ring_area(raw) > 0 or cur is None:
                    cur = [ll, []]
                    polys.append(cur)
                else:
                    cur[1].append(ll)
            for ring, holes in polys:
                g = Polygon(ring, holes).buffer(0)
                if not g.is_empty and g.intersects(clip):
                    out.append({"geometry": g, "props": {"source": f["props"].get("@geometry_source"), "height": f["props"].get("height"),
                                                         "num_floors": f["props"].get("num_floors")}})
            if fid:
                seen.add(fid)
    return out
