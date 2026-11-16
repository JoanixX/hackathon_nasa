"""Candidate seed/capsule deposition planning (extension).

Produces deposition nodes inside funded eligible areas (outside no-go buffers) and splits them
into sorties bounded by payload and a route-length limit that already includes the energy
reserve. This is a planning artifact only: no flight command, upload or planting is executed,
and operational constraints remain unverified.
"""

from __future__ import annotations

import math
from typing import Any

from shapely.geometry import Point
from shapely.ops import unary_union
from shapely.prepared import prep

from .contracts import BudgetScenario, DepositionNode, DroneParameters, DroneSeedingPlan, DroneSortie
from .geo import geometry_from_geojson, lonlat_to_metric, metric_to_lonlat, to_metric

MAX_NODES = 1500
MAX_VISITS = 6000


def candidate_grid(bounds, spacing: float, budget: int):
    """Deterministic, bounded grid. Coarsens display sampling without changing physical coordinates."""
    if (not isinstance(budget, int) or not 0 <= budget <= MAX_NODES * 4 or
            not math.isfinite(spacing) or spacing <= 0 or len(bounds) != 4 or
            not all(math.isfinite(v) for v in bounds)):
        raise ValueError("Finite grid bounds, positive spacing and a bounded sample budget are required.")
    minx, miny, maxx, maxy = bounds
    width, height = maxx - minx, maxy - miny
    if budget < 1 or width <= 0 or height <= 0:
        return
    nx = max(1, math.ceil(width / spacing))
    ny = max(1, math.ceil(height / spacing))
    if nx * ny > budget:
        nx = min(nx, budget, max(1, int(math.sqrt(budget * width / max(height, spacing)))))
        ny = min(ny, max(1, budget // nx))
    for row in range(ny):
        indices = range(nx) if row % 2 == 0 else range(nx - 1, -1, -1)
        for col in indices:
            yield minx + (col + .5) * width / nx, miny + (row + .5) * height / ny

UNVERIFIED = [
    "Aviation authorization and local operating rules (not verified).",
    "Terrain clearance and obstacle survey (no DEM or field survey ingested).",
    "Seed/capsule release mechanism, rate and spatial accuracy (not verified).",
    "Wind, temperature and battery performance; route limit is a user assumption.",
    "Landowner permission and community consultation (not verified).",
]


def _route_length(points: list[tuple[float, float]], launch: tuple[float, float]) -> float:
    if not points:
        return 0.0
    d = math.dist(launch, points[0])
    for a, b in zip(points, points[1:]):
        d += math.dist(a, b)
    return d + math.dist(points[-1], launch)


def plan_deposition(
    features: list[dict[str, Any]],
    budget: BudgetScenario,
    params: DroneParameters,
    metric_crs: str,
) -> DroneSeedingPlan:
    by_id = {f["properties"]["sector_id"]: f for f in features}
    funded = [a for a in budget.allocations if a.capsules > 0]
    purpose = "Candidate seed/capsule deposition plan for planning review; deposits seeds, not mature plants."
    note = "Not an executable flight plan. No route upload, aircraft control or planting has occurred."
    if not funded:
        return DroneSeedingPlan(status="not_applicable", purpose=purpose, launch_lat=None, launch_lon=None,
                                nodes=[], sorties=[], total_capsules=0, unverified_constraints=UNVERIFIED,
                                infeasibility_reason="No funded capsules to deposit.", note=note)

    no_go = [to_metric(geometry_from_geojson(f["geometry"]), metric_crs).buffer(params.no_go_buffer_m)
             for f in features if f["properties"].get("exclusion_reason")]
    # Mapped infrastructure (buildings, roads, paths) with the largest mature crown radius as clearance (NV-04).
    from .exclusions import exclusion_metric
    from .scenarios import SPECIES_MAX_CROWN_RADIUS_M

    for f in features:
        ex = exclusion_metric(f, metric_crs)
        if ex is not None:
            no_go.append(ex.buffer(SPECIES_MAX_CROWN_RADIUS_M))
    no_go_shape = unary_union(no_go) if no_go else None
    no_go_union = prep(no_go_shape) if no_go_shape is not None else None

    spacing = params.node_spacing_m
    raw_nodes: list[tuple[str, float, float]] = []
    quota = max(1, MAX_NODES // len(funded))
    for alloc in funded:
        geom = funded_geometry(to_metric(geometry_from_geojson(by_id[alloc.sector_id]["geometry"]), metric_crs),
                               alloc.funded_fraction)
        pg = prep(geom)
        pts: list[tuple[float, float]] = []
        target = min(quota, alloc.capsules)
        for x, y in candidate_grid(geom.bounds, spacing, target * 4):
            pt = Point(x, y)
            if pg.contains(pt) and not (no_go_union and no_go_union.covers(pt)):
                pts.append((x, y))
        if len(pts) > target:
            pts = [pts[int(i * len(pts) / target)] for i in range(target)]
        if not pts:
            available = geom.difference(no_go_shape) if no_go_shape is not None else geom
            c = available.representative_point()
            if not c.is_empty and not (no_go_union and no_go_union.covers(c)):
                pts = [(c.x, c.y)]
        raw_nodes.extend((alloc.sector_id, x, y) for x, y in pts)
        if len(raw_nodes) > MAX_NODES * 4:
            break

    # Thin uniformly if the grid is too dense for a reviewable plan.
    if len(raw_nodes) > MAX_NODES:
        step = len(raw_nodes) / MAX_NODES
        raw_nodes = [raw_nodes[int(i * step)] for i in range(MAX_NODES)]

    by_sector: dict[str, list[tuple[float, float]]] = {}
    for sid, x, y in raw_nodes:
        by_sector.setdefault(sid, []).append((x, y))

    missing = [a.sector_id for a in funded if not by_sector.get(a.sector_id)]
    if missing:
        return DroneSeedingPlan(status="infeasible", purpose=purpose, launch_lat=None, launch_lon=None, nodes=[],
                                sorties=[], total_capsules=0, unverified_constraints=UNVERIFIED,
                                infeasibility_reason=f"No deposition node fits outside no-go areas in: {', '.join(missing)}.",
                                note=note)

    if params.launch_lat is not None and params.launch_lon is not None:
        launch = lonlat_to_metric(params.launch_lon, params.launch_lat, metric_crs)
    else:
        first = by_sector[funded[0].sector_id][0]
        launch = (first[0], first[1])

    # Distribute each sector's capsules over its nodes (integer split, remainder to the first nodes).
    nodes_m: list[tuple[str, float, float, int]] = []
    for a in funded:
        pts = by_sector[a.sector_id]
        base, rem = divmod(a.capsules, len(pts))
        for i, (x, y) in enumerate(pts):
            c = base + (1 if i < rem else 0)
            if c > 0:
                nodes_m.append((a.sector_id, x, y, c))

    # Split a node whose capsules exceed the payload into repeated visits.
    queue: list[tuple[str, float, float, int]] = []
    cap = params.payload_capsules_per_sortie
    if sum(math.ceil(c / cap) for _, _, _, c in nodes_m) > MAX_VISITS:
        return DroneSeedingPlan(status="infeasible", purpose=purpose, launch_lat=None, launch_lon=None,
                                nodes=[], sorties=[], total_capsules=0, unverified_constraints=UNVERIFIED,
                                infeasibility_reason="The preview exceeds 6,000 deposition visits; split the intervention into phases.", note=note)
    for sid, x, y, c in nodes_m:
        while c > cap:
            queue.append((sid, x, y, cap))
            c -= cap
        queue.append((sid, x, y, c))

    sorties: list[DroneSortie] = []
    nodes: list[DepositionNode] = []
    current: list[tuple[str, float, float, int]] = []
    load = 0
    route_length = 0.0

    def close() -> str | None:
        nonlocal current, load, route_length
        if not current:
            return None
        pts = [(x, y) for _, x, y, _ in current]
        length = _route_length(pts, launch)
        if length > params.max_route_m_per_sortie:
            return "A sortie exceeds the route limit; move the launch point or raise the limit."
        sortie_no = len(sorties) + 1
        ids = []
        for i, (sid, x, y, c) in enumerate(current):
            lon, lat = metric_to_lonlat(x, y, metric_crs)
            nid = f"N{len(nodes) + 1:04d}"
            nodes.append(DepositionNode(node_id=nid, sector_id=sid, lat=lat, lon=lon, capsules=c, sortie=sortie_no, order=i + 1))
            ids.append(nid)
        sorties.append(DroneSortie(sortie=sortie_no, capsules=load, route_m=round(length, 1), node_ids=ids))
        current, load, route_length = [], 0, 0.0
        return None

    for item in queue:
        sid, x, y, c = item
        single = 2 * math.dist(launch, (x, y))
        if single > params.max_route_m_per_sortie:
            return DroneSeedingPlan(status="infeasible", purpose=purpose, launch_lat=None, launch_lon=None, nodes=[],
                                    sorties=[], total_capsules=0, unverified_constraints=UNVERIFIED,
                                    infeasibility_reason="A deposition node is beyond the round-trip route limit from the launch point.",
                                    note=note)
        last = (current[-1][1], current[-1][2]) if current else launch
        trial_length = route_length + math.dist(last, (x, y)) + math.dist((x, y), launch) - math.dist(last, launch)
        if current and (load + c > cap or trial_length > params.max_route_m_per_sortie):
            err = close()
            if err:
                return DroneSeedingPlan(status="infeasible", purpose=purpose, launch_lat=None, launch_lon=None,
                                        nodes=[], sorties=[], total_capsules=0, unverified_constraints=UNVERIFIED,
                                        infeasibility_reason=err, note=note)
            trial_length = single
        current.append(item)
        load += c
        route_length = trial_length
    err = close()
    if err:
        return DroneSeedingPlan(status="infeasible", purpose=purpose, launch_lat=None, launch_lon=None,
                                nodes=[], sorties=[], total_capsules=0, unverified_constraints=UNVERIFIED,
                                infeasibility_reason=err, note=note)

    lon, lat = metric_to_lonlat(launch[0], launch[1], metric_crs)
    return DroneSeedingPlan(
        status="candidate_plan_incomplete", purpose=purpose, launch_lat=lat, launch_lon=lon,
        nodes=nodes, sorties=sorties, total_capsules=sum(n.capsules for n in nodes),
        unverified_constraints=UNVERIFIED, infeasibility_reason=None, note=note,
    )


def funded_geometry(geom_m, fraction: float):
    """Area share funded by the budget, laid out as the zone's core (inward buffer found by bisection).

    The location of the funded part inside a zone is not optimized; the core is a neutral, declared
    layout so markers and deposition points do not cluster against an arbitrary edge.
    """
    if fraction >= 1.0:
        return geom_m
    if fraction <= 0:
        return geom_m.buffer(-1e9)
    target = geom_m.area * fraction
    minx, miny, maxx, maxy = geom_m.bounds
    lo, hi = 0.0, max(maxx - minx, maxy - miny)
    best = geom_m
    for _ in range(40):
        mid = (lo + hi) / 2
        core = geom_m.buffer(-mid)
        if core.is_empty or core.area < target:
            hi = mid
        else:
            lo, best = mid, core
    return best if not best.is_empty else geom_m
