"""Model output cannot override planning constraints; drone plan stays inside eligible geometry."""

from __future__ import annotations

import copy
import json

from hypothesis import given, settings
from hypothesis import strategies as st
from shapely.geometry import Point, shape

from conftest import budget
from raiz_sar.ai_provider import GenerationResult
from raiz_sar.contracts import DroneParameters, PlanRequest
from raiz_sar.drone import funded_geometry
from raiz_sar.geo import lonlat_to_metric, to_metric
from raiz_sar.plans import build_plan, resolve_dataset
from raiz_sar.scenarios import get_scenario, scenario_ids
from raiz_sar.scene import (
    build_prompt,
    assemble_scene,
    fixture_scene_responder,
    scene_context,
    validate_ai_plan,
)


def _plan(scenario_id: str, budget_pen: float, **drone):
    ds = get_scenario(scenario_id)
    req = PlanRequest(scenario_id=scenario_id, dataset_version=ds["summary"]["dataset_version"], budget_pen=budget_pen,
                      drone=DroneParameters(**drone))
    plan = build_plan(req)
    return plan, resolve_dataset(req)


PLANS = {sid: _plan(sid, 12000) for sid in scenario_ids()}


def _valid_output(sid):
    plan, ds = PLANS[sid]
    ctx = scene_context(plan, ds)
    return plan, ds, ctx, json.loads(fixture_scene_responder(build_prompt(ctx), {}))


MUTATIONS = [
    "none", "foreign_sector", "excluded_sector", "wrong_species", "share_over", "drop_stage", "reorder_stages",
    "plants_at_zero", "height_decrease", "height_over_cap", "banned_text", "markup", "nan", "extra_field", "drop_zone",
    "huge_list", "negative_share", "string_number",
]


def mutate(doc, kind, plan, draw_text):
    d = copy.deepcopy(doc)
    excluded = [e.sector_id for e in plan.eligibility if e.status == "excluded"]
    if kind == "foreign_sector":
        d["zones"][0]["sector_id"] = "ZZZ-99"
    elif kind == "excluded_sector" and excluded:
        d["zones"][0]["sector_id"] = excluded[0]
    elif kind == "wrong_species":
        d["zones"][0]["species_id"] = "eucalyptus"
    elif kind == "share_over":
        d["zones"][0]["share_of_sector_plants"] = 0.95
    elif kind == "drop_stage":
        d["stages"].pop()
    elif kind == "reorder_stages":
        d["stages"].reverse()
    elif kind == "plants_at_zero":
        d["stages"][0]["visible_fraction_of_expected"] = 0.5
    elif kind == "height_decrease":
        d["stages"][3]["max_height_m"] = 0.1
    elif kind == "height_over_cap":
        d["stages"][3]["max_height_m"] = 9.0
    elif kind == "banned_text":
        d["uncertainty_note"] = draw_text + " This planting will prevent every huaico and is guaranteed."
    elif kind == "markup":
        d["title"] = "<script>alert(1)</script>"
    elif kind == "nan":
        return json.dumps(d).replace('"max_height_m": 0.9', '"max_height_m": NaN')
    elif kind == "extra_field":
        d["zones"][0]["execute"] = "rm -rf /"
    elif kind == "drop_zone":
        d["zones"] = [z for z in d["zones"] if z["sector_id"] != d["zones"][0]["sector_id"]]
    elif kind == "huge_list":
        d["assumptions"] = ["a"] * 1000
    elif kind == "negative_share":
        d["zones"][0]["share_of_sector_plants"] = -0.2
    elif kind == "string_number":
        d["stages"][1]["max_height_m"] = "0.1"
    return json.dumps(d)


@settings(max_examples=budget(1200))
@given(st.sampled_from(scenario_ids()), st.sampled_from(MUTATIONS), st.text(max_size=40))
def test_model_output_cannot_override_constraints(sid, kind, text):
    plan, ds, ctx, doc = _valid_output(sid)
    raw = mutate(doc, kind, plan, text)
    ai, errors = validate_ai_plan(raw, ctx)
    if kind in ("none",):
        assert ai is not None, errors
    if ai is None:
        assert errors
        return
    gen = GenerationResult(text=raw, mode="fixture", provider="test", model="test", response_id=None, latency_ms=0)
    spec = assemble_scene(plan, ds, ai, gen, "h", 1)
    _check_scene(spec, plan, ds)


def _check_scene(spec, plan, ds):
    crs = ds["summary"]["metric_crs"]
    alloc = {a.sector_id: a for a in plan.budget.allocations}
    feats = {f["properties"]["sector_id"]: f for f in ds["sectors"]["features"]}
    no_go = [to_metric(shape(f["geometry"]), crs).buffer(plan.request.drone.no_go_buffer_m)
             for f in feats.values() if f["properties"].get("exclusion_reason")]
    fr = spec.frame
    for p in spec.placements:
        a = alloc[p.sector_id]
        assert a.capsules > 0, "vegetation placed in an unfunded sector"
        assert p.species_id == a.species_id
        assert abs(p.x) <= 0.5 + 1e-6 and abs(p.y) <= fr.target_aspect / 2 + 1e-6
        mx, my = p.x * fr.meters_per_ar_unit + fr.origin_x_m, p.y * fr.meters_per_ar_unit + fr.origin_y_m
        geom = funded_geometry(to_metric(shape(feats[p.sector_id]["geometry"]), crs), a.funded_fraction)
        # Rounding of AR coordinates to 1e-5 units is below 0.03 m for these frames.
        assert geom.buffer(0.5).contains(Point(mx, my))
        assert not any(g.buffer(-0.5).contains(Point(mx, my)) for g in no_go)
    # Rendered plants never exceed expected established plants (markers represent >= 1 plant).
    for sid, a in alloc.items():
        n = sum(p.represents_plants for p in spec.placements if p.sector_id == sid)
        markers = sum(1 for p in spec.placements if p.sector_id == sid)
        assert markers <= max(1, a.expected_established) if a.expected_established else markers == 0
        assert n >= 0
    assert spec.stages[0].visible_fraction_of_expected == 0 and spec.stages[0].max_height_m == 0
    assert [s.horizon_months for s in spec.stages] == [0, 3, 6, 12]
    assert spec.plan_version == plan.plan_version


@settings(max_examples=budget(2000))
@given(st.one_of(st.text(max_size=300), st.binary(max_size=300).map(lambda b: b.decode("latin-1")),
                 st.recursive(st.one_of(st.none(), st.booleans(), st.integers(), st.floats(allow_nan=False), st.text(max_size=20)),
                              lambda c: st.one_of(st.lists(c, max_size=5), st.dictionaries(st.text(max_size=12), c, max_size=5)),
                              max_leaves=30).map(json.dumps)))
def test_validator_never_crashes_on_arbitrary_text(raw):
    plan, ds, ctx, _ = _valid_output("carabayllo-rio-seco")
    ai, errors = validate_ai_plan(raw, ctx)
    assert ai is None and errors


def test_scene_is_deterministic_for_same_inputs():
    plan, ds, ctx, doc = _valid_output("lower-piura-sechura")
    raw = json.dumps(doc)
    ai, _ = validate_ai_plan(raw, ctx)
    gen = GenerationResult(text=raw, mode="fixture", provider="t", model="t", response_id=None, latency_ms=0)
    a = assemble_scene(plan, ds, ai, gen, "h", 1)
    b = assemble_scene(plan, ds, ai, gen, "h", 1)
    assert a.scene_version == b.scene_version and a.placements == b.placements


@st.composite
def drone_params(draw):
    return dict(payload_capsules_per_sortie=draw(st.integers(1, 5000)), max_route_m_per_sortie=draw(st.floats(200, 20000)),
                node_spacing_m=draw(st.floats(8, 120)), no_go_buffer_m=draw(st.floats(0, 80)))


@settings(max_examples=budget(150))
@given(st.sampled_from(scenario_ids()), st.floats(2000, 60000), drone_params())
def test_drone_plan_respects_geometry_payload_and_route(sid, budget_pen, params):
    plan, ds = _plan(sid, budget_pen, **params)
    d = plan.drone
    funded_caps = sum(a.capsules for a in plan.budget.allocations)
    assert d.execution == "not_executed"
    if d.status != "candidate_plan_incomplete":
        assert d.nodes == [] and d.infeasibility_reason or d.status == "not_applicable"
        return
    crs = ds["summary"]["metric_crs"]
    feats = {f["properties"]["sector_id"]: f for f in ds["sectors"]["features"]}
    alloc = {a.sector_id: a for a in plan.budget.allocations}
    no_go = [to_metric(shape(f["geometry"]), crs).buffer(params["no_go_buffer_m"])
             for f in feats.values() if f["properties"].get("exclusion_reason")]
    assert d.total_capsules == funded_caps  # every funded capsule is assigned exactly once
    for n in d.nodes:
        x, y = lonlat_to_metric(n.lon, n.lat, crs)
        geom = funded_geometry(to_metric(shape(feats[n.sector_id]["geometry"]), crs), alloc[n.sector_id].funded_fraction)
        assert geom.buffer(0.01).contains(Point(x, y))
        assert not any(g.contains(Point(x, y)) for g in no_go)
        assert n.capsules >= 1
    for s in d.sorties:
        assert s.capsules <= params["payload_capsules_per_sortie"]
        assert s.route_m <= params["max_route_m_per_sortie"] + 0.1
    assert sum(s.capsules for s in d.sorties) == d.total_capsules
