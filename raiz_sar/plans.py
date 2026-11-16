"""Builds the single versioned planting plan that drives map, budget, charts, report and AR."""

from __future__ import annotations

import datetime as dt
from typing import Any

from .contracts import PlanRequest, PlantingPlan, content_hash
from .drone import plan_deposition
from .planning import allocate, establishment_scenarios, evaluate_eligibility
from .scenarios import get_scenario, species_for


class PlanInputError(ValueError):
    pass


def resolve_dataset(request: PlanRequest) -> dict[str, Any]:
    """Return the sector dataset (fixture or imported) that the request is versioned against."""
    try:
        scenario = get_scenario(request.scenario_id)
    except KeyError as exc:
        raise PlanInputError(f"Unknown scenario '{request.scenario_id}'.") from exc
    summary = dict(scenario["summary"])
    sectors = scenario["sectors"]
    if request.imported_sectors is not None:
        imported = request.imported_sectors
        if imported.get("scenario_id") != request.scenario_id:
            raise PlanInputError("Imported sectors belong to a different scenario.")
        sectors = imported["sectors"]
        summary["dataset_version"] = imported["dataset_version"]
        summary["data_mode"] = imported.get("data_mode", "real")
        if content_hash({"sectors": sectors}) != imported.get("content_hash"):
            raise PlanInputError("Imported sector dataset failed its integrity check; import it again.")
    if summary["dataset_version"] != request.dataset_version:
        raise PlanInputError("Stale dataset version: reload the scenario before planning.")
    return {"summary": summary, "sectors": sectors}


def load_nisar_evidence(request: PlanRequest, features: list[dict[str, Any]]) -> dict[str, Any]:
    """Load the referenced NISAR evidence and check it was computed for exactly these zone geometries."""
    import json

    from .config import get_settings

    path = get_settings().artifact_dir / "nisar_water" / str(request.nisar_run_id) / "evidence.json"
    try:
        ev = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PlanInputError("The referenced NISAR evidence was not found; run the NISAR water analysis again.") from exc
    by_sid = {f["properties"]["sector_id"]: f for f in features}
    zones = {}
    for z in ev.get("zones", []):
        f = by_sid.get(z.get("sector_id"))
        if f is None:
            continue
        if content_hash(z.get("geometry_hash_basis")) != content_hash(f["geometry"]):
            raise PlanInputError(f"NISAR evidence for {z['sector_id']} was computed for a different boundary; run it again.")
        zones[z["sector_id"]] = z
    return {"run_id": ev["run_id"], "event_date": ev["event"]["date"], "zones": zones, "evidence_version": ev["evidence_version"]}


def build_plan(request: PlanRequest) -> PlantingPlan:
    ds = resolve_dataset(request)
    features = ds["sectors"]["features"]
    ids = [f["properties"]["sector_id"] for f in features]
    if len(set(ids)) != len(ids):
        raise PlanInputError("Duplicate sector identifiers in dataset.")
    unknown_ids = set(request.species_by_sector) - set(ids)
    if unknown_ids:
        raise PlanInputError(f"Species assigned to unknown sectors: {sorted(unknown_ids)}.")
    if request.selected_sector_ids is not None and set(request.selected_sector_ids) - set(ids):
        raise PlanInputError("Selection contains unknown sectors.")
    allowed = {s.species_id for s in species_for(request.scenario_id)}
    nisar = load_nisar_evidence(request, features) if request.evidence_mode == "nisar" else None
    eligibility = evaluate_eligibility(features, allowed, request, nisar)
    budget = allocate(features, eligibility, request)
    establishment = establishment_scenarios(request, budget)
    drone = plan_deposition(features, budget, request.drone, ds["summary"]["metric_crs"])
    version_basis = {"request": request.model_dump(mode="json"), "dataset_version": ds["summary"]["dataset_version"],
                     "engine": "plan-engine-1"}
    return PlantingPlan(
        plan_version=content_hash(version_basis),
        scenario_id=request.scenario_id,
        dataset_version=ds["summary"]["dataset_version"],
        request=request,
        eligibility=eligibility,
        budget=budget,
        establishment=establishment,
        drone=drone,
        created_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    )
