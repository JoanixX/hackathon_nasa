"""The two source-requested scenario locators with synthetic demonstration sectors.

Sector polygons are SYNTHETIC FIXTURES generated around the approximate locators supplied by
the solution source. They are not surveyed boundaries, hazard footprints or verified planting
sites. Slope values are illustrative placeholders. SAR-derived values are unknown until a GCOV
product is processed. Imported GIS sectors replace these through the GIS connector.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from shapely.geometry import Polygon

from .contracts import (
    DataMode,
    EvidenceClass,
    Quantity,
    SectorProperties,
    SpeciesCandidate,
    StudyAreaSummary,
    content_hash,
    unknown,
)
from .geo import geodesic_area_ha, geometry_to_geojson, lonlat_to_metric, to_wgs84

SYNTHETIC_BOUNDARY_NOTE = "Synthetic demonstration polygon near the source locator; not a surveyed boundary."

SPECIES: list[SpeciesCandidate] = [
    SpeciesCandidate(
        species_id="tara",
        common_name="Tara",
        supplied_taxon="Caesalpinia spinosa (as supplied)",
        review_status="unreviewed_source_candidate",
        scenarios=["carabayllo-rio-seco"],
        asset_id="shrub_tree_small",
        note="Source candidate. Accepted taxonomy, native range, seed suitability and density need specialist review.",
    ),
    SpeciesCandidate(
        species_id="molle-costero",
        common_name="Molle Costero",
        supplied_taxon="Schinus molle (as supplied)",
        review_status="unreviewed_source_candidate",
        scenarios=["carabayllo-rio-seco"],
        asset_id="broad_tree",
        note="Source candidate. Verify the supplied taxon and its local suitability before any prescription.",
    ),
    SpeciesCandidate(
        species_id="algarrobo",
        common_name="Algarrobo",
        supplied_taxon="Prosopis pallida (as supplied)",
        review_status="unreviewed_source_candidate",
        scenarios=["lower-piura-sechura"],
        asset_id="dry_forest_tree",
        note="Source candidate for dry-forest establishment. Verify taxonomy, conservation constraints and seed source.",
    ),
    SpeciesCandidate(
        species_id="sapote",
        common_name="Sapote",
        supplied_taxon=None,
        review_status="unreviewed_source_candidate",
        scenarios=["lower-piura-sechura"],
        asset_id="dry_forest_tree",
        note="Source candidate with unspecified taxon. A specialist must identify the taxon before use.",
    ),
]

SPECIES_BY_ID = {s.species_id: s for s in SPECIES}

_SCENARIOS: dict[str, dict[str, Any]] = {
    "carabayllo-rio-seco": {
        "region_bbox": [-77.25, -12.05, -76.75, -11.6],
        "primary": False,
        "name": "Río Seco ravine / Carabayllo, northern Lima",
        "locator": (-11.83, -77.01),
        "metric_crs": "EPSG:32718",
        "intervention_case": "Slope bioengineering assessment on arid ravine slopes",
        "hazard_mechanism_note": (
            "Candidate contribution to reducing surface erosion and shallow slope instability on hillsides. "
            "Channelized debris-flow runout in the active channel needs other measures; planting alone is inappropriate there."
        ),
        # (sector suffix, name, centre offset east m, north m, half-width m, half-height m, rotation deg,
        #  slope % or None, exclusion reason or None, species candidate)
        "sectors": [
            ("01", "Río Seco north slope A", -650, 380, 210, 150, 18, 38.0, None, "tara"),
            ("02", "Río Seco north slope B", -120, 520, 230, 140, 8, 55.0, None, "molle-costero"),
            ("03", "Río Seco south slope", -260, -420, 220, 160, -12, None, None, "tara"),
            ("04", "Active channel bed", -330, 40, 520, 60, 4, 8.0,
             "Active debris-flow channel: planting alone is inappropriate and deposition is a no-go.", None),
            ("05", "Upper ridge", 520, 640, 170, 120, 25, 120.0, None, "tara"),
        ],
    },
    "lower-piura-sechura": {
        "region_bbox": [-81.4, -6.4, -79.2, -4.05],
        "primary": True,
        "name": "Piura region — lower Piura dry forest and Sechura depression",
        "locator": (-5.52, -80.65),
        "metric_crs": "EPSG:32717",
        "intervention_case": "Dry-forest establishment comparison on low-relief terrain",
        "hazard_mechanism_note": (
            "Low-relief dry-forest restoration under different hydrology. This is not equivalent to hillside "
            "root reinforcement against huaicos; flooding, salinity and tenure need field assessment."
        ),
        "sectors": [
            ("01", "Dry-forest terrace A", -700, 300, 320, 220, 5, 2.0, None, "algarrobo"),
            ("02", "Dry-forest terrace B", 120, 420, 300, 200, -6, 3.0, None, "sapote"),
            ("03", "Depression margin", -250, -450, 380, 180, 0, None, None, "algarrobo"),
            ("04", "Drainage channel", 0, -40, 700, 50, 2, 1.0,
             "Drainage channel: seasonal flow path; deposition is a no-go.", None),
        ],
    },
}

SCENARIO_PREFIX = {"carabayllo-rio-seco": "CRB", "lower-piura-sechura": "PIU"}


def _polygon_lonlat(lat: float, lon: float, metric_crs: str, dx: float, dy: float, hw: float, hh: float, rot: float) -> Polygon:
    import math

    cx, cy = lonlat_to_metric(lon, lat, metric_crs)
    cx, cy = cx + dx, cy + dy
    # Irregular hexagon with a deterministic shape so polygons do not look like map tiles.
    shape = [(-1.0, -0.8), (-0.2, -1.0), (0.9, -0.7), (1.0, 0.4), (0.3, 1.0), (-0.8, 0.8)]
    r = math.radians(rot)
    pts = []
    for ux, uy in shape:
        x, y = ux * hw, uy * hh
        pts.append((cx + x * math.cos(r) - y * math.sin(r), cy + x * math.sin(r) + y * math.cos(r)))
    return to_wgs84(Polygon(pts), metric_crs)


def _sector_feature(scenario_id: str, spec: dict[str, Any], row: tuple) -> dict[str, Any]:
    suffix, name, dx, dy, hw, hh, rot, slope, exclusion, species = row
    lat, lon = spec["locator"]
    poly = _polygon_lonlat(lat, lon, spec["metric_crs"], dx, dy, hw, hh, rot)
    area = round(geodesic_area_ha(poly), 4)
    props = SectorProperties(
        sector_id=f"{SCENARIO_PREFIX[scenario_id]}-{suffix}",
        source_feature_id=None,
        sector_name=name,
        scenario_id=scenario_id,
        data_mode=DataMode.synthetic_fixture,
        boundary_note=SYNTHETIC_BOUNDARY_NOTE,
        area_ha=Quantity(value=area, unit="ha", evidence_class=EvidenceClass.derived, source="geodesic area of polygon"),
        declared_area_ha=unknown("ha", "No declared area for synthetic polygons."),
        slope_percent=(
            Quantity(value=slope, unit="percent", evidence_class=EvidenceClass.illustrative,
                     note="Illustrative placeholder; no DEM has been ingested.")
            if slope is not None
            else unknown("percent", "Slope not available; field assessment or DEM derivation required.")
        ),
        dielectric_er=unknown("dimensionless", "No validated dielectric retrieval exists for this sector."),
        sigma_hh_db=unknown("dB", "No sigma0 HH value supplied."),
        sigma_hv_db=unknown("dB", "No sigma0 HV value supplied."),
        gamma0_hh_db=unknown("dB", "Process a GCOV product to derive gamma0 HH."),
        gamma0_hv_db=unknown("dB", "Process a GCOV product to derive gamma0 HV."),
        rvi=unknown("dimensionless", "Quad-pol RVI requires HH, HV and VV channels."),
        species_candidate=species,
        exclusion_reason=exclusion,
    )
    return {"type": "Feature", "id": props.sector_id, "geometry": geometry_to_geojson(poly), "properties": props.model_dump(mode="json")}


@lru_cache(maxsize=4)
def _build(scenario_id: str) -> dict[str, Any]:
    spec = _SCENARIOS[scenario_id]
    features = [_sector_feature(scenario_id, spec, row) for row in spec["sectors"]]
    fc = {"type": "FeatureCollection", "features": features}
    lat, lon = spec["locator"]
    species = [s.model_dump(mode="json") for s in SPECIES if scenario_id in s.scenarios]
    version = content_hash({"fc": fc, "species": species, "crs": spec["metric_crs"]})
    summary = StudyAreaSummary(
        scenario_id=scenario_id,
        name=spec["name"],
        locator_lat=lat,
        locator_lon=lon,
        locator_note="Approximate locator supplied by the solution source; not a verified boundary.",
        intervention_case=spec["intervention_case"],
        hazard_mechanism_note=spec["hazard_mechanism_note"],
        metric_crs=spec["metric_crs"],
        data_mode=DataMode.synthetic_fixture,
        dataset_version=version,
        region_bbox=spec["region_bbox"],
        primary=spec["primary"],
    )
    return {"summary": summary.model_dump(mode="json"), "sectors": fc, "species": species}


def scenario_ids() -> list[str]:
    """Primary study area first (ADR 0002: Piura)."""
    return sorted(_SCENARIOS, key=lambda k: not _SCENARIOS[k]["primary"])


def get_scenario(scenario_id: str) -> dict[str, Any]:
    if scenario_id not in _SCENARIOS:
        raise KeyError(scenario_id)
    return _build(scenario_id)


def species_for(scenario_id: str) -> list[SpeciesCandidate]:
    return [s for s in SPECIES if scenario_id in s.scenarios]
