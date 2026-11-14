"""Coordinate, area and tabletop-frame utilities.

Geographic coordinates are WGS 84 longitude/latitude (GeoJSON order). Metric work uses the
UTM zone of the actual AOI, chosen from its centroid rather than assigned globally.
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Iterable

import shapely
from pyproj import CRS, Geod, Transformer
from shapely.geometry import MultiPolygon, Polygon, mapping, shape
from shapely.geometry.base import BaseGeometry

GEOD = Geod(ellps="WGS84")
WGS84 = "EPSG:4326"


def utm_epsg_for(lon: float, lat: float) -> str:
    if not (-180.0 <= lon <= 180.0 and -80.0 <= lat <= 84.0):
        raise ValueError("coordinate outside UTM coverage")
    zone = min(60, int((lon + 180.0) // 6.0) + 1)
    base = 32600 if lat >= 0 else 32700
    return f"EPSG:{base + zone}"


@lru_cache(maxsize=32)
def _transformer(src: str, dst: str) -> Transformer:
    return Transformer.from_crs(CRS.from_user_input(src), CRS.from_user_input(dst), always_xy=True)


def _reproject(geom: BaseGeometry, tr: Transformer) -> BaseGeometry:
    return shapely.transform(geom, lambda x, y: tr.transform(x, y), interleaved=False)


def to_metric(geom: BaseGeometry, metric_crs: str) -> BaseGeometry:
    return _reproject(geom, _transformer(WGS84, metric_crs))


def to_wgs84(geom: BaseGeometry, metric_crs: str) -> BaseGeometry:
    return _reproject(geom, _transformer(metric_crs, WGS84))


def lonlat_to_metric(lon: float, lat: float, metric_crs: str) -> tuple[float, float]:
    return _transformer(WGS84, metric_crs).transform(lon, lat)


def metric_to_lonlat(x: float, y: float, metric_crs: str) -> tuple[float, float]:
    return _transformer(metric_crs, WGS84).transform(x, y)


def geodesic_area_ha(geom: BaseGeometry) -> float:
    """Geodesic (ellipsoidal) area in hectares of a lon/lat polygon geometry."""
    area_m2, _ = GEOD.geometry_area_perimeter(geom)
    return abs(area_m2) / 10_000.0


def geometry_from_geojson(obj: dict) -> BaseGeometry:
    geom = shape(obj)
    if not isinstance(geom, (Polygon, MultiPolygon)):
        raise ValueError("geometry must be Polygon or MultiPolygon")
    return geom


def geometry_to_geojson(geom: BaseGeometry) -> dict:
    return mapping(geom)


class TabletopFrame:
    """Affine mapping between a metric AOI bounding box and the AR image-target plane.

    The target plane is 1 AR unit wide (MindAR convention) and ``aspect`` units high,
    centred on the origin, with +x east and +y north. Scale is uniform so shapes are not
    distorted; the AOI is fitted inside the target with a margin.
    """

    def __init__(self, bounds_m: tuple[float, float, float, float], aspect: float, margin: float = 0.06):
        minx, miny, maxx, maxy = bounds_m
        if not (maxx > minx and maxy > miny):
            raise ValueError("degenerate AOI bounds")
        if not (0.1 <= aspect <= 10):
            raise ValueError("unsupported target aspect")
        self.aspect = aspect
        self.origin_x = (minx + maxx) / 2.0
        self.origin_y = (miny + maxy) / 2.0
        usable_w = 1.0 - 2 * margin
        usable_h = aspect - 2 * margin
        self.meters_per_unit = max((maxx - minx) / usable_w, (maxy - miny) / usable_h)

    def to_ar(self, x_m: float, y_m: float) -> tuple[float, float]:
        return ((x_m - self.origin_x) / self.meters_per_unit, (y_m - self.origin_y) / self.meters_per_unit)

    def from_ar(self, x: float, y: float) -> tuple[float, float]:
        return (x * self.meters_per_unit + self.origin_x, y * self.meters_per_unit + self.origin_y)

    def inside_target(self, x: float, y: float) -> bool:
        return abs(x) <= 0.5 + 1e-9 and abs(y) <= self.aspect / 2 + 1e-9


def union_bounds(geoms: Iterable[BaseGeometry]) -> tuple[float, float, float, float]:
    b = [g.bounds for g in geoms]
    if not b:
        raise ValueError("no geometries")
    return (min(x[0] for x in b), min(x[1] for x in b), max(x[2] for x in b), max(x[3] for x in b))


def finite(*values: float) -> bool:
    return all(isinstance(v, (int, float)) and math.isfinite(v) for v in values)
