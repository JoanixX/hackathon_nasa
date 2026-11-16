"""Shared, versioned data contracts used by the API, workers, frontend and AR scene.

Every derived object carries the input versions it was computed from, its evidence class
and units. Unknown values stay ``None``; they never silently become zero or high confidence.
"""

from __future__ import annotations

import hashlib
import json
import math
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from . import SCHEMA_VERSION


class EvidenceClass(str, Enum):
    observed = "observed"
    derived = "derived"
    modeled = "modeled"
    ai_generated = "ai_generated"
    illustrative = "illustrative"
    unknown = "unknown"


class DataMode(str, Enum):
    real = "real"
    synthetic_fixture = "synthetic_fixture"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=False)


def canonical_json(obj: Any) -> str:
    """Stable JSON used for content hashes and version identifiers."""
    if isinstance(obj, BaseModel):
        obj = obj.model_dump(mode="json")
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def content_hash(obj: Any, length: int = 16) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()[:length]


class Quantity(StrictModel):
    """A value with unit and evidence class. ``value`` is ``None`` when unknown."""

    value: float | None = None
    unit: str
    evidence_class: EvidenceClass = EvidenceClass.unknown
    source: str | None = None
    note: str | None = None

    @field_validator("value")
    @classmethod
    def _finite(cls, v: float | None) -> float | None:
        if v is not None and not math.isfinite(v):
            raise ValueError("quantity value must be finite or null")
        return v

    @model_validator(mode="after")
    def _unknown_has_no_value(self) -> "Quantity":
        if self.value is None and self.evidence_class not in (EvidenceClass.unknown,):
            # A missing value cannot carry a stronger evidence class than unknown.
            self.evidence_class = EvidenceClass.unknown
        if self.value is not None and self.evidence_class == EvidenceClass.unknown:
            raise ValueError("a known value needs an explicit evidence class")
        return self


def unknown(unit: str, note: str | None = None) -> Quantity:
    return Quantity(value=None, unit=unit, evidence_class=EvidenceClass.unknown, note=note)


# --------------------------------------------------------------------------------------
# Study areas, sectors and species
# --------------------------------------------------------------------------------------


class SectorProperties(StrictModel):
    sector_id: str = Field(min_length=1, max_length=64)
    source_feature_id: str | None = None
    sector_name: str = Field(min_length=1, max_length=120)
    scenario_id: str
    data_mode: DataMode
    boundary_note: str
    area_ha: Quantity
    declared_area_ha: Quantity
    slope_percent: Quantity
    dielectric_er: Quantity
    sigma_hh_db: Quantity
    sigma_hv_db: Quantity
    gamma0_hh_db: Quantity
    gamma0_hv_db: Quantity
    rvi: Quantity
    species_candidate: str | None = None
    exclusion_reason: str | None = None
    field_assessment_status: Literal["required", "in_progress", "completed"] = "required"
    warnings: list[str] = Field(default_factory=list)


class SpeciesCandidate(StrictModel):
    species_id: str
    common_name: str
    supplied_taxon: str | None
    review_status: Literal["unreviewed_source_candidate", "specialist_reviewed", "rejected"]
    scenarios: list[str]
    asset_id: Literal["shrub_tree_small", "broad_tree", "dry_forest_tree", "umbrella_tree", "round_shrub_tree"]
    note: str
    water_need: Literal["low", "moderate", "unknown"] = "unknown"  # qualitative, pending specialist review
    model: dict[str, Any] = Field(default_factory=dict)  # 3D form parameters for the tree digital twin (illustrative)


class StudyAreaSummary(StrictModel):
    scenario_id: str
    name: str
    locator_lat: float
    locator_lon: float
    locator_note: str
    intervention_case: str
    hazard_mechanism_note: str
    metric_crs: str
    data_mode: DataMode
    dataset_version: str
    region_bbox: list[float] | None = None  # [west, south, east, north] where zones may be drawn
    region_boundary: str | None = None  # stored exact boundary (raiz_sar/boundaries/<name>.geojson); zones must lie inside it
    primary: bool = False
    listed: bool = True  # offered in the interface (owner decision 2026-11-15: Piura only)
    focus_areas: list[dict[str, Any]] = Field(default_factory=list)  # [{name, lon, lat, zoom}]


# --------------------------------------------------------------------------------------
# Planning
# --------------------------------------------------------------------------------------


class PlanningAssumptions(StrictModel):
    """User-editable assumptions. Defaults are illustrative placeholders, not specialist values."""

    target_density_plants_per_ha: float = Field(default=400.0, ge=0, le=20000)
    seeds_per_capsule: int = Field(default=3, ge=1, le=100)
    germination_fraction: float = Field(default=0.3, gt=0, le=1)
    establishment_fraction: float = Field(default=0.4, gt=0, le=1)
    capsule_cost_pen: float = Field(default=0.6, ge=0, le=1000)
    delivery_cost_per_ha_pen: float = Field(default=180.0, ge=0, le=1_000_000)
    maintenance_cost_per_ha_pen: float = Field(default=120.0, ge=0, le=1_000_000)
    monitoring_fixed_cost_pen: float = Field(default=1500.0, ge=0, le=10_000_000)
    max_slope_percent: float = Field(default=100.0, gt=0, le=1000)
    evidence_class: Literal["illustrative", "specialist_reviewed"] = "illustrative"


class DroneParameters(StrictModel):
    payload_capsules_per_sortie: int = Field(default=400, ge=1, le=100_000)
    max_route_m_per_sortie: float = Field(default=3000.0, gt=0, le=200_000)
    node_spacing_m: float = Field(default=25.0, ge=2, le=1000)
    no_go_buffer_m: float = Field(default=10.0, ge=0, le=1000)
    launch_lat: float | None = Field(default=None, ge=-90, le=90)
    launch_lon: float | None = Field(default=None, ge=-180, le=180)


class PlanRequest(StrictModel):
    scenario_id: str
    dataset_version: str
    mode: Literal["budget", "target"] = "budget"
    budget_pen: float | None = Field(default=25000.0, ge=0, le=1_000_000_000)
    target_established_plants: int | None = Field(default=None, ge=0, le=100_000_000)
    species_by_sector: dict[str, str] = Field(default_factory=dict)
    selected_sector_ids: list[str] | None = None
    assumptions: PlanningAssumptions = Field(default_factory=PlanningAssumptions)
    drone: DroneParameters = Field(default_factory=DroneParameters)
    reference_date: str = Field(default="2026-03-15", pattern=r"^\d{4}-\d{2}-\d{2}$")
    delay_days: list[int] = Field(default_factory=lambda: [0, 15, 30, 45, 60])
    establishment_half_life_days: float | None = Field(default=None, gt=0, le=3650)
    imported_sectors: dict[str, Any] | None = None
    # "nisar": candidate zones must carry NISAR-observed temporary water from the referenced evidence run.
    # "manual": explicitly labelled planning without NISAR evidence (demo / field-led).
    evidence_mode: Literal["nisar", "manual"] = "manual"
    nisar_run_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{16}$")

    @model_validator(mode="after")
    def _mode_inputs(self) -> "PlanRequest":
        if self.evidence_mode == "nisar" and not self.nisar_run_id:
            raise ValueError("NISAR-informed planning requires nisar_run_id (run the NISAR water evidence first)")
        if self.mode == "budget" and self.budget_pen is None:
            raise ValueError("budget mode requires budget_pen")
        if self.mode == "target" and self.target_established_plants is None:
            raise ValueError("target mode requires target_established_plants")
        if not self.delay_days or len(self.delay_days) > 12:
            raise ValueError("delay_days must contain 1 to 12 values")
        if any(d < 0 or d > 365 for d in self.delay_days):
            raise ValueError("delay_days must be within 0..365")
        if len(set(self.delay_days)) != len(self.delay_days):
            raise ValueError("delay_days must be unique")
        return self


class SectorEligibility(StrictModel):
    sector_id: str
    status: Literal["eligible", "excluded", "field_assessment_required", "not_selected"]
    reasons: list[str]


class SectorAllocation(StrictModel):
    sector_id: str
    species_id: str | None
    priority_rank: int | None
    area_ha: float
    funded_area_ha: float
    target_established_plants: int
    capsules: int
    seeds_released: int
    expected_germinated: int
    expected_established: int
    capsule_cost_cents: int
    area_cost_cents: int
    total_cost_cents: int
    funded_fraction: float


class BudgetScenario(StrictModel):
    mode: Literal["budget", "target"]
    budget_cents: int | None
    monitoring_fixed_cost_cents: int
    total_cost_cents: int
    remaining_cents: int | None
    feasible: bool
    infeasibility_reason: str | None
    objective: str
    allocations: list[SectorAllocation]
    totals: dict[str, int]
    evidence_class: EvidenceClass = EvidenceClass.modeled
    note: str


class EstablishmentPoint(StrictModel):
    delay_days: int
    planting_date: str
    low: int | None
    central: int | None
    high: int | None


class EstablishmentScenario(StrictModel):
    status: Literal["sensitivity_scenario", "not_estimated"]
    reference_date: str
    reference_date_meaning: str
    half_life_days: float | None
    model: str
    points: list[EstablishmentPoint]
    evidence_class: EvidenceClass
    note: str


class DepositionNode(StrictModel):
    node_id: str
    sector_id: str
    lat: float
    lon: float
    capsules: int
    sortie: int
    order: int


class DroneSortie(StrictModel):
    sortie: int
    capsules: int
    route_m: float
    node_ids: list[str]


class DroneSeedingPlan(StrictModel):
    status: Literal["candidate_plan_incomplete", "infeasible", "not_applicable"]
    purpose: str
    launch_lat: float | None
    launch_lon: float | None
    nodes: list[DepositionNode]
    sorties: list[DroneSortie]
    total_capsules: int
    unverified_constraints: list[str]
    infeasibility_reason: str | None
    execution: Literal["not_executed"] = "not_executed"
    note: str


class PlantingPlan(StrictModel):
    schema_version: str = SCHEMA_VERSION
    plan_version: str
    scenario_id: str
    dataset_version: str
    request: PlanRequest
    eligibility: list[SectorEligibility]
    budget: BudgetScenario
    establishment: EstablishmentScenario
    drone: DroneSeedingPlan
    created_at: str


# --------------------------------------------------------------------------------------
# AI output and future scene specification
# --------------------------------------------------------------------------------------

HORIZONS_MONTHS = (0, 3, 6, 12)
StageLabel = Literal["seed_deposition", "germination", "early_establishment", "establishment"]
Pattern = Literal["clustered", "scattered", "contour_rows"]

_SHORT = 160


class AIZone(StrictModel):
    sector_id: str = Field(min_length=1, max_length=64)
    species_id: str = Field(min_length=1, max_length=64)
    pattern: Pattern
    share_of_sector_plants: float = Field(ge=0, le=1)
    rationale: str = Field(max_length=240)


class AIStage(StrictModel):
    horizon_months: int
    stage_label: StageLabel
    visible_fraction_of_expected: float = Field(ge=0, le=1)
    max_height_m: float = Field(ge=0, le=20)
    canopy_radius_m: float = Field(ge=0, le=10)
    caption: str = Field(max_length=_SHORT)


class AIRootCutaway(StrictModel):
    show: bool
    caption: str = Field(max_length=_SHORT)


class AIScenePlan(StrictModel):
    """Exact structure requested from the model (schema-constrained generation)."""

    title: str = Field(min_length=1, max_length=80)
    zones: list[AIZone] = Field(min_length=1, max_length=40)
    stages: list[AIStage] = Field(min_length=4, max_length=4)
    root_cutaway: AIRootCutaway
    assumptions: list[str] = Field(min_length=1, max_length=8)
    uncertainty_note: str = Field(min_length=1, max_length=300)


class InferenceTrace(StrictModel):
    mode: Literal["actual_inference", "fixture"]
    provider: str
    model: str
    response_id: str | None
    prompt_hash: str
    latency_ms: int | None
    usage: dict[str, int] = Field(default_factory=dict)
    attempts: int
    note: str


class ARFrame(StrictModel):
    """Maps the AOI onto the printed image target (tabletop registration, not geolocation)."""

    registration: Literal["image_target_tabletop"] = "image_target_tabletop"
    target_id: str
    target_aspect: float  # height / width of the printed target
    metric_crs: str
    origin_x_m: float
    origin_y_m: float
    meters_per_ar_unit: float
    vertical_exaggeration: float
    terrain: str
    datum_note: str
    bbox_lonlat: list[float] | None = None  # [west, south, east, north] of the printed target's footprint


class ScenePlacement(StrictModel):
    sector_id: str
    species_id: str
    asset_id: str
    x: float
    y: float
    reveal_rank: float  # 0..1 ordering used to reveal placements per stage
    represents_plants: int
    lon: float | None = None
    lat: float | None = None


class SceneZone(StrictModel):
    sector_id: str
    sector_name: str
    eligibility: str
    outline: list[list[float]]  # tabletop coordinates [[x, y], ...]
    species_id: str | None
    pattern: str | None
    expected_established: int
    seeds_released: int


class SceneStage(StrictModel):
    horizon_months: int
    stage_label: StageLabel
    visible_fraction_of_expected: float
    max_height_m: float
    canopy_radius_m: float
    caption: str
    evidence_class: EvidenceClass = EvidenceClass.ai_generated


class FutureSceneSpecification(StrictModel):
    schema_version: str = SCHEMA_VERSION
    scene_version: str
    plan_version: str
    scenario_id: str
    title: str
    frame: ARFrame
    zones: list[SceneZone]
    placements: list[ScenePlacement]
    deposition_points: list[list[float]]
    stages: list[SceneStage]
    evidence_overlay: dict[str, Any] | None = None
    terrain_grid: dict[str, Any] | None = None  # DEM heights for the AR mesh (row 0 = north)
    root_cutaway: AIRootCutaway
    assumptions: list[str]
    uncertainty_note: str
    inference: InferenceTrace
    labels: dict[str, str]
    created_at: str


# --------------------------------------------------------------------------------------
# Planning draft (report)
# --------------------------------------------------------------------------------------


class AIReportSections(StrictModel):
    executive_summary: str = Field(min_length=1, max_length=1200)
    field_checks: list[str] = Field(min_length=1, max_length=10)
    monitoring_protocol: list[str] = Field(min_length=1, max_length=10)
    risks_and_limitations: list[str] = Field(min_length=1, max_length=10)


class ReportStatement(StrictModel):
    text: str
    authorship: Literal["human_entered", "measured", "derived", "modeled", "ai_generated", "illustrative"]
    source_ids: list[str] = Field(default_factory=list)


class PlanningDraft(StrictModel):
    schema_version: str = SCHEMA_VERSION
    report_version: str
    plan_version: str
    scene_version: str | None
    scenario_id: str
    title: str
    status_label: str
    sections: dict[str, list[ReportStatement]]
    tables: dict[str, list[dict[str, Any]]]
    ai_status: Literal["actual_inference", "fixture", "not_generated"]
    inference: InferenceTrace | None
    ai_error: str | None
    created_at: str


# --------------------------------------------------------------------------------------
# Jobs
# --------------------------------------------------------------------------------------

JobState = Literal["validating", "queued", "running", "ready", "partial", "failed", "cancelled"]
JobKind = Literal["scene", "report", "sar_process", "sar_discover", "ponding", "nisar_water"]


class JobStatus(StrictModel):
    job_id: str
    kind: JobKind
    state: JobState
    plan_version: str | None
    attempts: int
    created_at: str
    updated_at: str
    result_ref: str | None
    error_code: str | None
    error_message: str | None
