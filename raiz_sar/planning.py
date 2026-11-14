"""Eligibility-first planting allocation, seed/plant quantities and establishment scenarios.

All money is computed in integer centimos (PEN cents) to avoid rounding drift. Seeds/capsules,
expected germination and expected established plants are kept separate. Outputs are modeled
scenarios under user-entered assumptions; they are not survival predictions.
"""

from __future__ import annotations

import datetime as dt
import math
from typing import Any

from .contracts import (
    BudgetScenario,
    EstablishmentPoint,
    EstablishmentScenario,
    EvidenceClass,
    PlanningAssumptions,
    PlanRequest,
    SectorAllocation,
    SectorEligibility,
)

OBJECTIVE = (
    "Deterministic priority fill: eligible sectors are funded in order of steeper known slope within the "
    "planning limit (an erosion-exposure planning heuristic, not a validated benefit objective). "
    "Excluded and unknown-evidence sectors receive nothing."
)


def cents(pen: float) -> int:
    if not math.isfinite(pen) or pen < 0:
        raise ValueError("amount must be finite and non-negative")
    return int(round(pen * 100))


def _prop_value(props: dict[str, Any], key: str) -> float | None:
    q = props.get(key) or {}
    v = q.get("value") if isinstance(q, dict) else None
    return float(v) if isinstance(v, (int, float)) and math.isfinite(v) else None


def evaluate_eligibility(
    features: list[dict[str, Any]],
    allowed_species: set[str],
    request: PlanRequest,
) -> list[SectorEligibility]:
    out: list[SectorEligibility] = []
    selected = set(request.selected_sector_ids) if request.selected_sector_ids is not None else None
    max_slope = request.assumptions.max_slope_percent
    for f in features:
        p = f["properties"]
        sid = p["sector_id"]
        reasons: list[str] = []
        species = request.species_by_sector.get(sid) or p.get("species_candidate")
        if p.get("exclusion_reason"):
            out.append(SectorEligibility(sector_id=sid, status="excluded", reasons=[p["exclusion_reason"]]))
            continue
        slope = _prop_value(p, "slope_percent")
        area = _prop_value(p, "area_ha")
        if slope is not None and slope > max_slope:
            out.append(SectorEligibility(sector_id=sid, status="excluded",
                                         reasons=[f"Slope {slope:g}% exceeds the planning limit of {max_slope:g}%."]))
            continue
        if selected is not None and sid not in selected:
            out.append(SectorEligibility(sector_id=sid, status="not_selected", reasons=["Not selected by the user."]))
            continue
        if slope is None:
            reasons.append("Slope unknown: field assessment required before allocation.")
        if area is None or area <= 0:
            reasons.append("Area unknown or zero.")
        if not species:
            reasons.append("No candidate species assigned.")
        elif species not in allowed_species:
            reasons.append(f"Species '{species}' is not an allowed candidate for this scenario.")
        if reasons:
            out.append(SectorEligibility(sector_id=sid, status="field_assessment_required", reasons=reasons))
        else:
            out.append(SectorEligibility(sector_id=sid, status="eligible",
                                         reasons=["Candidate planting sector; field assessment still required."]))
    return out


def _sector_full_need(area_ha: float, a: PlanningAssumptions) -> tuple[int, int, int, int]:
    """Return (target established, seeds needed, capsules, area cost cents) for full funding."""
    target = int(math.floor(area_ha * a.target_density_plants_per_ha + 1e-9))
    yield_per_seed = a.germination_fraction * a.establishment_fraction
    seeds = int(math.ceil(target / yield_per_seed - 1e-9)) if target > 0 else 0
    capsules = int(math.ceil(seeds / a.seeds_per_capsule)) if seeds > 0 else 0
    area_cost = cents(area_ha * (a.delivery_cost_per_ha_pen + a.maintenance_cost_per_ha_pen))
    return target, seeds, capsules, area_cost


def _cost_for(k: int, full_k: int, capsule_cents: int, area_cents_full: int) -> tuple[int, int]:
    if full_k == 0 or k == 0:
        return 0, 0
    area = -(-area_cents_full * k // full_k)  # ceil division: prorated area cost never under-charges
    return k * capsule_cents, area


def _max_capsules_within(remaining: int, full_k: int, capsule_cents: int, area_cents_full: int) -> int:
    lo, hi = 0, full_k
    while lo < hi:
        mid = (lo + hi + 1) // 2
        c, ar = _cost_for(mid, full_k, capsule_cents, area_cents_full)
        if c + ar <= remaining:
            lo = mid
        else:
            hi = mid - 1
    return lo


def _expected(capsules: int, a: PlanningAssumptions) -> tuple[int, int, int]:
    seeds = capsules * a.seeds_per_capsule
    germ = int(math.floor(seeds * a.germination_fraction + 1e-9))
    est = int(math.floor(germ * a.establishment_fraction + 1e-9))
    return seeds, min(germ, seeds), min(est, germ)


def allocate(
    features: list[dict[str, Any]],
    eligibility: list[SectorEligibility],
    request: PlanRequest,
) -> BudgetScenario:
    a = request.assumptions
    by_id = {f["properties"]["sector_id"]: f for f in features}
    eligible = [e.sector_id for e in eligibility if e.status == "eligible"]
    # Priority: steeper known slope first, then larger area, then id for determinism.
    def key(sid: str):
        p = by_id[sid]["properties"]
        return (-(_prop_value(p, "slope_percent") or 0.0), -(_prop_value(p, "area_ha") or 0.0), sid)

    order = sorted(eligible, key=key)
    capsule_cents = cents(a.capsule_cost_pen)
    monitoring = cents(a.monitoring_fixed_cost_pen)
    budget = cents(request.budget_pen) if request.mode == "budget" and request.budget_pen is not None else None
    remaining_target = request.target_established_plants if request.mode == "target" else None

    allocations: list[SectorAllocation] = []
    infeasible: str | None = None
    if not order:
        infeasible = "No eligible sectors: resolve exclusions or field-assessment requirements first."
    remaining = None
    if budget is not None:
        if budget < monitoring:
            infeasible = infeasible or "Budget does not cover the fixed monitoring cost."
            remaining = 0
        else:
            remaining = budget - monitoring

    rank = 0
    for sid in order:
        p = by_id[sid]["properties"]
        area = _prop_value(p, "area_ha") or 0.0
        species = request.species_by_sector.get(sid) or p.get("species_candidate")
        target, _seeds, full_k, area_cents = _sector_full_need(area, a)
        k = full_k
        if remaining_target is not None:
            # Target mode: fund just enough capsules for the remaining established-plant target.
            if remaining_target <= 0:
                k = 0
            else:
                need = int(math.ceil(remaining_target / (a.germination_fraction * a.establishment_fraction) - 1e-9))
                k = min(full_k, int(math.ceil(need / a.seeds_per_capsule)))
                while k > 0 and _expected(k - 1, a)[2] >= remaining_target:
                    k -= 1
                while k < full_k and _expected(k, a)[2] < remaining_target:
                    k += 1
        if remaining is not None:
            k = min(k, _max_capsules_within(remaining, full_k, capsule_cents, area_cents))
        c_cost, a_cost = _cost_for(k, full_k, capsule_cents, area_cents)
        seeds, germ, est = _expected(k, a)
        frac = (k / full_k) if full_k else 0.0
        rank += 1
        allocations.append(SectorAllocation(
            sector_id=sid, species_id=species, priority_rank=rank, area_ha=area,
            funded_area_ha=round(area * frac, 6), target_established_plants=target, capsules=k,
            seeds_released=seeds, expected_germinated=germ, expected_established=est,
            capsule_cost_cents=c_cost, area_cost_cents=a_cost, total_cost_cents=c_cost + a_cost,
            funded_fraction=round(frac, 6),
        ))
        if remaining is not None:
            remaining -= c_cost + a_cost
        if remaining_target is not None:
            remaining_target -= est

    for e in eligibility:
        if e.status != "eligible":
            p = by_id[e.sector_id]["properties"]
            allocations.append(SectorAllocation(
                sector_id=e.sector_id, species_id=None, priority_rank=None,
                area_ha=_prop_value(p, "area_ha") or 0.0, funded_area_ha=0.0, target_established_plants=0,
                capsules=0, seeds_released=0, expected_germinated=0, expected_established=0,
                capsule_cost_cents=0, area_cost_cents=0, total_cost_cents=0, funded_fraction=0.0,
            ))

    sector_cost = sum(x.total_cost_cents for x in allocations)
    funded_any = sector_cost > 0
    total = sector_cost + (monitoring if funded_any or request.mode == "target" else 0)
    if request.mode == "target" and remaining_target is not None and remaining_target > 0 and infeasible is None:
        infeasible = "Target exceeds the full planting capacity of eligible sectors at the chosen density."
    if budget is not None and infeasible is None and not funded_any:
        infeasible = "Budget covers monitoring but not a single capsule with its prorated area costs."
    totals = {
        "capsules": sum(x.capsules for x in allocations),
        "seeds_released": sum(x.seeds_released for x in allocations),
        "expected_germinated": sum(x.expected_germinated for x in allocations),
        "expected_established": sum(x.expected_established for x in allocations),
        "target_established_plants": sum(x.target_established_plants for x in allocations),
    }
    return BudgetScenario(
        mode=request.mode,
        budget_cents=budget,
        monitoring_fixed_cost_cents=monitoring,
        total_cost_cents=total,
        remaining_cents=(budget - total) if budget is not None else None,
        feasible=infeasible is None,
        infeasibility_reason=infeasible,
        objective=OBJECTIVE,
        allocations=allocations,
        totals=totals,
        evidence_class=EvidenceClass.modeled,
        note=(
            "Seeds released, expected germination and expected established plants use illustrative assumptions "
            "entered by the user. They are planning quantities, not predicted survival."
        ),
    )


def establishment_scenarios(request: PlanRequest, budget: BudgetScenario) -> EstablishmentScenario:
    ref = dt.date.fromisoformat(request.reference_date)
    delays = sorted(request.delay_days)
    base = budget.totals["expected_established"]
    meaning = "User-selected post-rainfall reference date; offsets are planning delays, not optimal dates."
    if request.establishment_half_life_days is None:
        points = [EstablishmentPoint(delay_days=d, planting_date=(ref + dt.timedelta(days=d)).isoformat(),
                                     low=None, central=None, high=None) for d in delays]
        return EstablishmentScenario(
            status="not_estimated", reference_date=ref.isoformat(), reference_date_meaning=meaning,
            half_life_days=None, model="none", points=points, evidence_class=EvidenceClass.unknown,
            note="Not estimated: enter an establishment half-life assumption to run a sensitivity scenario.",
        )
    h = request.establishment_half_life_days
    points = []
    for d in delays:
        vals = [int(math.floor(base * 0.5 ** (d / hl) + 1e-9)) for hl in (h * 0.5, h, h * 2.0)]
        points.append(EstablishmentPoint(delay_days=d, planting_date=(ref + dt.timedelta(days=d)).isoformat(),
                                         low=vals[0], central=vals[1], high=vals[2]))
    return EstablishmentScenario(
        status="sensitivity_scenario", reference_date=ref.isoformat(), reference_date_meaning=meaning,
        half_life_days=h,
        model="Exponential decay of the establishment multiplier with planting delay; bands use half-life ×0.5, ×1, ×2.",
        points=points, evidence_class=EvidenceClass.illustrative,
        note="Sensitivity scenario under a user-entered half-life. Not a survival probability or calibrated forecast.",
    )
