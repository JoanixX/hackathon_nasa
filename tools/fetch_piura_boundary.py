"""Fetch the Piura department (Peru, admin level 4) boundary from OpenStreetMap once and store it with provenance.

Usage (inside the app container): python tools/fetch_piura_boundary.py
Writes raiz_sar/boundaries/piura_department.geojson and piura_department.source.json (source, date, licence,
SHA-256, area). Cross-checks the area against geoBoundaries gbOpen PER ADM1 (reported, not used as the boundary).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

import httpx
from shapely.geometry import mapping, shape

OUT = Path(__file__).resolve().parent.parent / "raiz_sar" / "boundaries"
UA = "RAIZ-SAR-AI/1.0 (NASA Space Apps 2026 prototype)"
NOMINATIM = ("https://nominatim.openstreetmap.org/search?q=Piura&countrycodes=pe&featureType=state"
             "&polygon_geojson=1&polygon_threshold=0.0005&format=geojson&limit=1")
GEOBOUNDARIES = "https://github.com/wmgeolab/geoBoundaries/raw/90a1d52/releaseData/gbOpen/PER/ADM1/geoBoundaries-PER-ADM1_simplified.geojson"


def area_km2(g) -> float:
    from pyproj import Geod

    return abs(Geod(ellps="WGS84").geometry_area_perimeter(g)[0]) / 1e6


def main() -> None:
    with httpx.Client(headers={"User-Agent": UA}, timeout=60, follow_redirects=True) as c:
        r = c.get(NOMINATIM)
        r.raise_for_status()
        fc = r.json()
        feat = fc["features"][0]
        props = feat["properties"]
        if props.get("addresstype") not in ("state", "region") and props.get("type") not in ("administrative",):
            raise SystemExit(f"Unexpected result: {props}")
        g = shape(feat["geometry"]).buffer(0)
        gb_area = None
        try:
            gb = c.get(GEOBOUNDARIES).json()
            for f in gb["features"]:
                if "piura" in str(f["properties"].get("shapeName", "")).lower():
                    gb_area = area_km2(shape(f["geometry"]).buffer(0))
        except (httpx.HTTPError, ValueError):
            pass
    OUT.mkdir(parents=True, exist_ok=True)
    out_fc = {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": mapping(g),
                                                          "properties": {"name": "Piura", "admin_level": 4, "country": "PE"}}]}
    data = json.dumps(out_fc, separators=(",", ":")).encode()
    (OUT / "piura_department.geojson").write_bytes(data)
    meta = {"name": "Piura department (región Piura)", "source": "OpenStreetMap administrative boundary via Nominatim",
            "osm_type": props.get("osm_type"), "osm_id": props.get("osm_id"), "display_name": props.get("display_name"),
            "query": NOMINATIM, "retrieved_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "licence": "ODbL 1.0, © OpenStreetMap contributors", "simplification": "Nominatim polygon_threshold=0.0005 deg (~55 m)",
            "sha256": hashlib.sha256(data).hexdigest(), "area_km2": round(area_km2(g), 1), "bounds": [round(v, 5) for v in g.bounds],
            "cross_check": {"dataset": "geoBoundaries gbOpen PER ADM1 (Wikimedia Commons, 2008)", "area_km2": round(gb_area, 1) if gb_area else None}}
    (OUT / "piura_department.source.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
