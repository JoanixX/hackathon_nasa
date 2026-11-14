"""GIS import boundary: valid exports normalize correctly; malformed input fails safely."""

from __future__ import annotations

import copy
import json
import math

from hypothesis import given, settings
from hypothesis import strategies as st
from shapely.geometry import shape

from conftest import budget
from raiz_sar.gis_import import LEGACY_KEYS, ImportErrorReport, normalize_feature_collection


def legacy_feature(i, lon, lat, size, props):
    ring = [[lon, lat], [lon + size, lat], [lon + size, lat + size], [lon, lat + size], [lon, lat]]
    return {"type": "Feature", "id": f"F{i}", "geometry": {"type": "Polygon", "coordinates": [ring]}, "properties": props}


legacy_props = st.fixed_dictionaries({
    "nombre": st.text(min_size=1, max_size=40).filter(lambda s: s.strip() and any(c.isprintable() and not c.isspace() for c in s)),
}, optional={
    "hectareas": st.floats(0.01, 5000, allow_nan=False),
    "pendiente": st.floats(0, 200, allow_nan=False),
    "sigma_hh": st.floats(-40, 10, allow_nan=False),
    "sigma_hv": st.floats(-40, 10, allow_nan=False),
    "dielectric_er": st.floats(1, 80, allow_nan=False),
    "rvi": st.floats(0, 1, allow_nan=False),
    "especie": st.sampled_from(["Tara", "Algarrobo", "Prosopis pallida", ""]),
    "unrelated_field": st.text(max_size=10),
})


@st.composite
def valid_collections(draw):
    n = draw(st.integers(1, 8))
    feats = [legacy_feature(i, -77.2 + i * 0.01, -11.9, draw(st.floats(0.0005, 0.008)), draw(legacy_props)) for i in range(n)]
    return {"type": "FeatureCollection", "features": feats}


@settings(max_examples=budget(1500))
@given(valid_collections())
def test_valid_legacy_exports_normalize(fc):
    out = normalize_feature_collection(fc, "carabayllo-rio-seco", "test")
    feats = out["sectors"]["features"]
    assert len(feats) + len(out["rejected"]) == len(fc["features"])
    ids = [f["properties"]["sector_id"] for f in feats]
    assert len(set(ids)) == len(ids)
    for f in feats:
        p = f["properties"]
        # Only English internal keys survive; legacy keys are translated at the boundary.
        assert not set(LEGACY_KEYS) - {"dielectric_er", "rvi"} & set(p)
        assert p["area_ha"]["value"] > 0 and p["area_ha"]["evidence_class"] == "derived"
        assert shape(f["geometry"]).is_valid
        for k in ("slope_percent", "sigma_hh_db", "sigma_hv_db", "dielectric_er", "rvi"):
            q = p[k]
            assert (q["value"] is None) == (q["evidence_class"] == "unknown")
            assert q["value"] is None or math.isfinite(q["value"])
        # A supplied dielectric value is never presented as observed telemetry.
        if p["dielectric_er"]["value"] is not None:
            assert p["dielectric_er"]["evidence_class"] == "illustrative"


def _json_values():
    return st.recursive(
        st.one_of(st.none(), st.booleans(), st.integers(-10**12, 10**12), st.floats(allow_nan=True, allow_infinity=True),
                  st.text(max_size=30)),
        lambda c: st.one_of(st.lists(c, max_size=6), st.dictionaries(st.sampled_from(
            ["type", "features", "geometry", "coordinates", "properties", "nombre", "id", "crs", "x"]), c, max_size=6)),
        max_leaves=60)


@settings(max_examples=budget(3000))
@given(_json_values())
def test_arbitrary_json_fails_safely(obj):
    try:
        out = normalize_feature_collection(obj, "carabayllo-rio-seco", "fuzz")
    except ImportErrorReport as exc:
        assert str(exc)
        return
    for f in out["sectors"]["features"]:
        assert shape(f["geometry"]).is_valid


def test_regression_null_properties_rejected():
    """Minimized from the campaign: a feature with null properties is rejected, not crashed on."""
    fc = {"type": "FeatureCollection", "features": [legacy_feature(0, -77.2, -11.9, 0.001, None)]}
    try:
        normalize_feature_collection(fc, "carabayllo-rio-seco", "regression")
    except ImportErrorReport as exc:
        assert "sector_name" in " ".join(exc.details)
    else:
        raise AssertionError("expected rejection")


MUTATORS = ["nan_coord", "projected_coord", "open_ring", "self_intersect", "point_geom", "dup_id", "string_area",
            "neg_area", "bool_slope", "huge_name", "deep_nesting", "empty_coords", "three_d", "bad_crs", "null_props"]


@settings(max_examples=budget(2000))
@given(valid_collections(), st.lists(st.sampled_from(MUTATORS), min_size=1, max_size=3), st.integers(0, 7))
def test_structured_mutations_are_rejected_or_valid(fc, muts, idx):
    fc = copy.deepcopy(fc)
    f = fc["features"][idx % len(fc["features"])]
    ring = f["geometry"]["coordinates"][0]
    # Structure-destroying mutations run last so earlier mutators still find their targets
    # (minimized harness defects: ['null_props', 'huge_name'] and ['point_geom', 'three_d']).
    muts = sorted(muts, key=lambda m: m in ("null_props", "point_geom", "deep_nesting", "empty_coords"))
    for m in muts:
        if m == "nan_coord":
            ring[1][0] = float("nan")
        elif m == "projected_coord":
            ring[2] = [312000.0, 8690000.0]
        elif m == "open_ring":
            ring.pop()
        elif m == "self_intersect":
            ring[1], ring[2] = ring[2], ring[1]
        elif m == "point_geom":
            f["geometry"] = {"type": "Point", "coordinates": [-77.0, -11.8]}
        elif m == "dup_id":
            f["id"] = fc["features"][0]["id"]
        elif m == "string_area":
            f["properties"]["hectareas"] = "twelve"
        elif m == "neg_area":
            f["properties"]["hectareas"] = -3
        elif m == "bool_slope":
            f["properties"]["pendiente"] = True
        elif m == "huge_name":
            f["properties"]["nombre"] = "x" * 5000
        elif m == "deep_nesting":
            f["geometry"]["coordinates"] = [[[[[[[[[0]]]]]]]]]
        elif m == "empty_coords":
            f["geometry"]["coordinates"] = []
        elif m == "three_d":
            for pt in ring:
                pt.append(10.0)
        elif m == "bad_crs":
            fc["crs"] = {"type": "name", "properties": {"name": "EPSG:32718"}}
        elif m == "null_props":
            f["properties"] = None
            break
    try:
        out = normalize_feature_collection(json.loads(json.dumps(fc, allow_nan=True)), "carabayllo-rio-seco", "mut")
    except ImportErrorReport:
        return
    for g in out["sectors"]["features"]:
        geom = shape(g["geometry"])
        assert geom.is_valid and geom.geom_type in ("Polygon", "MultiPolygon")
        minx, miny, maxx, maxy = geom.bounds
        assert -180 <= minx <= maxx <= 180 and -90 <= miny <= maxy <= 90
        assert len(g["properties"]["sector_name"]) <= 120
