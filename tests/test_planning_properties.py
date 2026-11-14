"""Contract-derived properties for eligibility, budget allocation and establishment scenarios."""

from __future__ import annotations

import math

from hypothesis import given, settings
from hypothesis import strategies as st

from conftest import budget
from raiz_sar.planning import allocate, cents, establishment_scenarios, evaluate_eligibility
from strategies import plan_requests, sector_features

ALLOWED = {"tara", "molle-costero"}


@st.composite
def dataset_and_request(draw):
    feats = draw(sector_features())
    req = draw(plan_requests([f["properties"]["sector_id"] for f in feats]))
    return feats, req


def run(feats, req):
    elig = evaluate_eligibility(feats, ALLOWED, req)
    return elig, allocate(feats, elig, req)


@settings(max_examples=budget(3000))
@given(dataset_and_request())
def test_budget_and_quantity_invariants(data):
    feats, req = data
    elig, b = run(feats, req)
    a = req.assumptions
    status = {e.sector_id: e.status for e in elig}
    # Every sector is evaluated exactly once.
    assert sorted(status) == sorted(f["properties"]["sector_id"] for f in feats)
    for x in b.allocations:
        # Non-negative integer quantities; seeds/capsules/germinated/established stay distinct.
        assert min(x.capsules, x.seeds_released, x.expected_germinated, x.expected_established) >= 0
        assert x.seeds_released == x.capsules * a.seeds_per_capsule
        assert x.expected_established <= x.expected_germinated <= x.seeds_released
        assert x.total_cost_cents == x.capsule_cost_cents + x.area_cost_cents >= 0
        assert 0.0 <= x.funded_fraction <= 1.0
        # Exclusion and unknown-evidence preservation: only eligible sectors receive anything.
        if status[x.sector_id] != "eligible":
            assert x.capsules == 0 and x.total_cost_cents == 0
    funded = sum(x.total_cost_cents for x in b.allocations)
    if funded:
        assert b.total_cost_cents == funded + b.monitoring_fixed_cost_cents
    if req.mode == "budget":
        assert b.total_cost_cents <= cents(req.budget_pen) or funded == 0
        if funded:
            assert b.remaining_cents >= 0
    assert b.totals["expected_established"] == sum(x.expected_established for x in b.allocations)
    assert b.feasible == (b.infeasibility_reason is None)


@settings(max_examples=budget(1500))
@given(dataset_and_request(), st.floats(0, 200_000, allow_nan=False))
def test_more_budget_never_reduces_planting(data, extra):
    """Metamorphic: raising the budget cannot lower any sector's capsules (greedy priority fill)."""
    feats, req = data
    if req.mode != "budget":
        return
    _, b1 = run(feats, req)
    req2 = req.model_copy(update={"budget_pen": req.budget_pen + extra})
    _, b2 = run(feats, req2)
    c1 = {x.sector_id: x.capsules for x in b1.allocations}
    c2 = {x.sector_id: x.capsules for x in b2.allocations}
    for sid in c1:
        assert c2[sid] >= c1[sid]


@settings(max_examples=budget(1500))
@given(dataset_and_request())
def test_target_mode_meets_target_or_reports_infeasible(data):
    feats, req = data
    if req.mode != "target":
        return
    _, b = run(feats, req)
    got = b.totals["expected_established"]
    if b.feasible:
        assert got >= req.target_established_plants
    else:
        assert b.infeasibility_reason


@settings(max_examples=budget(1500))
@given(dataset_and_request())
def test_establishment_scenarios_are_monotone_and_ordered(data):
    feats, req = data
    _, b = run(feats, req)
    es = establishment_scenarios(req, b)
    pts = es.points
    assert [p.delay_days for p in pts] == sorted(req.delay_days)
    if req.establishment_half_life_days is None:
        # Unknown stays unknown: no number is invented.
        assert es.status == "not_estimated"
        assert all(p.low is None and p.central is None and p.high is None for p in pts)
        return
    base = b.totals["expected_established"]
    for p in pts:
        assert 0 <= p.low <= p.central <= p.high <= base
    for p, q in zip(pts, pts[1:]):
        assert q.low <= p.low and q.central <= p.central and q.high <= p.high


@settings(max_examples=budget(2000))
@given(st.floats(0, 1e9, allow_nan=False))
def test_cents_conversion_is_exact_to_half_a_cent(pen):
    assert abs(cents(pen) / 100 - pen) <= 0.005 + 1e-9 * pen


def test_zero_budget_is_infeasible_without_spending():
    from raiz_sar.contracts import PlanRequest
    from raiz_sar.scenarios import get_scenario

    feats = get_scenario("carabayllo-rio-seco")["sectors"]["features"]
    req = PlanRequest(scenario_id="carabayllo-rio-seco", dataset_version="x", budget_pen=0)
    _, b = run(feats, req)
    assert not b.feasible and b.total_cost_cents == 0 and b.totals["capsules"] == 0


def test_nonfinite_budget_rejected():
    import pytest
    from pydantic import ValidationError

    from raiz_sar.contracts import PlanRequest

    for bad in (math.nan, math.inf, -1):
        with pytest.raises(ValidationError):
            PlanRequest(scenario_id="x", dataset_version="x", budget_pen=bad)
