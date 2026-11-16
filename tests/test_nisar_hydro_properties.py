"""Properties for the NISAR water classifier, DEM hydrology, the MVT decoder, NISAR-gated planning and
infrastructure exclusions. Synthetic inputs test the contracts; the real-data check is separate (see docs)."""

from __future__ import annotations

import math

import numpy as np
import pytest
from fastapi.testclient import TestClient
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from hypothesis.extra import numpy as hnp

from conftest import budget
from raiz_sar import hydro, mvt
from raiz_sar.sar import water as W


# ------------------------------------------------------------------ water classifier
@settings(max_examples=budget(400), deadline=None)
@given(st.floats(-28, -18), st.floats(-12, -4), st.floats(0.05, 0.6), st.integers(0, 2**31 - 1))
def test_otsu_splits_two_separated_modes(m_water, m_land, share, seed):
    rng = np.random.default_rng(seed)
    n = 4000
    k = int(n * share)
    v = np.concatenate([rng.normal(m_water, 1.0, k), rng.normal(m_land, 1.0, n - k)])
    t = W.otsu(v)
    assert t is not None and m_water < t < m_land


@settings(max_examples=budget(300), deadline=None)
@given(hnp.arrays(np.float64, (12, 12), elements=st.floats(-30, 0)), st.lists(hnp.arrays(np.float64, (12, 12), elements=st.floats(-30, 0)), min_size=1, max_size=3),
       st.floats(-25, -10), hnp.arrays(np.bool_, (12, 12)), st.integers(1, 6))
def test_classes_are_consistent_with_their_definitions(event, bases, thr, nan_mask, mmu):
    event = np.where(nan_mask, np.nan, event)
    p = W.Params(mmu_pixels=mmu)
    c = W.classify(event, bases, thr, None, p)
    base = np.stack(bases)
    bmean = base.mean(axis=0)
    bwater = (base < thr).sum(axis=0) >= math.ceil(0.5 * len(bases))
    # Unknown exactly where the event or a baseline sample is invalid.
    assert np.array_equal(c == W.UNKNOWN, ~np.isfinite(event))
    new, per, rec = c == W.NEW_WATER, c == W.PERSISTENT, c == W.RECEDED
    with np.errstate(invalid="ignore"):
        assert np.all(event[new] < thr) and not np.any(bwater[new]) and np.all(event[new] - bmean[new] <= p.delta_db + 1e-9)
        assert np.all(event[per] < thr) and np.all(bwater[per])
        assert np.all(bwater[rec]) and np.all(event[rec] >= thr) and np.all(event[rec] - bmean[rec] >= -p.delta_db - 1e-9)


@settings(max_examples=budget(200), deadline=None)
@given(st.integers(1, 3), st.integers(4, 9))
def test_minimum_mapping_unit_drops_small_groups_only(size, mmu):
    event = np.full((20, 20), -5.0)
    base = [np.full((20, 20), -5.0)]
    event[2:2 + size, 2:2 + size] = -25.0     # small new-water group
    event[10:13, 10:13] = -25.0                # 9-pixel group
    c = W.classify(event, base, -15.0, None, W.Params(mmu_pixels=mmu))
    assert (c[2:2 + size, 2:2 + size] == W.NEW_WATER).all() == (size * size >= mmu)
    assert (c[10:13, 10:13] == W.NEW_WATER).all() == (9 >= mmu)


@settings(max_examples=budget(500))
@given(hnp.arrays(np.bool_, 50), hnp.arrays(np.bool_, 50), hnp.arrays(np.bool_, 50))
def test_confusion_metrics_are_bounded_and_counted_on_reference_pixels(pred, ref, valid):
    m = W.confusion(pred, ref, valid)
    assert m["true_positive"] + m["false_positive"] + m["false_negative"] <= m["reference_pixels"] == int(valid.sum())
    for k in ("precision", "recall", "iou"):
        assert m[k] is None or 0 <= m[k] <= 1


@settings(max_examples=budget(200), deadline=None)
@given(st.floats(-26, -20), st.floats(-12, -6), st.integers(0, 2**31 - 1))
def test_calibration_separates_reference_water_from_land(m_w, m_l, seed):
    from raiz_sar.nisar_evidence import calibrate

    rng = np.random.default_rng(seed)
    db = rng.normal(m_l, 0.8, (40, 40))
    water = np.zeros((40, 40), bool)
    water[5:20, 5:20] = True
    db[water] = rng.normal(m_w, 0.8, water.sum())
    cal = calibrate([(db, {"valid": np.ones((40, 40), bool), "water": water})])
    assert cal["threshold_db"] is not None and m_w < cal["threshold_db"] < m_l and cal["train_f1"] > 0.95


def test_calibration_refuses_without_reference_water():
    from raiz_sar.nisar_evidence import calibrate

    db = np.full((30, 30), -10.0)
    cal = calibrate([(db, {"valid": np.ones((30, 30), bool), "water": np.zeros((30, 30), bool)})])
    assert cal["threshold_db"] is None


# ------------------------------------------------------------------ hydrology
dems = hnp.arrays(np.float64, st.tuples(st.integers(3, 14), st.integers(3, 14)), elements=st.floats(0, 100, allow_nan=False))


@settings(max_examples=budget(400), deadline=None)
@given(dems)
def test_filled_surface_never_lowers_terrain_and_everything_drains(dem):
    filled = hydro.priority_flood(dem)
    assert np.all(filled >= dem - 1e-9)
    rec = hydro.d8_receivers(filled + np.indices(dem.shape).sum(axis=0) * 0.0, 30.0)
    acc = hydro.accumulation(filled, rec)
    # Mass balance: upslope counts end at outlets (cells without receiver) and sum to the cell count.
    outlets = rec.ravel() < 0
    assert math.isclose(acc.ravel()[outlets].sum(), dem.size)
    # No cycles: following receivers from any cell reaches an outlet within n steps.
    r = rec.ravel()
    for i in range(dem.size):
        k, steps = i, 0
        while r[k] >= 0:
            k = r[k]
            steps += 1
            assert steps <= dem.size


@settings(max_examples=budget(300))
@given(st.floats(1, 3000), st.floats(0.001, 500))
def test_melton_classes_follow_wilford_thresholds(relief, area_km2):
    res = 30.0
    n = max(1, int(round(area_km2 * 1e6 / res ** 2)))
    side = int(math.ceil(math.sqrt(n)))
    assume(side <= 400)
    dem = np.zeros((side, side))
    basin = np.zeros((side, side), bool)
    basin.ravel()[:n] = True
    dem.ravel()[0] = relief
    assume(side > 1)
    m = hydro.melton(dem, basin, res, (side - 1, side - 1))  # outlet at elevation 0 (any cell but the summit)
    R = m["melton_ratio"]
    if R is not None:
        assert m["class"] == ("debris_flow_prone" if R > 0.6 else "debris_flood" if R > 0.3 else "flood")


# ------------------------------------------------------------------ MVT decoder round trip
def _vint(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def _field(num, wt, payload):
    key = _vint((num << 3) | wt)
    return key + (_vint(payload) if wt == 0 else _vint(len(payload)) + payload)


def _zz(n):
    return (n << 1) ^ (n >> 63)


def _encode_line(points):
    cmds = [(1 << 3) | 1, _zz(points[0][0]), _zz(points[0][1]), ((len(points) - 1) << 3) | 2]
    x, y = points[0]
    for px, py in points[1:]:
        cmds += [_zz(px - x), _zz(py - y)]
        x, y = px, py
    return cmds


@settings(max_examples=budget(500))
@given(st.lists(st.lists(st.tuples(st.integers(-200, 4300), st.integers(-200, 4300)), min_size=2, max_size=8), min_size=1, max_size=5),
       st.text("abcdefgh", min_size=1, max_size=8))
def test_mvt_decoder_round_trips_lines_and_tags(lines, cls):
    feats = b""
    for pts in lines:
        geom = b"".join(_vint(c) for c in _encode_line(pts))
        f = _field(2, 2, _vint(0) + _vint(0)) + _field(3, 0, 2) + _field(4, 2, geom)
        feats += _field(2, 2, f)
    value = _field(1, 2, cls.encode())
    layer = _field(15, 0, 2) + _field(1, 2, b"waterway") + feats + _field(3, 2, b"class") + _field(4, 2, value) + _field(5, 0, 4096)
    tile = _field(3, 2, layer)
    out = mvt.decode(tile)
    got = out["waterway"]["features"]
    assert [f["parts"][0] for f in got] == [list(p) for p in lines]
    assert all(f["props"] == {"class": cls} and f["type"] == "LineString" for f in got)


@settings(max_examples=budget(1000))
@given(st.binary(max_size=200))
def test_mvt_decoder_never_crashes_on_garbage(data):
    try:
        mvt.decode(data)
    except mvt.MVTError:
        pass


# ------------------------------------------------------------------ NISAR-gated planning
def _ev(new=0.0, per=0.0, cov=1.0):
    return {"zones": {"Z01": {"valid_coverage": cov, "areas_ha": {"new_water": new, "persistent_low_backscatter": per, "receded": 0.0, "unknown": 0.0, "not_water": 1.0}}},
            "event_date": "2026-10-31"}


@settings(max_examples=budget(400))
@given(st.floats(0, 5), st.floats(0, 5), st.floats(0, 1))
def test_nisar_mode_makes_a_zone_eligible_only_with_observed_new_water(new, per, cov):
    from raiz_sar.planning import MIN_NISAR_VALID_COVERAGE, _nisar_reasons

    status, reasons = _nisar_reasons("Z01", _ev(new, per, cov))
    assert (status == "eligible") == (cov >= MIN_NISAR_VALID_COVERAGE and new > 0)
    assert reasons


def test_nisar_mode_requires_a_run_and_missing_zone_is_not_eligible():
    from pydantic import ValidationError

    from raiz_sar.contracts import PlanRequest
    from raiz_sar.planning import _nisar_reasons

    with pytest.raises(ValidationError):
        PlanRequest(scenario_id="lower-piura-sechura", dataset_version="x", evidence_mode="nisar")
    assert _nisar_reasons("Z09", _ev(3.0))[0] == "field_assessment_required"


def test_plan_with_unknown_nisar_run_is_rejected():
    from raiz_sar.api import app

    c = TestClient(app)
    s = c.get("/api/scenarios/lower-piura-sechura").json()
    r = c.post("/api/plans", json={"scenario_id": "lower-piura-sechura", "dataset_version": s["summary"]["dataset_version"],
                                   "evidence_mode": "nisar", "nisar_run_id": "0123456789abcdef"})
    assert r.status_code in (409, 422) and "NISAR evidence" in r.text


# ------------------------------------------------------------------ huayco start gate on the server
@pytest.mark.parametrize("decision", ["rejected", "insufficient"])
def test_flowpath_refuses_points_outside_accepted_ravines(monkeypatch, decision):
    import raiz_sar.ravines as R
    from raiz_sar.api import app

    monkeypatch.setattr(R, "analyse_point", lambda lon, lat: {"decision": decision, "message": "m", "reason": "r", "eligible_corridors": {}})
    r = TestClient(app).get("/api/terrain/flowpath", params={"lon": -80.6, "lat": -5.2})
    assert r.status_code == 409 and r.json()["error"] == f"ravine_{decision}"


# ------------------------------------------------------------------ infrastructure exclusions in drone nodes
@settings(max_examples=budget(60), deadline=None)
@given(st.floats(0.0005, 0.003), st.floats(0.0005, 0.003))
def test_drone_nodes_keep_crown_clearance_from_mapped_infrastructure(bw, bh):
    from shapely.geometry import Point, box, mapping

    from raiz_sar.contracts import BudgetScenario, DroneParameters, SectorAllocation
    from raiz_sar.drone import plan_deposition
    from raiz_sar.geo import to_metric
    from raiz_sar.scenarios import SPECIES_MAX_CROWN_RADIUS_M

    zone = box(-80.640, -5.210, -80.630, -5.200)
    infra = box(-80.636, -5.206, -80.636 + bw, -5.206 + bh)
    feat = {"type": "Feature", "geometry": mapping(zone), "properties": {"sector_id": "Z01", "infrastructure": {"geometry": mapping(infra)}}}
    alloc = SectorAllocation.model_construct(sector_id="Z01", capsules=100, funded_fraction=1.0)
    budget_s = BudgetScenario.model_construct(allocations=[alloc])
    plan = plan_deposition([feat], budget_s, DroneParameters(node_spacing_m=25), "EPSG:32717")
    infra_m = to_metric(infra, "EPSG:32717")
    for n in plan.nodes:
        p = to_metric(Point(n.lon, n.lat), "EPSG:32717")
        assert infra_m.distance(p) >= SPECIES_MAX_CROWN_RADIUS_M - 1e-6
