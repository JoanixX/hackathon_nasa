"""Hypothesis strategies for sector datasets, plan requests and model outputs."""

from __future__ import annotations

import math

from hypothesis import strategies as st
from shapely.geometry import Polygon

from raiz_sar.contracts import DroneParameters, PlanningAssumptions, PlanRequest
from raiz_sar.geo import geodesic_area_ha, geometry_to_geojson, lonlat_to_metric, to_wgs84

CRS = "EPSG:32718"
BASE_LON, BASE_LAT = -77.01, -11.83


def quantity(value, unit, cls):
    if value is None:
        return {"value": None, "unit": unit, "evidence_class": "unknown", "source": None, "note": None}
    return {"value": value, "unit": unit, "evidence_class": cls, "source": None, "note": None}


@st.composite
def sector_features(draw, min_size=1, max_size=6):
    """Non-overlapping rectangular sectors laid out on a grid with random attributes."""
    n = draw(st.integers(min_size, max_size))
    cx, cy = lonlat_to_metric(BASE_LON, BASE_LAT, CRS)
    feats = []
    for i in range(n):
        w = draw(st.floats(40, 600))
        h = draw(st.floats(40, 600))
        ox = (i % 3) * 800.0
        oy = (i // 3) * 800.0
        poly_m = Polygon([(cx + ox, cy + oy), (cx + ox + w, cy + oy), (cx + ox + w, cy + oy + h), (cx + ox, cy + oy + h)])
        poly = to_wgs84(poly_m, CRS)
        slope = draw(st.one_of(st.none(), st.floats(0, 300, allow_nan=False)))
        excluded = draw(st.booleans()) and draw(st.booleans())
        species = draw(st.sampled_from(["tara", "molle-costero", None, "not-a-species"]))
        feats.append({
            "type": "Feature", "id": f"S{i}", "geometry": geometry_to_geojson(poly),
            "properties": {
                "sector_id": f"S{i}", "sector_name": f"Sector {i}", "scenario_id": "carabayllo-rio-seco",
                "data_mode": "synthetic_fixture", "boundary_note": "test",
                "area_ha": quantity(round(geodesic_area_ha(poly), 4), "ha", "derived"),
                "slope_percent": quantity(slope, "percent", "illustrative"),
                "species_candidate": species,
                "exclusion_reason": "test exclusion" if excluded else None,
            },
        })
    return feats


finite_pos = lambda lo, hi: st.floats(lo, hi, allow_nan=False, allow_infinity=False)  # noqa: E731


@st.composite
def assumptions(draw):
    return PlanningAssumptions(
        target_density_plants_per_ha=draw(finite_pos(0, 5000)),
        seeds_per_capsule=draw(st.integers(1, 50)),
        germination_fraction=draw(finite_pos(0.01, 1)),
        establishment_fraction=draw(finite_pos(0.01, 1)),
        capsule_cost_pen=draw(finite_pos(0, 20)),
        delivery_cost_per_ha_pen=draw(finite_pos(0, 5000)),
        maintenance_cost_per_ha_pen=draw(finite_pos(0, 5000)),
        monitoring_fixed_cost_pen=draw(finite_pos(0, 20000)),
        max_slope_percent=draw(finite_pos(1, 400)),
    )


@st.composite
def plan_requests(draw, sector_ids):
    mode = draw(st.sampled_from(["budget", "target"]))
    selected = draw(st.one_of(st.none(), st.lists(st.sampled_from(sector_ids), unique=True))) if sector_ids else None
    return PlanRequest(
        scenario_id="carabayllo-rio-seco", dataset_version="test", mode=mode,
        budget_pen=draw(finite_pos(0, 500_000)) if mode == "budget" else None,
        target_established_plants=draw(st.integers(0, 500_000)) if mode == "target" else None,
        selected_sector_ids=selected,
        assumptions=draw(assumptions()),
        drone=DroneParameters(),
        establishment_half_life_days=draw(st.one_of(st.none(), finite_pos(1, 3650))),
        delay_days=draw(st.lists(st.integers(0, 365), min_size=1, max_size=12, unique=True)),
    )


def is_finite(x) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(x)
