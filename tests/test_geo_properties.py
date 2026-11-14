"""Coordinate conversion, area and tabletop-frame properties with independent oracles."""

from __future__ import annotations

import math

from hypothesis import assume, given, settings
from hypothesis import strategies as st
from shapely.geometry import box

from conftest import budget
from raiz_sar.geo import TabletopFrame, geodesic_area_ha, lonlat_to_metric, metric_to_lonlat, to_metric, to_wgs84, utm_epsg_for

# Peru-relevant extent; UTM zones 17S and 18S.
lons = st.floats(-81.3, -68.7, allow_nan=False)
lats = st.floats(-18.3, -0.1, allow_nan=False)


@settings(max_examples=budget(3000))
@given(lons, lats)
def test_utm_round_trip(lon, lat):
    crs = utm_epsg_for(lon, lat)
    x, y = lonlat_to_metric(lon, lat, crs)
    lon2, lat2 = metric_to_lonlat(x, y, crs)
    # Tolerance 1e-7 degrees (~1 cm): far below grid spacing; pyproj UTM is sub-millimetre in-zone.
    assert abs(lon2 - lon) < 1e-7 and abs(lat2 - lat) < 1e-7


@settings(max_examples=budget(2000))
@given(lons, lats)
def test_utm_zone_matches_formula(lon, lat):
    crs = utm_epsg_for(lon, lat)
    zone = int(crs.split(":")[1]) - 32700
    assert 1 <= zone <= 60
    central = -183 + 6 * zone
    assert abs(lon - central) <= 3 + 1e-9


@settings(max_examples=budget(1500))
@given(lons, lats, st.floats(10, 3000), st.floats(10, 3000))
def test_geodesic_area_matches_projected_area(lon, lat, w, h):
    crs = utm_epsg_for(lon, lat)
    x, y = lonlat_to_metric(lon, lat, crs)
    poly_m = box(x, y, x + w, y + h)
    poly = to_wgs84(poly_m, crs)
    planar_ha = poly_m.area / 10_000
    # Independent oracle: UTM scale distortion is below 0.1% near the central meridian and
    # below ~0.1-1% at zone edges; allow 1.5% (edges plus rectangle-to-geodesic edge curvature).
    assert math.isclose(geodesic_area_ha(poly), planar_ha, rel_tol=0.015)


@settings(max_examples=budget(3000))
@given(st.floats(-1e6, 1e6), st.floats(-1e6, 1e6), st.floats(1, 2e4), st.floats(1, 2e4),
       st.floats(0.2, 5), st.floats(0, 1), st.floats(0, 1))
def test_tabletop_frame_round_trip_and_containment(x0, y0, w, h, aspect, u, v):
    f = TabletopFrame((x0, y0, x0 + w, y0 + h), aspect)
    px, py = x0 + u * w, y0 + v * h
    ax, ay = f.to_ar(px, py)
    assert f.inside_target(ax, ay)  # every AOI point lands on the printed target
    bx, by = f.from_ar(ax, ay)
    assert math.isclose(bx, px, abs_tol=1e-6 * max(1, abs(px))) and math.isclose(by, py, abs_tol=1e-6 * max(1, abs(py)))


@settings(max_examples=budget(1000))
@given(st.floats(-1e5, 1e5), st.floats(-1e5, 1e5), st.floats(1, 1e4), st.floats(0.2, 5), st.floats(0.01, 100))
def test_tabletop_scale_is_uniform(x0, y0, w, aspect, ratio):
    h = w * ratio
    f = TabletopFrame((x0, y0, x0 + w, y0 + h), aspect)
    a = f.to_ar(x0, y0)
    b = f.to_ar(x0 + w, y0)
    c = f.to_ar(x0, y0 + h)
    # Same metres per unit on both axes: shapes are not distorted.
    assert math.isclose((b[0] - a[0]) * f.meters_per_unit, w, rel_tol=1e-9)
    assert math.isclose((c[1] - a[1]) * f.meters_per_unit, h, rel_tol=1e-9)


def test_degenerate_frame_rejected():
    import pytest

    with pytest.raises(ValueError):
        TabletopFrame((0, 0, 0, 10), 0.7)
    with pytest.raises(ValueError):
        utm_epsg_for(0, 85)


@settings(max_examples=budget(500))
@given(lons, lats)
def test_to_metric_then_wgs84_identity_for_polygons(lon, lat):
    assume(abs(lat) < 17)
    crs = utm_epsg_for(lon, lat)
    poly = box(lon, lat, lon + 0.01, lat + 0.01)
    back = to_wgs84(to_metric(poly, crs), crs)
    assert back.symmetric_difference(poly).area < 1e-12
