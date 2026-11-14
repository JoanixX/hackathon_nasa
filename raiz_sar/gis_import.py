"""GIS import boundary: validates external GeoJSON (for example an ArcGIS export) and normalizes
legacy attribute keys into the English internal sector contract.

Imported text is untrusted data. Invalid features are rejected with actionable reasons; the
current plan is never mutated by a failed import.
"""

from __future__ import annotations

import math
from typing import Any

from shapely.validation import explain_validity

from .contracts import DataMode, EvidenceClass, Quantity, SectorProperties, content_hash, unknown
from .geo import geodesic_area_ha, geometry_from_geojson, geometry_to_geojson

MAX_FEATURES = 500
MAX_VERTICES = 20_000
MAX_TEXT = 120

# External legacy key -> internal key. The internal names are the stable contract.
LEGACY_KEYS = {
    "nombre": "sector_name",
    "hectareas": "area_ha",
    "pendiente": "slope_percent",
    "dielectric_er": "dielectric_er",
    "sigma_hh": "sigma_hh_db",
    "sigma_hv": "sigma_hv_db",
    "rvi": "rvi",
    "especie": "species_candidate",
}
INTERNAL_KEYS = set(LEGACY_KEYS.values()) | {"sector_id"}
ACCEPTED_CRS = {
    "urn:ogc:def:crs:OGC:1.3:CRS84",
    "urn:ogc:def:crs:OGC::CRS84",
    "EPSG:4326",
    "urn:ogc:def:crs:EPSG::4326",
}


class ImportErrorReport(ValueError):
    def __init__(self, message: str, details: list[str] | None = None):
        super().__init__(message)
        self.details = details or []


def _clean_text(v: Any, field: str) -> str | None:
    if v is None:
        return None
    if not isinstance(v, (str, int, float)) or isinstance(v, bool):
        raise ValueError(f"{field} must be text")
    s = str(v).strip()
    s = "".join(ch for ch in s if ch.isprintable())
    if not s:
        return None
    if len(s) > MAX_TEXT:
        raise ValueError(f"{field} exceeds {MAX_TEXT} characters")
    return s


def _number(v: Any, field: str) -> float | None:
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    if isinstance(v, bool):
        raise ValueError(f"{field} must be numeric")
    try:
        x = float(v)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if not math.isfinite(x):
        raise ValueError(f"{field} must be finite")
    return x


def _count_vertices(coords: Any, depth: int = 0) -> int:
    if depth > 6:
        raise ValueError("geometry nesting too deep")
    if isinstance(coords, (list, tuple)) and coords and isinstance(coords[0], (int, float)) and not isinstance(coords[0], bool):
        return 1
    if not isinstance(coords, (list, tuple)):
        raise ValueError("coordinates must be arrays")
    return sum(_count_vertices(c, depth + 1) for c in coords)


def _check_positions(coords: Any, depth: int = 0) -> None:
    if isinstance(coords, (list, tuple)) and coords and isinstance(coords[0], (int, float)) and not isinstance(coords[0], bool):
        if len(coords) < 2 or len(coords) > 3:
            raise ValueError("positions need 2 or 3 numbers")
        for c in coords:
            if isinstance(c, bool) or not isinstance(c, (int, float)) or not math.isfinite(c):
                raise ValueError("position values must be finite numbers")
        lon, lat = coords[0], coords[1]
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise ValueError("coordinates outside WGS 84 longitude/latitude range (projected CRS is not supported)")
        return
    if not isinstance(coords, (list, tuple)) or not coords:
        raise ValueError("empty or malformed coordinate array")
    for c in coords:
        _check_positions(c, depth + 1)


def normalize_feature_collection(obj: Any, scenario_id: str, source_label: str) -> dict[str, Any]:
    if not isinstance(obj, dict) or obj.get("type") != "FeatureCollection":
        raise ImportErrorReport("Expected a GeoJSON FeatureCollection.")
    crs = obj.get("crs")
    if crs is not None:
        name = (crs.get("properties") or {}).get("name") if isinstance(crs, dict) else None
        if name not in ACCEPTED_CRS:
            raise ImportErrorReport(f"Unsupported CRS '{name}'. Export WGS 84 longitude/latitude (EPSG:4326).")
    feats = obj.get("features")
    if not isinstance(feats, list) or not feats:
        raise ImportErrorReport("The FeatureCollection has no features.")
    if len(feats) > MAX_FEATURES:
        raise ImportErrorReport(f"Too many features ({len(feats)}); the limit is {MAX_FEATURES}.")

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen: set[str] = set()
    total_vertices = 0
    for idx, f in enumerate(feats):
        try:
            if not isinstance(f, dict) or f.get("type") != "Feature":
                raise ValueError("not a GeoJSON Feature")
            geom_obj = f.get("geometry")
            if not isinstance(geom_obj, dict) or geom_obj.get("type") not in ("Polygon", "MultiPolygon"):
                raise ValueError("geometry must be a Polygon or MultiPolygon")
            coords = geom_obj.get("coordinates")
            total_vertices += _count_vertices(coords)
            if total_vertices > MAX_VERTICES:
                raise ImportErrorReport(f"Too many vertices; the limit is {MAX_VERTICES}.")
            _check_positions(coords)
            geom = geometry_from_geojson({"type": geom_obj["type"], "coordinates": coords})
            if geom.is_empty:
                raise ValueError("empty geometry")
            if not geom.is_valid:
                raise ValueError(f"invalid geometry: {explain_validity(geom)}")
            raw = f.get("properties") or {}
            if not isinstance(raw, dict):
                raise ValueError("properties must be an object")
            props: dict[str, Any] = {}
            for k, v in raw.items():
                if not isinstance(k, str):
                    continue
                target = LEGACY_KEYS.get(k, k if k in INTERNAL_KEYS else None)
                if target:
                    props[target] = v
            fid = _clean_text(f.get("id"), "id") if f.get("id") is not None else None
            sid = _clean_text(props.get("sector_id"), "sector_id") or fid or f"IMP-{idx + 1:03d}"
            sid = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in sid)[:64]
            if sid in seen:
                raise ValueError(f"duplicate sector_id '{sid}'")
            name = _clean_text(props.get("sector_name"), "sector_name")
            if not name:
                raise ValueError("sector_name (nombre) is required")
            feat_warn: list[str] = []
            area = round(geodesic_area_ha(geom), 4)
            if area <= 0:
                raise ValueError("zero-area polygon")
            declared = _number(props.get("area_ha"), "area_ha")
            if declared is not None:
                if declared <= 0:
                    raise ValueError("declared area must be positive")
                if abs(declared - area) / area > 0.10:
                    feat_warn.append(f"Declared area {declared:g} ha differs from geometry area {area:g} ha by more than 10%.")
            slope = _number(props.get("slope_percent"), "slope_percent")
            if slope is not None:
                if slope < 0 or slope > 1000:
                    raise ValueError("slope_percent must be within 0..1000")
                feat_warn.append("Slope units not declared by the source; interpreted as percent, not degrees.")
            hh = _number(props.get("sigma_hh_db"), "sigma_hh_db")
            hv = _number(props.get("sigma_hv_db"), "sigma_hv_db")
            for nm, v in (("sigma_hh_db", hh), ("sigma_hv_db", hv)):
                if v is not None and not (-60 <= v <= 30):
                    raise ValueError(f"{nm} outside plausible dB range -60..30")
            er = _number(props.get("dielectric_er"), "dielectric_er")
            if er is not None and not (1 <= er <= 90):
                raise ValueError("dielectric_er outside 1..90")
            rvi = _number(props.get("rvi"), "rvi")
            if rvi is not None and not (0 <= rvi <= 1):
                raise ValueError("rvi outside 0..1")
            species = _clean_text(props.get("species_candidate"), "species_candidate")
            src = f"Imported attribute ({source_label}); method and normalization not verified."
            sp = SectorProperties(
                sector_id=sid,
                source_feature_id=fid,
                sector_name=name,
                scenario_id=scenario_id,
                data_mode=DataMode.real,
                boundary_note="Imported boundary; provenance as declared by the source file.",
                area_ha=Quantity(value=area, unit="ha", evidence_class=EvidenceClass.derived, source="geodesic area of imported polygon"),
                declared_area_ha=(Quantity(value=declared, unit="ha", evidence_class=EvidenceClass.observed, source=src)
                                  if declared is not None else unknown("ha")),
                slope_percent=(Quantity(value=slope, unit="percent", evidence_class=EvidenceClass.observed, source=src)
                               if slope is not None else unknown("percent", "Not supplied.")),
                dielectric_er=(Quantity(value=er, unit="dimensionless", evidence_class=EvidenceClass.illustrative,
                                        source=src, note="Retrieval method unknown; not validated telemetry.")
                               if er is not None else unknown("dimensionless")),
                sigma_hh_db=(Quantity(value=hh, unit="dB", evidence_class=EvidenceClass.observed, source=src)
                             if hh is not None else unknown("dB")),
                sigma_hv_db=(Quantity(value=hv, unit="dB", evidence_class=EvidenceClass.observed, source=src)
                             if hv is not None else unknown("dB")),
                gamma0_hh_db=unknown("dB"),
                gamma0_hv_db=unknown("dB"),
                rvi=(Quantity(value=rvi, unit="dimensionless", evidence_class=EvidenceClass.observed, source=src,
                              note="Formula and channels not declared by the source.")
                     if rvi is not None else unknown("dimensionless")),
                species_candidate=species,
                exclusion_reason=None,
                warnings=feat_warn,
            )
            seen.add(sid)
            accepted.append({"type": "Feature", "id": sid, "geometry": geometry_to_geojson(geom),
                             "properties": sp.model_dump(mode="json")})
        except ImportErrorReport:
            raise
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            rejected.append({"index": idx, "reason": str(exc)[:200]})
    if not accepted:
        raise ImportErrorReport("No valid features were imported.", [f"Feature {r['index']}: {r['reason']}" for r in rejected[:20]])
    if rejected:
        warnings.append(f"{len(rejected)} feature(s) rejected; see details.")
    sectors = {"type": "FeatureCollection", "features": accepted}
    h = content_hash({"sectors": sectors})
    return {
        "scenario_id": scenario_id,
        "data_mode": "real",
        "source_label": source_label,
        "sectors": sectors,
        "content_hash": h,
        "dataset_version": f"import-{h}",
        "rejected": rejected,
        "warnings": warnings,
    }
