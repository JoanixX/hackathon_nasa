"""Contracts for bounded work, scope, reproducible municipal quantities and cent reconciliation."""
import math

import pytest
from hypothesis import given, settings, strategies as st
from shapely.geometry import box, mapping

from conftest import budget
from raiz_sar.contracts import PlanRequest
from raiz_sar.drone import candidate_grid
from raiz_sar.municipal import municipal_content
from raiz_sar.plans import build_plan, resolve_dataset
from raiz_sar.scenarios import get_scenario, screening_scope
from raiz_sar.zones import ZoneError, build_zone_dataset


@settings(max_examples=budget(2000))
@given(st.floats(.001, 1e6), st.floats(.001, 1e6), st.floats(2, 1000), st.integers(0, 6000))
def test_candidate_work_is_bounded_even_for_long_thin_large_areas(w, h, spacing, limit):
    bounds = (100, -200, 100+w, -200+h)
    points = list(candidate_grid(bounds, spacing, limit))
    assert len(points) <= limit
    assert len(set(points)) == len(points)
    assert all(100 <= x <= 100+w and -200 <= y <= -200+h for x, y in points)
    assert points == list(candidate_grid(bounds, spacing, limit))


@settings(max_examples=budget(1000))
@given(st.sampled_from([0, -1, math.nan, math.inf]), st.integers(-10000, 10000))
def test_invalid_grid_inputs_fail_before_iteration(spacing, limit):
    with pytest.raises(ValueError):
        list(candidate_grid((0, 0, 1, 1), spacing, limit))


@settings(max_examples=budget(1000))
@given(st.floats(0, 100000), st.floats(0, 1000), st.floats(0, 1000), st.floats(0, 1000))
def test_municipal_breakdown_reconciles_to_saved_plan(amount, capsule, delivery, maintenance):
    scenario = get_scenario("lower-piura-sechura")
    req = PlanRequest(scenario_id=scenario["summary"]["scenario_id"], dataset_version=scenario["summary"]["dataset_version"],
                      budget_pen=amount, assumptions={"capsule_cost_pen": capsule, "delivery_cost_per_ha_pen": delivery,
                                                      "maintenance_cost_per_ha_pen": maintenance})
    plan = build_plan(req)
    sections, tables = municipal_content(plan, resolve_dataset(req))
    assert sum(r["amount_cents"] for r in tables["budget_items"]) == plan.budget.total_cost_cents
    assert all(r["amount_cents"] >= 0 for r in tables["budget_items"])
    assert sum(r["capsules"] for r in tables["resources"]) == plan.budget.totals["capsules"]
    assert sum(r["seeds"] for r in tables["resources"]) == plan.budget.totals["seeds_released"]
    assert tables["coverage"][0]["ha"] >= tables["coverage"][1]["ha"] >= tables["coverage"][2]["ha"] >= 0
    assert "not official tariffs" in sections["budget_method"][0].text
    assert {r["source_id"] for r in tables["plant_benefits"]} <= {r["id"] for r in tables["sources"]}


@settings(max_examples=budget(1000))
@given(st.floats(-81.32, -79.22), st.floats(-6.37, -4.08))
def test_old_department_extent_cannot_bypass_screening_windows(lon, lat):
    g = box(lon, lat, lon+.001, lat+.001)
    if screening_scope("lower-piura-sechura").covers(g):
        return
    with pytest.raises(ZoneError, match="outside"):
        build_zone_dataset("lower-piura-sechura", [{"geometry": mapping(g)}],
                           terrain_fn=lambda _g: pytest.fail("Out-of-scope input reached DEM I/O"),
                           infra_fn=lambda _g: pytest.fail("Out-of-scope input reached infrastructure I/O"))


def test_total_scope_is_small_disconnected_and_locators_are_inside():
    s = get_scenario("lower-piura-sechura")["summary"]
    from shapely.geometry import Point
    from raiz_sar.geo import geodesic_area_ha
    scope = screening_scope(s["scenario_id"])
    assert scope.geom_type == "MultiPolygon"
    assert geodesic_area_ha(scope) < 4000
    assert all(scope.covers(Point(f["lon"], f["lat"])) for f in s["focus_areas"])


@settings(max_examples=budget(1000))
@given(st.floats(-79.618, -79.6), st.floats(-5.388, -5.37), st.integers(0, 100000))
def test_infrastructure_cache_returns_detached_copies(monkeypatch, lon, lat, count):
    from raiz_sar import exclusions, osm_features, overture
    exclusions._cached_infrastructure.cache_clear()
    calls = []
    monkeypatch.setattr(exclusions, "source_enabled", lambda: True)
    monkeypatch.setattr(osm_features, "features", lambda *a: calls.append("osm") or {"transportation": [], "park": []})
    monkeypatch.setattr(overture, "buildings", lambda *a: calls.append("buildings") or [])
    geom = box(lon, lat, lon+.001, lat+.001)
    first = exclusions.zone_infrastructure(geom)
    first["counts"]["buildings"] = count+1
    second = exclusions.zone_infrastructure(geom)
    assert sorted(calls) == ["buildings", "osm"]
    assert second["status"] == "ok" and second["counts"]["buildings"] == 0


def test_preview_is_complete_without_queue_or_provider(monkeypatch):
    from fastapi.testclient import TestClient
    from raiz_sar import api
    client = TestClient(api.app)
    scenario = get_scenario("lower-piura-sechura")
    plan = client.post("/api/plans", json={"scenario_id": scenario["summary"]["scenario_id"], "dataset_version": scenario["summary"]["dataset_version"]}).json()
    monkeypatch.setattr(api, "_submit", lambda *a, **kw: pytest.fail("Deterministic preview submitted a job"))
    response = client.post("/api/reports/preview", json={"plan_version": plan["plan_version"]})
    assert response.status_code == 200
    draft = response.json()
    assert draft["plan_version"] == plan["plan_version"] and draft["ai_status"] == "not_generated"
    assert {"coverage", "budget_items", "resources", "implementation", "risk_register", "sources"} <= draft["tables"].keys()
    assert client.post("/api/reports/preview", json={"plan_version": "deadbeef"}).status_code == 404
