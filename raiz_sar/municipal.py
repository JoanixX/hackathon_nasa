"""Reproducible municipal-review content. Rates are assumptions, never official tariffs."""
from __future__ import annotations

from collections import defaultdict

from shapely.geometry import shape
from shapely.ops import unary_union

from .contracts import ReportStatement
from .drone import funded_geometry
from .geo import geodesic_area_ha, to_metric, to_wgs84
from .scenarios import SPECIES_BY_ID, SPECIES_MAX_CROWN_RADIUS_M

SOURCES = [
    {"id": "osce-040-2021", "publisher": "OSCE", "document": "Opinion 040-2021/DTN, sections 2.1.2–2.1.3 (2021)",
     "url": "https://cdn.www.gob.pe/uploads/document/file/1823405/Opini%C3%B3n%20040-2021%20-%20CONSORCIO%20INTEG.VIAL%20-%20Valorizaci%C3%B3n%20de%20Mayores%20Metrados.pdf.pdf?v=1619026108",
     "use": "Historical official source for quantity × unit-price arithmetic; not current procurement-law advice or a tariff."},
    {"id": "serfor-algarrobo-2025", "publisher": "SERFOR", "document": "Plus-tree identification guide for Neltuma pallida (2025), printed page 10 / PDF page 12",
     "url": "https://repositorio.serfor.gob.pe/bitstream/SERFOR/977/3/SERFOR%202025%20Guia%20de%20Arboles%20Plus.pdf",
     "use": "Qualitative dry-forest livelihoods and ecosystem services; no site-specific yield or value."},
    {"id": "serfor-sapote-2019", "publisher": "SERFOR", "document": "Sapote (2019)",
     "url": "https://repositorio.serfor.gob.pe/handle/SERFOR/558",
     "use": "Multiple uses and conservation concern; specialist taxonomy and collection permission required."},
    {"id": "serfor-seeds-2024", "publisher": "SERFOR", "document": "Piura dry-forest seed collection (2024)",
     "url": "https://www.gob.pe/institucion/serfor/noticias/926693-piura-serfor-promueve-recoleccion-de-semillas-en-bosque-seco-del-campus-de-la-universidad-de-piura",
     "use": "Local occurrence and seed-source context, not Andean planting suitability."},
    {"id": "fao-bioengineering", "publisher": "FAO", "document": "Soil bioengineering techniques in watershed management",
     "url": "https://www.fao.org/4/x0622e/x0622e0s.htm",
     "use": "Technique- and site-dependent surface-erosion/shallow-slope contribution; no universal debris-flow protection."},
    {"id": "igp-faique-2021", "publisher": "IGP", "document": "Geodynamic inspection, San Miguel de El Faique (2021)",
     "url": "https://repositorio.igp.gob.pe/items/283d1986-01da-4da1-82da-18360781a4a8",
     "use": "Settlement/ravine context; screening boxes are not extracted official hazard polygons."},
    {"id": "ingemmet-canchaque", "publisher": "INGEMMET", "document": "Canchaque debris-flow reactivation warning (2021)",
     "url": "https://www.gob.pe/institucion/ingemmet/noticias/511383-piura-deslizamiento-en-canchaque-podria-reactivarse-ante-presencia-de-lluvias-intensas",
     "use": "Historical local hazard context, not a current warning or site clearance."},
]

BENEFITS = {
    "algarrobo": ("Potential pod products, forage and honey value chains where locally suitable and legally permitted; no revenue forecast.",
                   "Potential erosion moderation, soil-fertility and pollination services in a suitable dry-forest ecosystem.", "serfor-algarrobo-2025"),
    "sapote": ("Multipurpose dry-forest resource; any commercial use requires a conservation and legal review.",
                "Potential native habitat restoration where suitable. Conservation concern makes seed provenance and specialist review essential.", "serfor-sapote-2019"),
    "faique": ("Local nursery, seed-supply and maintenance work are potential project activities; income and markets are not estimated.",
                "Dry-forest native-cover candidate. Local occurrence is documented; erosion reduction, water demand and Andean suitability remain unmeasured.", "serfor-seeds-2024"),
}

IMPLEMENTATION = [
    ("Municipal sponsor / landholders", "Confirm residential adjacency, tenure and consent; acquire official hazard and cadastral layers. Reject active channels, runout zones and disputed land."),
    ("Geotechnical and hydrology specialists", "Survey slope, drainage, soils and infrastructure at adequate scale. Define setbacks and structural/drainage measures; stop if planting is inappropriate."),
    ("Ecologist / forestry authority", "Verify taxonomy, altitude, climate, native range, water availability, conservation rules and seed provenance. Approve or replace each candidate; dry-forest trees are not assumed suitable in the Andes."),
    ("GIS analyst", "Draw/import surveyed polygons inside a selected window. Confirm DEM/infrastructure analysis; record coverage, dates, missing data and exclusions. Missing mapping is not clearance."),
    ("Remote-sensing specialist", "Run compatible local NISAR L-SAR GCOV analysis with valid HH and available HV, acquisition dates, optical-reference and rainfall checks. Inspect coverage and uncertainty; retain evidence run and geometry versions."),
    ("Cost engineer / procurement team", "Replace illustrative rates with dated local quotations and resource-based unit-price analyses. Include surveys, seed preparation, labor, equipment, water, maintenance, permits, overhead, taxes and contingency where applicable."),
    ("Project engineer", "Set density, germination/establishment assumptions, budget and operational limits. Generate the versioned plan; review funded area, exclusions and candidate route feasibility. A capsule is not an established plant."),
    ("Licensed operator / field crew", "Obtain permissions and survey obstacles, launch sites, wind and battery reserve. Conduct a small release/calibration pilot; use manual planting if release accuracy or ecological suitability fails. No flight is authorized by this report."),
    ("Field supervisor", "Prepare approved microsites without destabilizing slopes; deposit documented seed/capsule batches in the approved season and maintain agreed clearance. Record actual quantities, weather and deviations."),
    ("Maintenance and monitoring team", "Maintain/protect sites and monitor fixed plots at baseline and 3, 6 and 12 months, then annually as agreed. Measure germination, survival, cover, soil loss and water use separately; stop and redesign if erosion, mortality or damage increases."),
    ("Municipal technical reviewer", "Reconcile as-built quantities and costs, attach surveys, quotations, permits and monitoring records. Review ecological, financial and operational feasibility before approving any technical dossier."),
]

RISKS = [
    ("Channelized debris flow / unstable slope", "Potentially severe; probability not estimated", "Geotechnical lead", "Exclude channels/runout; site assessment and complementary engineering; stop on instability."),
    ("Delayed roots / establishment failure", "Benefit may be absent or delayed", "Ecologist", "Pilot, seed-lot tests and maintenance; never assume immediate stabilization."),
    ("Unsuitable dry-forest species at elevation", "Suitability unresolved", "Forestry specialist", "Validate altitude, climate, soil and taxonomy; replace or reject candidates before procurement."),
    ("Drought, pests, fire, grazing and invasive behavior", "Local exposure unknown", "Maintenance lead", "Water plan, appropriate native stock, site protection and monitoring; quantify inputs locally."),
    ("Missing buildings / roads / drainage", "Incomplete source coverage", "GIS and field team", "Ground survey and full mature-crown clearance; unknown ground is not cleared."),
    ("SAR misclassification / coarse DSM", "Scale and uncertainty limits", "Remote-sensing lead", "Check acquisition coverage, calibration and independent reference; no water depth or root stability inference."),
    ("Aircraft release / obstacles / wind", "No aviation acceptance", "Licensed operator", "Permits, obstacle survey, test release and phase-split routes; manual alternative."),
    ("Budget gaps / maintenance underfunding", "Estimate incomplete until quoted", "Cost engineer", "Price all unpriced resources; approve recurring funding and applicable overhead/tax treatment."),
    ("Tenure / conservation / community conflict", "Permissions unverified", "Municipal sponsor", "Document consent, legal seed supply and specialist conservation review before field work."),
]


def municipal_content(plan, dataset):
    """Return sections/tables whose figures reconcile to the saved plan; no external I/O."""
    allocations = {a.sector_id: a for a in plan.budget.allocations}
    eligible = {e.sector_id for e in plan.eligibility if e.status == "eligible"}
    crs = dataset["summary"]["metric_crs"]
    assessed, possible, funded = [], [], []
    resources = defaultdict(lambda: {"capsules": 0, "seeds": 0, "modeled_germinated": 0, "modeled_established": 0})
    for f in dataset["sectors"]["features"]:
        g = shape(f["geometry"]); sid = f["properties"]["sector_id"]
        assessed.append(g)
        if sid in eligible:
            possible.append(g)
        a = allocations.get(sid)
        if a and a.capsules:
            funded.append(to_wgs84(funded_geometry(to_metric(g, crs), a.funded_fraction), crs))
            r = resources[a.species_id]
            for key, value in [("capsules", a.capsules), ("seeds", a.seeds_released),
                               ("modeled_germinated", a.expected_germinated), ("modeled_established", a.expected_established)]:
                r[key] += value
    coverage = []
    for label, geometries in [("Total assessed footprint", assessed), ("Eligible footprint before funding", possible),
                               ("Gross funded candidate footprint", funded)]:
        area = geodesic_area_ha(unary_union(geometries)) if geometries else 0.0
        coverage.append({"measure": label, "ha": round(area, 6), "m2": round(area * 10000, 2),
                         "basis": "Geodesic union; overlaps counted once. Proposed footprint, not demonstrated protection."})
    from .exclusions import exclusion_metric
    exclusions = []
    for f in dataset["sectors"]["features"]:
        blocked = exclusion_metric(f, crs)
        if blocked is not None:
            exclusions.append(to_wgs84(blocked.buffer(SPECIES_MAX_CROWN_RADIUS_M), crs))
        if f["properties"].get("exclusion_reason"):
            exclusions.append(to_wgs84(to_metric(shape(f["geometry"]), crs).buffer(plan.request.drone.no_go_buffer_m), crs))
    net = unary_union(funded).difference(unary_union(exclusions)) if funded else unary_union([])
    net_ha = geodesic_area_ha(net) if not net.is_empty else 0
    coverage.append({"measure": "Net funded core after recorded exclusions", "ha": round(net_ha, 6), "m2": round(net_ha*10000, 2),
                     "basis": "Stored infrastructure/mature-crown and no-go clearances; mapping is incomplete, field clearance still required. Budget uses gross funded area."})
    a = plan.request.assumptions
    capsule = sum(x.capsule_cost_cents for x in allocations.values())
    area_cost = sum(x.area_cost_cents for x in allocations.values())
    rate = a.delivery_cost_per_ha_pen + a.maintenance_cost_per_ha_pen
    delivery = round(area_cost * a.delivery_cost_per_ha_pen / rate) if rate else 0
    monitoring = plan.budget.total_cost_cents - capsule - area_cost
    funded_ha = sum(x.funded_area_ha for x in allocations.values())
    budget = []
    for item, qty, unit, price, cents in [
        ("Seed capsules", plan.budget.totals["capsules"], "capsule", a.capsule_cost_pen, capsule),
        ("Delivery", funded_ha, "funded ha", a.delivery_cost_per_ha_pen, delivery),
        ("Maintenance", funded_ha, "funded ha", a.maintenance_cost_per_ha_pen, area_cost - delivery),
        ("Monitoring", int(monitoring > 0), "package", a.monitoring_fixed_cost_pen, monitoring),
    ]:
        budget.append({"item": item, "quantity": qty, "unit": unit, "unit_price_pen": price, "amount_cents": cents,
                       "amount_pen": cents / 100, "rate_status": a.evidence_class, "source": "User assumptions; replace with dated local quotations"})
    benefits = []
    for sid in sorted(resources):
        econ, env, source = BENEFITS.get(sid, ("Not estimated; specialist review required.", "Not estimated; specialist review required.", "fao-bioengineering"))
        benefits.append({"species": SPECIES_BY_ID[sid].common_name, "economic_potential": econ, "environmental_potential": env,
                         "huaico_contribution": "Potential surface-erosion/shallow-slope contribution only after establishment and site validation; no quantified protection.",
                         "source_id": source, "monetary_benefit_pen": "Not estimated", "suitability": "Unreviewed; ecological and geotechnical approval required"})
    sections = {
        "budget_method": [ReportStatement(authorship="modeled", source_ids=["osce-040-2021", f"plan:{plan.plan_version}"], text=
            "Direct-cost structure: C = Σ(quantity_i × unit_price_i). Model: capsules × capsule rate + prorated funded-area delivery/maintenance + applied monitoring. "
            "The allocator rounds unit capsule prices to cents, full-area costs to cents, then rounds each funded-area fraction upward to a cent. "
            "Delivery and maintenance split that saved area cost proportionally, with the residual assigned to maintenance, so the breakdown reconciles exactly. "
            "Displayed hectares are rounded. OSCE Opinion 040-2021 is a historical arithmetic reference, not a statement of current procurement requirements. "
            "Rates are user assumptions, not official tariffs. Total shown is the modeled priced scope; a complete investment budget requires the unpriced items, applicable overhead, profit, taxes and contingency to be established by the cost engineer.")],
        "benefit_method": [ReportStatement(authorship="human_entered", source_ids=["fao-bioengineering", "serfor-algarrobo-2025"], text=
            "Benefits are qualitative opportunities conditional on ecology, land rights, maintenance and time. No avoided-loss, carbon-credit, revenue, NPV, protected-household or sediment-reduction value is estimated. "
            "A municipal appraisal needs a counterfactual, verified beneficiary inventory, measured change, valuation method and sensitivity analysis before monetization.")],
        "reproducibility": [ReportStatement(authorship="modeled", source_ids=[f"plan:{plan.plan_version}", f"dataset:{plan.dataset_version}"], text=
            f"Plan {plan.plan_version}; dataset {plan.dataset_version}; deposition engine plan-engine-2; evidence mode {plan.request.evidence_mode}; "
            f"NISAR run {plan.request.nisar_run_id or 'not linked'}; reference date {plan.request.reference_date}. Preserve the saved request, geometry, assumptions, source acquisitions and artifacts. "
            "Generated future scenes remain scenarios, not observed or validated futures. AI narrative is optional and does not change numeric quantities.")],
    }
    tables = {
        "coverage": coverage, "budget_items": budget,
        "resources": [{"species": SPECIES_BY_ID[sid].common_name, **r} for sid, r in sorted(resources.items())],
        "plant_benefits": benefits,
        "implementation": [{"step": i, "responsible": who, "action_and_gate": action} for i, (who, action) in enumerate(IMPLEMENTATION, 1)],
        "risk_register": [{"risk": r, "severity_or_uncertainty": s, "owner": o, "control": c} for r, s, o, c in RISKS],
        "unpriced_resources": [{"resource": r, "quantity": "Site-specific survey required", "cost_pen": "Not priced"} for r in
            ["Topographic/geotechnical/ecological surveys and professional review", "Legal seed sourcing, preparation and viability tests",
             "Labor, training, PPE, mobilization and equipment", "Water supply/irrigation, pest/fire/grazing protection and replacement stock",
             "Aviation/land/conservation permissions and community agreements", "Independent monitoring, recurring maintenance and contingency",
             "Applicable overhead, profit and tax treatment (confirm inclusions to avoid double counting)"]],
        "sources": [{**s, "checked_on": "2026-11-16"} for s in SOURCES],
    }
    return sections, tables
