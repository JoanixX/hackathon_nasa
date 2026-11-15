"""User-delimited zones: validation, DEM enrichment and segmentation-assisted boundary suggestions.

A suggestion is never applied here. It is returned beside the user's polygon with its method,
sources and comparison metrics; the user decides. Original and confirmed geometries are both kept.
"""

from __future__ import annotations

import datetime as dt
import math
from typing import Any

import numpy as np
from rasterio.features import geometry_mask, shapes
from rasterio.warp import reproject
from rasterio.enums import Resampling
from shapely.geometry import MultiPolygon, Polygon, mapping, shape
from shapely.ops import unary_union
from shapely.validation import explain_validity

from .contracts import DataMode, EvidenceClass, Quantity, SectorProperties, content_hash, unknown
from .geo import geodesic_area_ha, geometry_to_geojson, to_metric, to_wgs84, utm_epsg_for
from .scenarios import get_scenario

MAX_ZONES = 20
MAX_VERTICES = 2000
MIN_AREA_HA = 0.05
MAX_AREA_HA = 50_000


class ZoneError(ValueError):
    pass


def validate_polygon(obj: Any) -> Polygon | MultiPolygon:
    """Strict validation of one user polygon in lon/lat; never silently repairs it."""
    if not isinstance(obj, dict) or obj.get("type") not in ("Polygon", "MultiPolygon"):
        raise ZoneError("A zone must be a GeoJSON Polygon.")
    coords = obj.get("coordinates")
    try:
        geom = shape({"type": obj["type"], "coordinates": coords})
    except (ValueError, TypeError, IndexError, AttributeError) as exc:
        raise ZoneError("Malformed polygon coordinates.") from exc
    pts = list(geom.exterior.coords) if isinstance(geom, Polygon) else [c for g in geom.geoms for c in g.exterior.coords]
    if len(pts) > MAX_VERTICES:
        raise ZoneError(f"Too many vertices (limit {MAX_VERTICES}).")
    for p in pts:
        if len(p) < 2 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in p[:2]):
            raise ZoneError("Coordinates must be finite numbers.")
        if not (-180 <= p[0] <= 180 and -90 <= p[1] <= 90):
            raise ZoneError("Coordinates must be longitude/latitude (WGS 84).")
    if geom.is_empty:
        raise ZoneError("The polygon is empty.")
    if isinstance(geom, Polygon) and len(geom.exterior.coords) < 4:
        raise ZoneError("A polygon needs at least three distinct vertices.")
    if not geom.is_valid:
        raise ZoneError(f"Invalid polygon: {explain_validity(geom)}. Move the crossing vertices and close it again.")
    area = geodesic_area_ha(geom)
    if area < MIN_AREA_HA:
        raise ZoneError(f"Zone smaller than {MIN_AREA_HA} ha (about one 30 m grid cell is 0.09 ha).")
    if area > MAX_AREA_HA:
        raise ZoneError(f"Zone larger than {MAX_AREA_HA:,} ha; split it into smaller zones.")
    return geom


def build_zone_dataset(scenario_id: str, zones: list[dict[str, Any]], terrain_fn=None) -> dict[str, Any]:
    """Validate zones, attach DEM terrain statistics and return an imported-dataset record."""
    try:
        summary = get_scenario(scenario_id)["summary"]
    except KeyError as exc:
        raise ZoneError("Unknown scenario.") from exc
    if not zones:
        raise ZoneError("Draw at least one zone.")
    if len(zones) > MAX_ZONES:
        raise ZoneError(f"At most {MAX_ZONES} zones.")
    region = summary.get("region_bbox")
    from .terrain import TerrainUnavailable, zone_terrain_stats

    terrain_fn = terrain_fn or zone_terrain_stats
    features, seen = [], set()
    for i, z in enumerate(zones):
        geom = validate_polygon(z.get("geometry"))
        if region:
            w, s, e, n = region
            minx, miny, maxx, maxy = geom.bounds
            if minx < w or maxx > e or miny < s or maxy > n:
                raise ZoneError(f"Zone {i + 1} lies outside the {summary['name']} study region.")
        name = str(z.get("name") or f"Zone {i + 1}").strip()[:120] or f"Zone {i + 1}"
        name = "".join(ch for ch in name if ch.isprintable())
        sid = f"Z{i + 1:02d}"
        role = z.get("role", "candidate")
        if role not in ("candidate", "no_go"):
            raise ZoneError("Zone role must be candidate or no_go.")
        species = z.get("species_candidate") or None
        warnings: list[str] = []
        try:
            stats = terrain_fn(geom)
            slope = Quantity(value=stats["slope_percent_median"], unit="percent", evidence_class=EvidenceClass.derived,
                             source=stats["source"], note=f"Median of {stats['cells']} cells; p90 {stats['slope_percent_p90']}%.")
        except (TerrainUnavailable, ValueError) as exc:
            stats = None
            slope = unknown("percent", f"DEM unavailable: {exc}")
            warnings.append("Slope unknown: DEM unavailable for this zone.")
        refinement = z.get("refinement") or None
        props = SectorProperties(
            sector_id=sid, source_feature_id=None, sector_name=name, scenario_id=scenario_id, data_mode=DataMode.real,
            boundary_note=("User-drawn zone, boundary confirmed by the user"
                           + (" after accepting an assisted suggestion." if refinement and refinement.get("accepted") else ".")),
            area_ha=Quantity(value=round(geodesic_area_ha(geom), 4), unit="ha", evidence_class=EvidenceClass.derived,
                             source="geodesic area of the confirmed polygon"),
            declared_area_ha=unknown("ha"), slope_percent=slope,
            dielectric_er=unknown("dimensionless", "No validated dielectric retrieval."),
            sigma_hh_db=unknown("dB"), sigma_hv_db=unknown("dB"),
            gamma0_hh_db=unknown("dB", "Requires a downloaded GCOV product."),
            gamma0_hv_db=unknown("dB", "Requires a downloaded GCOV product."),
            rvi=unknown("dimensionless"), species_candidate=species,
            exclusion_reason=("Marked as a no-go zone by the user." if role == "no_go" else None),
            warnings=warnings,
        )
        feat = {"type": "Feature", "id": sid, "geometry": geometry_to_geojson(geom), "properties": props.model_dump(mode="json")}
        feat["properties"]["terrain"] = stats
        feat["properties"]["role"] = role
        # Both the original drawing and the confirmed geometry are always recorded.
        feat["properties"]["original_geometry"] = z.get("original_geometry") or geometry_to_geojson(geom)
        if refinement:
            feat["properties"]["refinement"] = refinement
        features.append(feat)
        seen.add(sid)
    # Zones may not overlap: overlapping candidates would double-count planting areas.
    geoms = [shape(f["geometry"]) for f in features]
    for a in range(len(geoms)):
        for b in range(a + 1, len(geoms)):
            if geoms[a].intersection(geoms[b]).area > 1e-12:
                raise ZoneError(f"Zones {a + 1} and {b + 1} overlap; edit one so they do not share area.")
    sectors = {"type": "FeatureCollection", "features": features}
    h = content_hash({"sectors": sectors})
    return {"scenario_id": scenario_id, "data_mode": "real", "source_label": "user-drawn zones", "sectors": sectors,
            "content_hash": h, "dataset_version": f"zones-{h}", "rejected": [], "warnings": []}


# ---------------------------------------------------------------- assisted boundary suggestion

def suggest_boundary(geometry: dict[str, Any], optical_date: str | None = None, res_m: float = 30.0,
                     dem_fn=None, imagery_fn=None) -> dict[str, Any]:
    """SLIC superpixels on DEM slope (+ HLS colour when available) snapped to the user's polygon.

    Returns a *proposal*: the user polygon is never modified here.
    """
    from skimage.segmentation import slic

    from .terrain import metric_dem, slope_percent

    user = validate_polygon(geometry)
    dem_fn = dem_fn or (lambda g: metric_dem(g, margin_m=max(150.0, math.sqrt(to_metric(g, utm_epsg_for(g.centroid.x, g.centroid.y)).area) * 0.3), res_m=res_m))
    dem, tf, crs, gm = dem_fn(user)
    slope = slope_percent(dem, res_m)
    h, w = dem.shape
    if h * w > 360_000:
        raise ZoneError("Zone too large for an assisted suggestion; draw a smaller zone (about 300 km² maximum).")
    feats = [np.clip(np.nan_to_num(slope, nan=0.0), 0, 150) / 150.0]
    sources = [{"layer": "Copernicus DEM GLO-30 slope", "resolution_m": res_m}]
    imagery_used = None
    if optical_date:
        try:
            rgb = (imagery_fn or _hls_rgb)(optical_date, user, dem.shape, tf, crs)
            if rgb is not None:
                feats.extend(list(rgb))
                imagery_used = optical_date
                sources.append({"layer": "HLS S30 true colour (GIBS rendering)", "date": optical_date, "resolution_m": 30})
        except Exception:  # imagery is optional; the suggestion falls back to terrain only
            imagery_used = None
    stack = np.stack(feats, axis=-1).astype("float64")
    inside = ~geometry_mask([mapping(gm)], out_shape=(h, w), transform=tf, all_touched=False)
    if inside.sum() < 4:
        raise ZoneError("Zone too small for a 30 m segmentation suggestion.")
    n_segments = max(12, int(h * w / 36))
    labels = slic(stack, n_segments=n_segments, compactness=0.12, start_label=1, channel_axis=-1, enforce_connectivity=True)
    keep = np.zeros_like(inside)
    for lab in np.unique(labels):
        m = labels == lab
        if inside[m].mean() >= 0.5:
            keep |= m
    polys = [shape(g) for g, v in shapes(keep.astype("uint8"), mask=keep, transform=tf) if v == 1]
    if not polys:
        raise ZoneError("No boundary suggestion could be formed for this zone.")
    merged = unary_union(polys).buffer(0).simplify(res_m / 2)
    if isinstance(merged, MultiPolygon):
        merged = max(merged.geoms, key=lambda p: p.area)  # one zone in, one zone out
    merged = Polygon(merged.exterior)  # drop pinholes from the pixel mask
    suggestion = to_wgs84(merged, crs)
    if not suggestion.is_valid:
        suggestion = suggestion.buffer(0)
    inter = gm.intersection(merged).area
    union = gm.union(merged).area
    return {
        "status": "proposal",
        "applied": False,
        "method": "SLIC superpixels (scikit-image) on DEM slope" + (" and HLS colour" if imagery_used else "")
                  + "; superpixels at least 50% inside the drawn polygon are kept.",
        "sources": sources,
        "grid": f"{crs} at {res_m:g} m",
        "boundary_uncertainty_m": res_m,
        "user_geometry": geometry_to_geojson(user),
        "suggested_geometry": geometry_to_geojson(suggestion),
        "metrics": {
            "user_area_ha": round(geodesic_area_ha(user), 3),
            "suggested_area_ha": round(geodesic_area_ha(suggestion), 3),
            "iou": round(inter / union, 3) if union else 0.0,
            "max_boundary_shift_m": round(gm.hausdorff_distance(merged), 1),
        },
        "note": ("A visual-terrain boundary proposal at 30 m, not a surveyed or scientifically determined limit. "
                 "Accept it, edit it, or keep your own polygon."),
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }


def _hls_rgb(date: str, user, shape_hw, tf, crs):
    from .sources import fetch_gibs_mosaic

    b = user.buffer(0.02).bounds
    rgba, src_tf = fetch_gibs_mosaic("hls_s30", date, b, 12)
    if rgba[3].mean() < 10:
        return None
    out = np.zeros((3, *shape_hw), dtype="float32")
    for i in range(3):
        reproject(rgba[i].astype("float32"), out[i], src_transform=src_tf, src_crs="EPSG:3857", dst_transform=tf,
                  dst_crs=crs, resampling=Resampling.bilinear)
    return out / 255.0
