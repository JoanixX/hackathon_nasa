"""Properties for terrain tiles, zone validation, zone datasets and the assisted boundary proposal.

Network-bound sources (Copernicus DEM, GIBS) are replaced by local synthetic rasters here; the live
paths are exercised by the end-to-end browser check.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from rasterio.transform import from_bounds
from shapely.geometry import Polygon, shape

from conftest import budget
from raiz_sar.geo import to_metric, utm_epsg_for
from raiz_sar.sources import lonlat_to_tile
from raiz_sar.terrain import decode_terrarium, encode_terrarium, slope_percent, tile_bounds
from raiz_sar.zones import ZoneError, build_zone_dataset, suggest_boundary, validate_polygon

PIURA = "lower-piura-sechura"


@settings(max_examples=budget(3000))
@given(st.lists(st.floats(-500, 9000, allow_nan=False), min_size=1, max_size=64))
def test_terrarium_round_trip(heights):
    h = np.array(heights, dtype="float64").reshape(1, -1)
    back = decode_terrarium(encode_terrarium(h))
    assert np.all(np.abs(back - h) <= 1 / 256 + 1e-9)


@settings(max_examples=budget(2000))
@given(st.integers(0, 14), st.floats(-179.9, 179.9), st.floats(-84, 84))
def test_tile_of_point_contains_point(z, lon, lat):
    x, y = lonlat_to_tile(lon, lat, z)
    w, s, e, n = tile_bounds(z, x, y)
    assert w - 1e-9 <= lon <= e + 1e-9 and s - 1e-9 <= lat <= n + 1e-9


@settings(max_examples=budget(1000))
@given(st.integers(1, 14), st.data())
def test_adjacent_tiles_share_edges(z, data):
    n = 2 ** z
    x = data.draw(st.integers(0, n - 2))
    y = data.draw(st.integers(0, n - 2))
    a, right, below = tile_bounds(z, x, y), tile_bounds(z, x + 1, y), tile_bounds(z, x, y + 1)
    assert math.isclose(a[2], right[0], abs_tol=1e-9) and math.isclose(a[1], below[3], abs_tol=1e-9)


@settings(max_examples=budget(1000))
@given(st.floats(-2, 2), st.floats(-2, 2), st.floats(5, 100))
def test_slope_of_plane_matches_analytic(gx, gy, res):
    yy, xx = np.mgrid[0:20, 0:20]
    dem = gx * xx * res + gy * yy * res
    s = slope_percent(dem, res)
    assert np.allclose(s[2:-2, 2:-2], 100 * math.hypot(gx, gy), rtol=1e-6, atol=1e-6)


@st.composite
def star_polygons(draw, lon=-79.612, lat=-5.375, min_n=3, max_n=12):
    """Simple (star-shaped, sorted by angle) polygons: never self-intersecting."""
    n = draw(st.integers(min_n, max_n))
    angles = sorted(draw(st.lists(st.floats(0, 2 * math.pi - 1e-3), min_size=n, max_size=n, unique=True)))
    assume(all(b - a > 0.05 for a, b in zip(angles, angles[1:])) and (2 * math.pi - angles[-1] + angles[0]) > 0.05)
    radii = draw(st.lists(st.floats(0.001, 0.003), min_size=n, max_size=n))
    ring = [[lon + r * math.cos(a), lat + r * math.sin(a)] for a, r in zip(angles, radii)]
    ring.append(ring[0])
    poly = Polygon(ring)
    assume(poly.is_valid)
    return {"type": "Polygon", "coordinates": [ring]}


@settings(max_examples=budget(1500))
@given(star_polygons())
def test_valid_star_polygons_accepted(geom):
    from raiz_sar.geo import geodesic_area_ha
    from raiz_sar.zones import MIN_AREA_HA

    # Contract: valid polygons are accepted unless below the minimum area (about one 30 m cell).
    # Minimized case: a sliver triangle of ~0.02 ha was correctly rejected by the area rule.
    if geodesic_area_ha(Polygon(geom["coordinates"][0])) < MIN_AREA_HA:
        with pytest.raises(ZoneError, match="smaller than"):
            validate_polygon(geom)
        return
    g = validate_polygon(geom)
    assert g.is_valid and not g.is_empty


@settings(max_examples=budget(1500))
@given(st.floats(0.002, 0.05), st.floats(0.002, 0.05))
def test_bowtie_rejected_with_reason(dx, dy):
    lon, lat = -80.62, -5.2
    ring = [[lon, lat], [lon + dx, lat + dy], [lon + dx, lat], [lon, lat + dy], [lon, lat]]
    with pytest.raises(ZoneError) as exc:
        validate_polygon({"type": "Polygon", "coordinates": [ring]})
    assert "Invalid polygon" in str(exc.value)


@settings(max_examples=budget(2000))
@given(st.one_of(st.none(), st.integers(), st.text(max_size=20), st.dictionaries(st.text(max_size=8), st.integers(), max_size=3),
                 st.fixed_dictionaries({"type": st.sampled_from(["Polygon", "Point", "MultiPolygon"]),
                                        "coordinates": st.recursive(st.floats(allow_nan=True, allow_infinity=True), lambda c: st.lists(c, max_size=5), max_leaves=30)})))
def test_validate_polygon_never_crashes(obj):
    try:
        g = validate_polygon(obj)
    except ZoneError:
        return
    assert g.is_valid


def fake_terrain(geom):
    return {"source": "test DEM", "cells": 100, "slope_percent_median": 12.5, "slope_percent_p10": 2.0, "slope_percent_p90": 30.0,
            "elevation_m_min": 10.0, "elevation_m_max": 80.0, "slope_histogram": {"edges_percent": [0, 5, 15, 30, 60, 100, 1000], "cells": [10, 40, 30, 15, 5, 0]},
            "note": "test", "grid": "test"}


@settings(max_examples=budget(400))
@given(st.lists(star_polygons(min_n=4, max_n=8), min_size=1, max_size=3), st.lists(st.sampled_from(["candidate", "no_go"]), min_size=3, max_size=3))
def test_zone_dataset_invariants(polys, roles):
    from raiz_sar.geo import geodesic_area_ha
    from raiz_sar.zones import MIN_AREA_HA

    assume(all(geodesic_area_ha(Polygon(g["coordinates"][0])) >= MIN_AREA_HA for g in polys))  # area rule tested separately
    # Shift polygons apart so only deliberate overlap tests overlap.
    zones = []
    for i, g in enumerate(polys):
        ring = [[x + i * 0.007, y] for x, y in g["coordinates"][0]]
        zones.append({"name": f"Z {i}", "geometry": {"type": "Polygon", "coordinates": [ring]}, "role": roles[i]})
    out = build_zone_dataset(PIURA, zones, terrain_fn=fake_terrain)
    feats = out["sectors"]["features"]
    assert len(feats) == len(zones)
    assert out["dataset_version"].startswith("zones-") and out["data_mode"] == "real"
    for f, z in zip(feats, zones):
        p = f["properties"]
        assert p["area_ha"]["value"] > 0 and p["slope_percent"]["evidence_class"] == "derived"
        assert (p["exclusion_reason"] is not None) == (z["role"] == "no_go")
        assert shape(f["geometry"]).equals(shape(z["geometry"]))  # never silently repaired or moved
        assert shape(p["original_geometry"]).equals(shape(z.get("original_geometry") or z["geometry"]))


@settings(max_examples=budget(300))
@given(st.one_of(star_polygons(min_n=3, max_n=3), star_polygons(min_n=9, max_n=12)))
def test_drawn_zone_vertex_count_outside_4_to_8_rejected(geom):
    from raiz_sar.geo import geodesic_area_ha
    from raiz_sar.zones import MIN_AREA_HA

    assume(geodesic_area_ha(Polygon(geom["coordinates"][0])) >= MIN_AREA_HA)
    with pytest.raises(ZoneError, match="a zone needs 4 to 8"):
        build_zone_dataset(PIURA, [{"geometry": geom}], terrain_fn=fake_terrain)


@settings(max_examples=budget(300))
@given(star_polygons(min_n=9, max_n=12))
def test_imported_zones_keep_their_vertices(geom):
    from raiz_sar.geo import geodesic_area_ha
    from raiz_sar.zones import MIN_AREA_HA

    assume(geodesic_area_ha(Polygon(geom["coordinates"][0])) >= MIN_AREA_HA)
    out = build_zone_dataset(PIURA, [{"geometry": geom, "imported": True}], terrain_fn=fake_terrain)
    assert shape(out["sectors"]["features"][0]["geometry"]).equals(shape(geom))


def test_overlapping_zones_rejected():
    a = {"type": "Polygon", "coordinates": [[[-79.615, -5.38], [-79.605, -5.38], [-79.605, -5.37], [-79.615, -5.37], [-79.615, -5.38]]]}
    b = {"type": "Polygon", "coordinates": [[[-79.61, -5.38], [-79.60, -5.38], [-79.60, -5.37], [-79.61, -5.37], [-79.61, -5.38]]]}
    with pytest.raises(ZoneError, match="overlap"):
        build_zone_dataset(PIURA, [{"geometry": a}, {"geometry": b}], terrain_fn=fake_terrain)


def test_zone_outside_region_rejected():
    far = {"type": "Polygon", "coordinates": [[[-77.0, -12.0], [-76.99, -12.0], [-76.99, -11.99], [-77.0, -11.99], [-77.0, -12.0]]]}
    with pytest.raises(ZoneError, match="outside"):
        build_zone_dataset(PIURA, [{"geometry": far}], terrain_fn=fake_terrain)


def test_dem_failure_keeps_slope_unknown():
    from raiz_sar.terrain import TerrainUnavailable

    def broken(_g):
        raise TerrainUnavailable("no coverage")

    g = {"type": "Polygon", "coordinates": [[[-79.615, -5.38], [-79.605, -5.38], [-79.605, -5.37], [-79.612, -5.372], [-79.615, -5.38]]]}
    out = build_zone_dataset(PIURA, [{"geometry": g}], terrain_fn=broken)
    q = out["sectors"]["features"][0]["properties"]["slope_percent"]
    assert q["value"] is None and q["evidence_class"] == "unknown"


def test_concurrent_requests_render_a_tile_once(monkeypatch, tmp_path):
    """Regression: terrain and hillshade request the same tile at once; both used one temp file and 503'd."""
    import threading
    import time

    import raiz_sar.terrain as T

    calls = []

    def fake_render(z, x, y, cache, path):
        calls.append((z, x, y))
        time.sleep(0.2)
        cache.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"png")
        return b"png"

    monkeypatch.setattr(T, "_render_tile", fake_render)
    z = 12
    x, y = lonlat_to_tile(-79.605, -5.375, z)
    results = []
    threads = [threading.Thread(target=lambda: results.append(T.terrain_tile_png(z, x, y))) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results == [b"png"] * 8 and calls == [(z, x, y)]


def _png(rgba):
    import warnings

    from rasterio.errors import NotGeoreferencedWarning
    from rasterio.io import MemoryFile

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", NotGeoreferencedWarning)
        with MemoryFile() as mf:
            with mf.open(driver="PNG", width=rgba.shape[2], height=rgba.shape[1], count=rgba.shape[0], dtype="uint8") as d:
                d.write(rgba)
            return mf.read()


@settings(max_examples=budget(200), deadline=None)
@given(st.integers(0, 255), st.integers(1, 255), st.integers(0, 255), st.integers(1, 255), st.integers(0, 3))
def test_proxy_makes_only_black_nodata_transparent(r, g, b, black_rows, channels_extra):
    """Regression: GIBS SAR tiles render no-data as opaque black squares that read as data."""
    import httpx
    from rasterio.io import MemoryFile

    import raiz_sar.sources as S

    a = np.zeros((3 + (1 if channels_extra % 2 else 0), 256, 256), dtype="uint8")
    a[0], a[1], a[2] = r, g, b
    if a.shape[0] == 4:
        a[3] = 255
    a[:3, :black_rows, :] = 0  # black no-data band
    content = _png(a)

    class R:
        status_code = 200

    R.content = content
    import shutil

    shutil.rmtree(S._cache("gibs_tiles") / "nisar_gcov", ignore_errors=True)  # each example fetches afresh
    shutil.rmtree(S._cache("gibs_raw") / "nisar_gcov", ignore_errors=True)  # raw tiles are cached too (shared with mosaics)
    client = S.http()
    S_get = client.get
    try:
        client.get = lambda *args, **kw: R()
        out = S.gibs_tile_transparent("nisar_gcov", "2026-10-31", 10, 280 + channels_extra, 526 + black_rows % 7)
    finally:
        client.get = S_get
    with MemoryFile(out) as m, m.open() as d:
        o = d.read()
    assert np.all(o[3, :black_rows, :] == 0)  # no-data is transparent
    assert np.all(o[3, black_rows:, :] == 255)  # data stays opaque
    assert np.array_equal(o[:3, black_rows:, :], a[:3, black_rows:, :])  # data pixels unchanged
    import shutil

    shutil.rmtree(S._cache("gibs_tiles"), ignore_errors=True)


def synthetic_dem(geom, res_m=30.0):
    """Local DEM with a valley and a ridge around the geometry (no network)."""
    crs = utm_epsg_for(geom.centroid.x, geom.centroid.y)
    gm = to_metric(geom, crs)
    minx, miny, maxx, maxy = gm.buffer(300).bounds
    w, h = int((maxx - minx) / res_m) + 1, int((maxy - miny) / res_m) + 1
    yy, xx = np.mgrid[0:h, 0:w]
    dem = (40 + 25 * np.sin(xx / 7.0) + 0.5 * yy).astype("float32")
    return dem, from_bounds(minx, miny, minx + w * res_m, miny + h * res_m, w, h), crs, gm


@settings(max_examples=budget(60), deadline=None)
@given(star_polygons())
def test_suggestion_is_a_valid_unapplied_proposal(geom):
    try:
        r = suggest_boundary(geom, None, dem_fn=lambda g: synthetic_dem(g))
    except ZoneError:
        return  # too small for a 30 m segmentation: reported, not faked
    assert r["status"] == "proposal" and r["applied"] is False
    assert r["user_geometry"] == validate_polygon(geom).__geo_interface__ or shape(r["user_geometry"]).equals(shape(geom))
    sug = shape(r["suggested_geometry"])
    assert sug.is_valid and not sug.is_empty
    assert 0.0 <= r["metrics"]["iou"] <= 1.0
    assert r["boundary_uncertainty_m"] == 30.0


@settings(max_examples=budget(800))
@given(st.integers(4, 60), st.data(), st.integers(4, 8))
def test_suggestions_are_limited_to_drawable_vertex_counts(n, data, max_v):
    """Suggested boundaries must be drawable: 4 to max_v vertices, valid, and they keep most of the area."""
    from raiz_sar.zones import limit_vertices

    # Star polygon with evenly spaced, jittered angles (no filtering) at metric scale (metres).
    jit = data.draw(st.lists(st.floats(-0.3, 0.3), min_size=n, max_size=n))
    rad = data.draw(st.lists(st.floats(200, 1500), min_size=n, max_size=n))
    pts = [(r * math.cos((i + j) * 2 * math.pi / n), r * math.sin((i + j) * 2 * math.pi / n)) for i, (j, r) in enumerate(zip(jit, rad))]
    poly = Polygon(pts)
    assume(poly.is_valid)
    out = limit_vertices(poly, max_v)
    n = len(out.exterior.coords) - 1
    assert out.is_valid and 4 <= n <= max_v
    assert out.area > 0.3 * poly.area
