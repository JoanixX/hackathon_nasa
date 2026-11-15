"""Free external sources: GIBS layer availability, NASA POWER rainfall and the ASF acquisition catalog.

All results are cached on disk under the runtime directory. Failures raise SourceUnavailable with a
plain message; nothing is filled with placeholder values.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import httpx
import numpy as np

from .config import get_settings

GIBS = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best"
USER_AGENT = "RAIZ-SAR-AI/1.0 (NASA Space Apps 2026 prototype)"

# Layers offered in the UI. max_zoom is the native tile-matrix level; resolution is metres/pixel at
# the equator for that level (GIBS GoogleMapsCompatible_LevelN), not the sensor's resolution.
LAYERS: dict[str, dict[str, Any]] = {
    "hls_s30": {"id": "HLS_S30_Nadir_BRDF_Adjusted_Reflectance", "tms": "GoogleMapsCompatible_Level12", "max_zoom": 12,
                "ext": "png", "kind": "optical", "title": "HLS Sentinel-2 (S30) true colour", "sensor_res_m": 30},
    "hls_l30": {"id": "HLS_L30_Nadir_BRDF_Adjusted_Reflectance", "tms": "GoogleMapsCompatible_Level12", "max_zoom": 12,
                "ext": "png", "kind": "optical", "title": "HLS Landsat (L30) true colour", "sensor_res_m": 30},
    "nisar_gcov": {"id": "NISAR_L2_Geocoded_Polarimetric_Covariance", "tms": "GoogleMapsCompatible_Level13", "max_zoom": 13,
                   "ext": "png", "kind": "sar", "title": "NISAR GCOV normalized backscatter (false colour)", "sensor_res_m": 20},
    "opera_rtc": {"id": "OPERA_L2_Radiometric_Terrain_Corrected_SAR_Sentinel-1", "tms": "GoogleMapsCompatible_Level12", "max_zoom": 12,
                  "ext": "png", "kind": "sar", "title": "Sentinel-1 OPERA RTC backscatter (C-band)", "sensor_res_m": 30},
    "imerg": {"id": "IMERG_Precipitation_Rate", "tms": "GoogleMapsCompatible_Level6", "max_zoom": 6,
              "ext": "png", "kind": "rain", "title": "GPM IMERG precipitation rate (daily)", "sensor_res_m": 10000},
    "viirs": {"id": "VIIRS_SNPP_CorrectedReflectance_TrueColor", "tms": "GoogleMapsCompatible_Level9", "max_zoom": 9,
              "ext": "jpg", "kind": "optical", "title": "VIIRS SNPP true colour (regional)", "sensor_res_m": 375},
}


class SourceUnavailable(Exception):
    pass


def _cache(name: str) -> Path:
    p = get_settings().runtime_dir / "cache" / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def _cached_json(kind: str, key: Any, ttl_s: int, fn):
    path = _cache(kind) / (hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()[:24] + ".json")
    if path.exists() and time.time() - path.stat().st_mtime < ttl_s:
        return json.loads(path.read_text(encoding="utf-8"))
    value = fn()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value), encoding="utf-8")
    os.replace(tmp, path)
    return value


def lonlat_to_tile(lon: float, lat: float, z: int) -> tuple[int, int]:
    n = 2 ** z
    lat = max(-85.05, min(85.05, lat))
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n)
    return min(n - 1, max(0, x)), min(n - 1, max(0, y))


def gibs_tile_url(layer_key: str, date: str, z: int, x: int, y: int) -> str:
    L = LAYERS[layer_key]
    return f"{GIBS}/{L['id']}/default/{date}/{L['tms']}/{z}/{y}/{x}.{L['ext']}"


def _valid_fraction(content: bytes) -> float:
    from rasterio.io import MemoryFile
    import warnings
    from rasterio.errors import NotGeoreferencedWarning

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", NotGeoreferencedWarning)
        with MemoryFile(content) as m, m.open() as d:
            a = d.read()
    data = a[:3].astype("int32").sum(0) > 0  # GIBS renders no-data as black in some SAR layers
    if a.shape[0] == 4:
        return float(((a[3] > 0) & data).mean())
    return float(data.mean())


def _probe(client: httpx.Client, layer_key: str, date: str, z: int, x: int, y: int) -> float:
    key = ("probe", layer_key, date, z, x, y)
    path = _cache("gibs_probe") / (hashlib.sha256(repr(key).encode()).hexdigest()[:24] + ".json")
    if path.exists():
        return json.loads(path.read_text())["valid"]
    r = client.get(gibs_tile_url(layer_key, date, z, x, y))
    if r.status_code == 200 and r.content:
        valid = _valid_fraction(r.content)
    elif r.status_code in (400, 404):
        valid = 0.0
    else:
        raise SourceUnavailable(f"GIBS returned HTTP {r.status_code}")
    path.write_text(json.dumps({"valid": valid}))
    return valid


def available_dates(layer_key: str, lon: float, lat: float, start: str, end: str, min_valid: float = 0.2,
                    max_days: int = 120) -> dict[str, Any]:
    """Dates on which a GIBS layer has pixels over the tile containing (lon, lat)."""
    if layer_key not in LAYERS:
        raise ValueError("unknown layer")
    d0, d1 = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    if d1 < d0 or (d1 - d0).days > max_days:
        raise ValueError(f"date range must be 0..{max_days} days")
    z = min(LAYERS[layer_key]["max_zoom"], 10)
    x, y = lonlat_to_tile(lon, lat, z)
    days = [(d0 + dt.timedelta(days=i)).isoformat() for i in range((d1 - d0).days + 1)]
    with httpx.Client(timeout=20, headers={"User-Agent": USER_AGENT}) as client, ThreadPoolExecutor(8) as ex:
        try:
            fracs = list(ex.map(lambda d: _probe(client, layer_key, d, z, x, y), days))
        except httpx.HTTPError as exc:
            raise SourceUnavailable(f"GIBS unreachable: {type(exc).__name__}") from exc
    dates = [{"date": d, "valid_fraction": round(f, 3)} for d, f in zip(days, fracs) if f >= min_valid]
    return {"layer": layer_key, "gibs_id": LAYERS[layer_key]["id"], "probe_tile": [z, x, y], "checked_days": len(days),
            "min_valid_fraction": min_valid, "dates": dates,
            "note": "Valid pixels in the probe tile only; clouds in optical imagery are not masked by this check."}


def coverage(layer_key: str, lon: float, lat: float, dates: list[str]) -> dict[str, Any]:
    """Share of valid (non-black, non-transparent) pixels per date in the tile containing (lon, lat)."""
    if layer_key not in LAYERS:
        raise ValueError("unknown layer")
    if not dates or len(dates) > 60:
        raise ValueError("give 1..60 dates")
    for d in dates:
        dt.date.fromisoformat(d)
    z = min(LAYERS[layer_key]["max_zoom"], 10)
    x, y = lonlat_to_tile(lon, lat, z)
    with httpx.Client(timeout=20, headers={"User-Agent": USER_AGENT}) as client, ThreadPoolExecutor(6) as ex:
        try:
            fracs = list(ex.map(lambda d: _probe(client, layer_key, d, z, x, y), dates))
        except httpx.HTTPError as exc:
            raise SourceUnavailable(f"GIBS unreachable: {type(exc).__name__}") from exc
    return {"layer": layer_key, "probe_tile": [z, x, y], "coverage": [{"date": d, "valid_fraction": round(f, 3)} for d, f in zip(dates, fracs)],
            "note": "Valid-pixel share of one probe tile around the point; black no-data is excluded."}


def gibs_tile_transparent(layer_key: str, date: str, z: int, x: int, y: int) -> bytes:
    """Fetch a GIBS tile and make its black no-data pixels transparent (data pixels are unchanged)."""
    import warnings

    from rasterio.errors import NotGeoreferencedWarning
    from rasterio.io import MemoryFile

    L = LAYERS.get(layer_key)
    if L is None or L["kind"] not in ("sar", "optical"):
        raise ValueError("unknown layer")
    dt.date.fromisoformat(date)
    if not (0 <= z <= L["max_zoom"] and 0 <= x < 2 ** z and 0 <= y < 2 ** z):
        raise ValueError("tile outside the layer's range")
    path = _cache("gibs_tiles") / layer_key / date / str(z) / str(x) / f"{y}.png"
    if path.exists():
        return path.read_bytes()
    try:
        r = httpx.get(gibs_tile_url(layer_key, date, z, x, y), timeout=30, headers={"User-Agent": USER_AGENT})
    except httpx.HTTPError as exc:
        raise SourceUnavailable(f"GIBS unreachable: {type(exc).__name__}") from exc
    if r.status_code in (400, 404) or not r.content:
        a = np.zeros((4, 256, 256), dtype="uint8")
    elif r.status_code != 200:
        raise SourceUnavailable(f"GIBS returned HTTP {r.status_code}")
    else:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", NotGeoreferencedWarning)
            with MemoryFile(r.content) as m, m.open() as d:
                a = d.read()
        if a.shape[0] == 3:
            a = np.concatenate([a, np.full((1, *a.shape[1:]), 255, "uint8")])
        a = a[:4].copy()
        a[3][a[:3].astype("int32").sum(0) == 0] = 0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", NotGeoreferencedWarning)
        with MemoryFile() as mf:
            with mf.open(driver="PNG", width=a.shape[2], height=a.shape[1], count=4, dtype="uint8") as dst:
                dst.write(a)
            data = mf.read()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{y}-{os.getpid()}-{time.time_ns()}.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)
    return data


def rainfall(lat: float, lon: float, start: str, end: str) -> dict[str, Any]:
    """NASA POWER daily corrected precipitation (MERRA-2 reanalysis, mm/day) at a point."""
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("invalid coordinates")
    d0, d1 = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    if d1 < d0 or (d1 - d0).days > 731:
        raise ValueError("date range must be 0..731 days")

    def fetch():
        url = ("https://power.larc.nasa.gov/api/temporal/daily/point?parameters=PRECTOTCORR&community=AG"
               f"&longitude={lon:.4f}&latitude={lat:.4f}&start={d0:%Y%m%d}&end={d1:%Y%m%d}&format=JSON")
        try:
            r = httpx.get(url, timeout=60, headers={"User-Agent": USER_AGENT})
            r.raise_for_status()
            data = r.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise SourceUnavailable(f"NASA POWER unavailable: {type(exc).__name__}") from exc
        series = data["properties"]["parameter"]["PRECTOTCORR"]
        fill = data.get("header", {}).get("fill_value", -999)
        days = [{"date": f"{k[:4]}-{k[4:6]}-{k[6:]}", "mm": (None if v == fill else round(float(v), 2))} for k, v in sorted(series.items())]
        return {"source": "NASA POWER daily API, parameter PRECTOTCORR", "model": ", ".join(data.get("header", {}).get("sources", [])) or "unknown",
                "units": "mm/day", "evidence_class": "modeled", "point": [round(lon, 4), round(lat, 4)], "days": days,
                "note": "Reanalysis grid value (about 0.5° × 0.625°), not a rain-gauge observation at the zone."}

    return _cached_json("power", [round(lat, 3), round(lon, 3), start, end], 12 * 3600, fetch)


def acquisitions(bbox: tuple[float, float, float, float], start: str, end: str) -> dict[str, Any]:
    """ASF catalog acquisition dates for NISAR GCOV and OPERA RTC-S1 over a bounding box."""
    w, s, e, n = bbox
    if not (-180 <= w < e <= 180 and -90 <= s < n <= 90) or (e - w) * (n - s) > 4:
        raise ValueError("bbox must be valid and at most 4 square degrees")

    def fetch():
        import asf_search as asf

        wkt = f"POLYGON(({w} {s},{e} {s},{e} {n},{w} {n},{w} {s}))"
        out = {}
        for key, kw in (("nisar_gcov", dict(dataset="NISAR", processingLevel="GCOV")),
                        ("opera_rtc", dict(dataset="OPERA-S1", processingLevel="RTC"))):
            try:
                res = asf.search(intersectsWith=wkt, start=start, end=end, maxResults=500, **kw)
            except Exception as exc:  # catalog errors are reported, not simulated
                raise SourceUnavailable(f"ASF catalog unavailable: {type(exc).__name__}") from exc
            by_date: dict[str, dict] = {}
            for r in res:
                p = r.properties
                d = (p.get("startTime") or "")[:10]
                ent = by_date.setdefault(d, {"date": d, "granules": 0, "tracks": set(), "directions": set()})
                ent["granules"] += 1
                ent["tracks"].add(p.get("pathNumber"))
                ent["directions"].add(p.get("flightDirection"))
            out[key] = [{"date": v["date"], "granules": v["granules"], "tracks": sorted(t for t in v["tracks"] if t is not None),
                         "directions": sorted(x for x in v["directions"] if x)} for v in sorted(by_date.values(), key=lambda z: z["date"])]
        return {"source": "ASF catalog (asf_search)", "bbox": [w, s, e, n], "start": start, "end": end, "datasets": out,
                "note": "Catalog listing only: acquisitions intersecting the box; coverage of every pixel is not implied."}

    return _cached_json("asf", [round(v, 3) for v in bbox] + [start, end], 6 * 3600, fetch)


def fetch_gibs_mosaic(layer_key: str, date: str, bounds: tuple[float, float, float, float], z: int):
    """RGBA mosaic of GIBS tiles at zoom z covering lon/lat bounds; returns (array[4,H,W], mercator transform)."""
    from rasterio.io import MemoryFile
    from rasterio.transform import from_bounds as tf_bounds
    import warnings
    from rasterio.errors import NotGeoreferencedWarning

    w, s, e, n = bounds
    x0, y0 = lonlat_to_tile(w, n, z)
    x1, y1 = lonlat_to_tile(e, s, z)
    if (x1 - x0 + 1) * (y1 - y0 + 1) > 64:
        raise ValueError("area too large for imagery mosaic")
    tiles = np.zeros((4, (y1 - y0 + 1) * 256, (x1 - x0 + 1) * 256), dtype="uint8")
    with httpx.Client(timeout=30, headers={"User-Agent": USER_AGENT}) as client:
        for ty in range(y0, y1 + 1):
            for tx in range(x0, x1 + 1):
                r = client.get(gibs_tile_url(layer_key, date, z, tx, ty))
                if r.status_code != 200 or not r.content:
                    continue
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", NotGeoreferencedWarning)
                    with MemoryFile(r.content) as m, m.open() as d:
                        a = d.read()
                if a.shape[0] == 3:
                    a = np.concatenate([a, np.full((1, *a.shape[1:]), 255, "uint8")])
                tiles[:, (ty - y0) * 256:(ty - y0 + 1) * 256, (tx - x0) * 256:(tx - x0 + 1) * 256] = a[:4]
    R = 6378137.0
    world = 2 * math.pi * R
    size = world / 2 ** z
    left = -world / 2 + x0 * size
    top = world / 2 - y0 * size
    transform = tf_bounds(left, top - (y1 - y0 + 1) * size, left + (x1 - x0 + 1) * size, top, tiles.shape[2], tiles.shape[1])
    return tiles, transform
