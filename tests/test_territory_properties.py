"""Independent geographic and budget oracles; all I/O isolated from live data/credentials."""
import math

import numpy as np
import pytest
from affine import Affine
from fastapi.testclient import TestClient
from hypothesis import given, settings, strategies as st

from conftest import budget
from raiz_sar.api import app
from raiz_sar.territory import nearest_sample, tile_plan
from raiz_sar.terrain import tile_bounds


@settings(max_examples=budget(2000))
@given(st.integers(0, 7), st.integers(0, 7), st.floats(-100, 5000, allow_nan=False, allow_infinity=False), st.booleans())
def test_point_sampling_preserves_missingness_and_cell_values(row, col, value, missing):
    dem = np.full((8, 8), 123.0)
    dem[row, col] = np.nan if missing else value
    tf = Affine.translation(-81, -4) * Affine.scale(.01, -.01)
    lon, lat = tf * (col + .5, row + .5)
    assert nearest_sample(dem, tf, lon, lat) == (None if missing else round(value, 2))
    assert nearest_sample(dem, tf, -100, -40) is None


@settings(max_examples=budget(2000))
@given(st.floats(-81.2, -79.4, allow_nan=False), st.floats(-6.2, -4.3, allow_nan=False), st.integers(7, 12), st.integers(1, 64))
def test_tile_plan_has_no_duplicates_and_covers_the_requested_box(lon, lat, zoom, limit):
    bbox = [lon, lat, lon + .01, lat + .01]
    try:
        plan = tile_plan(bbox, zoom, zoom, limit)
    except ValueError:
        # Independent minimal covering rectangle count from the spherical Mercator equations.
        n = 2**zoom
        x0, x1 = math.floor((lon + 180) / 360 * n), math.floor((lon + .01 + 180) / 360 * n)
        y0 = math.floor((1 - math.asinh(math.tan(math.radians(lat + .01))) / math.pi) / 2 * n)
        y1 = math.floor((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
        assert (x1-x0+1)*(y1-y0+1) > limit
        return
    assert len(plan) <= limit and len(plan) == len(set(plan))
    boxes = [tile_bounds(*t) for t in plan]
    for p in [(lon, lat), (lon + .01 - 1e-10, lat + .01 - 1e-10)]:
        assert any(w <= p[0] <= e and s <= p[1] <= n for w, s, e, n in boxes)


@settings(max_examples=budget(1000))
@given(st.one_of(st.none(), st.text(max_size=64), st.lists(st.floats(allow_nan=True, allow_infinity=True), max_size=8)))
def test_bad_tile_plans_fail_before_io(bbox):
    if isinstance(bbox, list) and len(bbox) == 4 and all(math.isfinite(v) for v in bbox) and -180 <= bbox[0] < bbox[2] <= 180 and -85 < bbox[1] < bbox[3] < 85:
        return
    with pytest.raises(ValueError):
        tile_plan(bbox, 7, 8)


def test_point_api_unknown_is_not_zero_and_invalid_positions_are_rejected(monkeypatch):
    import raiz_sar.territory as t
    monkeypatch.setattr(t, "_in_regions", lambda _b: True)
    monkeypatch.setattr(t, "read_dem", lambda *a: (np.full((4,4), np.nan), Affine.identity(), False))
    with TestClient(app) as client:
        result = client.get("/api/terrain/point?lon=-80.6&lat=-5.2")
        assert result.status_code == 200
        assert result.json()["elevation_m"] is None and result.json()["evidence_class"] == "unknown"
        assert result.json()["vertical_crs"] == "EPSG:3855"
        for point in ["lon=nan&lat=0", "lon=0&lat=inf", "lon=181&lat=-5", "lon=-80&lat=-90"]:
            assert client.get("/api/terrain/point?"+point).status_code == 422
