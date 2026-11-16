"""Free external sources: GIBS layer availability, NASA POWER rainfall and the ASF acquisition catalog.

All results are cached on disk under the runtime directory. Failures raise SourceUnavailable with a
plain message; nothing is filled with placeholder values.
"""

from __future__ import annotations

import contextvars
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

from . import perf, upstream
from .config import get_settings
from .upstream import UpstreamBusy, UpstreamError

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
    "dswx": {"id": "OPERA_L3_Dynamic_Surface_Water_Extent-HLS", "tms": "GoogleMapsCompatible_Level12", "max_zoom": 12,
             "ext": "png", "kind": "water", "title": "OPERA DSWx-HLS surface water (open and partial)", "sensor_res_m": 30},
    "imerg": {"id": "IMERG_Precipitation_Rate", "tms": "GoogleMapsCompatible_Level6", "max_zoom": 6,
              "ext": "png", "kind": "rain", "title": "GPM IMERG precipitation rate (daily)", "sensor_res_m": 10000},
    "viirs": {"id": "VIIRS_SNPP_CorrectedReflectance_TrueColor", "tms": "GoogleMapsCompatible_Level9", "max_zoom": 9,
              "ext": "jpg", "kind": "optical", "title": "VIIRS SNPP true colour (regional)", "sensor_res_m": 375},
}


class SourceUnavailable(UpstreamError):
    """A provider failed or returned unusable data (cached copies, if any, are served as stale)."""


_FAIL = (UpstreamError, httpx.HTTPError)


def _manifest_ttl(end: str, recent_s: int, archive_s: int):
    """Short TTL while a range is still being acquired/published; long once it is in the past; 10 min if incomplete."""
    def ttl(value: Any) -> int:
        if isinstance(value, dict) and value.get("probe_errors"):
            return 600
        recent = dt.date.fromisoformat(end) >= dt.date.today() - dt.timedelta(days=45)
        return recent_s if recent else archive_s
    return ttl


_client: httpx.Client | None = None


def http() -> httpx.Client:
    """One pooled HTTP client per process: keep-alive avoids a TLS handshake on every tile (~1 s each)."""
    global _client
    if _client is None:
        _client = httpx.Client(timeout=30, headers={"User-Agent": USER_AGENT},
                               limits=httpx.Limits(max_connections=32, max_keepalive_connections=16, keepalive_expiry=60))
    return _client


def _cache(name: str) -> Path:
    p = get_settings().runtime_dir / "cache" / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def lonlat_to_tile(lon: float, lat: float, z: int) -> tuple[int, int]:
    n = 2 ** z
    lat = max(-85.05, min(85.05, lat))
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n)
    return min(n - 1, max(0, x)), min(n - 1, max(0, y))


def gibs_tile_url(layer_key: str, date: str, z: int, x: int, y: int) -> str:
    L = LAYERS[layer_key]
    return f"{GIBS}/{L['id']}/default/{date}/{L['tms']}/{z}/{y}/{x}.{L['ext']}"


def _read_rgba(content: bytes) -> np.ndarray:
    """Decode a GIBS PNG/JPEG into RGBA uint8, expanding paletted images with their colormap."""
    import warnings

    from rasterio.errors import NotGeoreferencedWarning
    from rasterio.io import MemoryFile

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", NotGeoreferencedWarning)
        with MemoryFile(content) as m, m.open() as d:
            a = d.read()
            cmap = None
            try:
                cmap = d.colormap(1)
            except ValueError:
                cmap = None
    if cmap and a.shape[0] in (1, 2):
        lut = np.zeros((256, 4), dtype="uint8")
        for k, v in cmap.items():
            if 0 <= k < 256:
                lut[k] = v
        out = np.moveaxis(lut[a[0]], -1, 0)
        if a.shape[0] == 2:
            out[3] = np.minimum(out[3], a[1])
        return out
    if a.shape[0] == 1:
        a = np.repeat(a, 3, axis=0)
    if a.shape[0] == 2:  # grey + alpha
        a = np.concatenate([np.repeat(a[:1], 3, axis=0), a[1:2]])
    if a.shape[0] == 3:
        a = np.concatenate([a, np.full((1, *a.shape[1:]), 255, "uint8")])
    return a[:4]


def _valid_fraction(content: bytes) -> float:
    a = _read_rgba(content)
    data = a[:3].astype("int32").sum(0) > 0  # GIBS renders no-data as black in some SAR layers
    return float(((a[3] > 0) & data).mean())


def _probe(client: httpx.Client, layer_key: str, date: str, z: int, x: int, y: int) -> float | None:
    """Valid-pixel share of one tile/date; None when the provider failed (unknown, never cached as 0)."""
    key = ("probe", layer_key, date, z, x, y)
    path = _cache("gibs_probe") / (hashlib.sha256(repr(key).encode()).hexdigest()[:24] + ".json")
    if path.exists():
        return json.loads(path.read_text())["valid"]
    try:
        with perf.span("gibs.probe_fetch"):
            r = upstream.get(client, gibs_tile_url(layer_key, date, z, x, y))
    except UpstreamBusy:
        raise
    except UpstreamError:
        return None
    if r.status_code == 200 and r.content:
        valid = _valid_fraction(r.content)
    elif r.status_code in (400, 404):
        valid = 0.0
    else:
        # GIBS answers 5xx for some date/tile pairs: unknown now, not cached, reported as a probe error.
        perf.log({"evt": "gibs_error", "status": r.status_code, "layer": layer_key, "date": date})
        return None
    path.write_text(json.dumps({"valid": valid}))
    return valid


def _probe_all(layer_key: str, z: int, x: int, y: int, days: list[str], workers: int) -> list[float | None]:
    client = http()
    with ThreadPoolExecutor(workers) as ex:
        # copy_context per task keeps timing spans attached to the request
        return [f.result() for f in [ex.submit(contextvars.copy_context().run, _probe, client, layer_key, d, z, x, y) for d in days]]


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

    def build():
        fracs = _probe_all(layer_key, z, x, y, days, 8)
        errors = sum(f is None for f in fracs)
        if days and errors == len(days):
            raise SourceUnavailable("GIBS returned no usable answer for any date")
        dates = [{"date": d, "valid_fraction": round(f, 3)} for d, f in zip(days, fracs) if f is not None and f >= min_valid]
        return {"layer": layer_key, "gibs_id": LAYERS[layer_key]["id"], "probe_tile": [z, x, y], "checked_days": len(days),
                "min_valid_fraction": min_valid, "dates": dates, "probe_errors": errors,
                "note": "Valid pixels in the probe tile only; clouds in optical imagery are not masked by this check."
                        + (f" {errors} date(s) could not be checked (provider error) and are omitted." if errors else "")}

    # Date manifest per layer, probe tile (AOI) and time range, with explicit age.
    return upstream.manifest("dates", [layer_key, z, x, y, start, end, min_valid], _manifest_ttl(end, 6 * 3600, 7 * 86400), build, _FAIL)


def coverage(layer_key: str, lon: float, lat: float, dates: list[str]) -> dict[str, Any]:
    """Share of valid (non-black, non-transparent) pixels per date in the tile containing (lon, lat)."""
    if layer_key not in LAYERS:
        raise ValueError("unknown layer")
    if not dates or len(dates) > 70:
        raise ValueError("give 1..70 dates")
    for d in dates:
        dt.date.fromisoformat(d)
    z = min(LAYERS[layer_key]["max_zoom"], 10)
    x, y = lonlat_to_tile(lon, lat, z)

    def build():
        fracs = _probe_all(layer_key, z, x, y, dates, 6)
        errors = sum(f is None for f in fracs)
        if errors == len(dates):
            raise SourceUnavailable("GIBS returned no usable answer for any date")
        return {"layer": layer_key, "probe_tile": [z, x, y], "probe_errors": errors,
                "coverage": [{"date": d, "valid_fraction": None if f is None else round(f, 3)} for d, f in zip(dates, fracs)],
                "note": "Valid-pixel share of one probe tile around the point; black no-data is excluded. null = provider error (unknown)."}

    return upstream.manifest("coverage", [layer_key, z, x, y, sorted(dates)], _manifest_ttl(max(dates), 6 * 3600, 7 * 86400), build, _FAIL)


def _raw_tile(layer_key: str, date: str, z: int, x: int, y: int) -> bytes | None:
    """Raw GIBS tile bytes, cached on disk and shared by the map proxy and the analysis mosaics.

    Returns None for an empty answer (400/404: no data on that date); raises SourceUnavailable on 5xx.
    """
    path = _cache("gibs_raw") / layer_key / date / str(z) / str(x) / f"{y}.bin"
    if path.exists():
        with perf.span("gibs.raw_cache_hit"):
            data = path.read_bytes()
        return data or None
    with perf.span("gibs.fetch"):
        r = upstream.get(http(), gibs_tile_url(layer_key, date, z, x, y))
    if r.status_code in (400, 404) or (r.status_code == 200 and not r.content):
        data = b""
    elif r.status_code != 200:
        raise SourceUnavailable(f"GIBS returned HTTP {r.status_code}")  # not cached; asked again next time
    else:
        data = r.content
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{y}-{os.getpid()}-{time.time_ns()}.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)
    return data or None


def gibs_tile_transparent(layer_key: str, date: str, z: int, x: int, y: int) -> bytes:
    """Fetch a GIBS tile and make its black no-data pixels transparent (data pixels are unchanged)."""
    import warnings

    from rasterio.errors import NotGeoreferencedWarning
    from rasterio.io import MemoryFile

    L = LAYERS.get(layer_key)
    if L is None or L["kind"] not in ("sar", "optical", "water"):
        raise ValueError("unknown layer")
    dt.date.fromisoformat(date)
    if not (0 <= z <= L["max_zoom"] and 0 <= x < 2 ** z and 0 <= y < 2 ** z):
        raise ValueError("tile outside the layer's range")
    path = _cache("gibs_tiles") / layer_key / date / str(z) / str(x) / f"{y}.png"
    if path.exists():
        with perf.span("gibs.cache_hit"):
            return path.read_bytes()
    try:
        content = _raw_tile(layer_key, date, z, x, y)
    except UpstreamBusy:
        raise
    except (UpstreamError, httpx.HTTPError) as exc:
        raise SourceUnavailable(f"GIBS unreachable: {type(exc).__name__}") from exc
    if not content:
        a = np.zeros((4, 256, 256), dtype="uint8")
    else:
        a = _read_rgba(content).copy()
        a[3][a[:3].astype("int32").sum(0) == 0] = 0
        if layer_key == "dswx":
            # Paint only water: "not water" (white) becomes transparent; cloud (grey) stays faint = unknown.
            rgb = a[:3].astype("int32")
            a[3][(rgb[0] == 255) & (rgb[1] == 255) & (rgb[2] == 255)] = 0
            a[3][(rgb[0] == 175) & (rgb[1] == 175) & (rgb[2] == 175)] = 70
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


# DSWx-HLS classes as rendered by GIBS (colormap OPERA_Dynamic_Surface_Water_Extent.xml, v1.3):
# 0 not water (white), 1 open water (0,0,255), 2 partial surface water (180,213,244),
# 3 snow/ice (0,255,255), 4 cloud/cloud shadow (175,175,175), 255 no data (transparent).
DSWX_CLASSES = {(0, 0, 255): "open_water", (180, 213, 244): "partial_water", (255, 255, 255): "not_water",
                (175, 175, 175): "cloud", (0, 255, 255): "snow_ice"}


def ponding_sites(bounds: tuple[float, float, float, float], date: str, min_pixels: int = 3) -> dict[str, Any]:
    """Water polygons (open and partial surface water) from DSWx-HLS on one date, at the product's 30 m grid.

    Derived from the colour-coded GIBS rendering using the published colormap, so classes are exact.
    Clouds are reported separately: cloudy pixels are unknown, never "dry".
    """
    from rasterio.features import shapes
    from shapely.geometry import mapping as shp_mapping
    from shapely.geometry import shape as shp_shape

    w, s, e, n = bounds
    if not (-180 <= w < e <= 180 and -90 <= s < n <= 90) or (e - w) * (n - s) > 0.5:
        raise ValueError("bbox must be valid and at most 0.5 square degrees")
    dt.date.fromisoformat(date)

    def build():
        failed: list = []
        with perf.span("dswx.mosaic"):
            rgba, tf = fetch_gibs_mosaic("dswx", date, (w, s, e, n), 12, failed)
        if failed and len(failed) * 256 * 256 >= rgba.shape[1] * rgba.shape[2]:
            raise SourceUnavailable("GIBS returned no DSWx tile for this area and date")
        rgb = rgba[:3].astype("int32")
        valid = rgba[3] > 0
        cls = np.full(rgba.shape[1:], -1, dtype="int16")
        codes = {"open_water": 1, "partial_water": 2, "not_water": 0, "cloud": 4, "snow_ice": 3}
        for (r_, g_, b_), name in DSWX_CLASSES.items():
            cls[(rgb[0] == r_) & (rgb[1] == g_) & (rgb[2] == b_) & valid] = codes[name]
        counts = {k: int((cls == v).sum()) for k, v in codes.items()}
        water = ((cls == 1) | (cls == 2)).astype("uint8")
        feats = []
        from .geo import to_wgs84

        for geom, val in shapes(water, mask=water.astype(bool), transform=tf):
            g = shp_shape(geom)
            if g.area < min_pixels * (tf.a ** 2):
                continue
            g4326 = to_wgs84(g, "EPSG:3857").simplify(0.00005)
            if g4326.is_empty:
                continue
            feats.append({"type": "Feature", "geometry": _round_coords(shp_mapping(g4326)), "properties": {"class": "water", "area_m2": round(g.area / (1 / math.cos(math.radians((s + n) / 2))) ** 2)}})
        feats.sort(key=lambda f: -f["properties"]["area_m2"])
        observed = counts["open_water"] + counts["partial_water"] + counts["not_water"]
        return {"source": "OPERA L3 DSWx-HLS (NASA JPL) via NASA GIBS", "date": date, "evidence_class": "derived",
                "grid": "Web Mercator zoom 12 rendering of the 30 m product", "pixel_counts": counts,
                "cloud_fraction": round(counts["cloud"] / max(1, observed + counts["cloud"]), 3),
                "features": feats[:400], "tiles_failed": len(failed),
                "note": "Open and partial surface water on this date. Cloudy pixels are unknown, not dry. Optical product: complements the radar layers."}

    # Complete results are kept 7 days; a result with failed tiles (unknown areas) only 10 minutes.
    return upstream.manifest("dswx", ponding_key(bounds, date), lambda v: 600 if v.get("tiles_failed") else 7 * 86400, build, _FAIL)


def _round_coords(geom: dict[str, Any], nd: int = 6) -> dict[str, Any]:
    """Round GeoJSON coordinates to ~0.1 m (6 decimals): the source grid is 30 m, so nothing is lost."""
    def r(c):
        return [round(c[0], nd), round(c[1], nd)] if isinstance(c[0], (int, float)) else [r(x) for x in c]
    return {**geom, "coordinates": r(geom["coordinates"])}


def ponding_key(bounds: tuple[float, float, float, float], date: str) -> list:
    return [round(v, 4) for v in bounds] + [date]


def ponding_cached(bounds: tuple[float, float, float, float], date: str) -> dict[str, Any] | None:
    """The ponding result if it is already built (no external work); None otherwise."""
    return upstream.peek("dswx", ponding_key(bounds, date))


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
            with perf.span("power.fetch"):
                r = upstream.get(http(), url, timeout=60)
            r.raise_for_status()
            data = r.json()
        except UpstreamBusy:
            raise
        except (httpx.HTTPError, UpstreamError, ValueError) as exc:
            raise SourceUnavailable(f"NASA POWER unavailable: {type(exc).__name__}") from exc
        series = data["properties"]["parameter"]["PRECTOTCORR"]
        fill = data.get("header", {}).get("fill_value", -999)
        days = [{"date": f"{k[:4]}-{k[4:6]}-{k[6:]}", "mm": (None if v == fill else round(float(v), 2))} for k, v in sorted(series.items())]
        return {"source": "NASA POWER daily API, parameter PRECTOTCORR", "model": ", ".join(data.get("header", {}).get("sources", [])) or "unknown",
                "units": "mm/day", "evidence_class": "modeled", "point": [round(lon, 4), round(lat, 4)], "days": days,
                "note": "Reanalysis grid value (about 0.5° × 0.625°), not a rain-gauge observation at the zone."}

    return upstream.manifest("power", [round(lat, 3), round(lon, 3), start, end], _manifest_ttl(end, 12 * 3600, 30 * 86400), fetch, _FAIL)


def acquisitions(bbox: tuple[float, float, float, float], start: str, end: str) -> dict[str, Any]:
    """ASF catalog acquisition dates for NISAR GCOV and OPERA RTC-S1 over a bounding box."""
    w, s, e, n = bbox
    if not (-180 <= w < e <= 180 and -90 <= s < n <= 90) or (e - w) * (n - s) > 4:
        raise ValueError("bbox must be valid and at most 4 square degrees")

    def fetch():
        import asf_search as asf

        wkt = f"POLYGON(({w} {s},{e} {s},{e} {n},{w} {n},{w} {s}))"
        out = {}
        queries = (("nisar_gcov", dict(dataset="NISAR", processingLevel="GCOV")),
                   ("opera_rtc", dict(dataset="OPERA-S1", processingLevel="RTC")))

        def search(key, kw):
            try:
                with upstream.slot(), perf.span("asf.search", dataset=key):
                    return asf.search(intersectsWith=wkt, start=start, end=end, maxResults=500, **kw)
            except UpstreamBusy:
                raise
            except Exception as exc:  # catalog errors are reported, not simulated
                raise SourceUnavailable(f"ASF catalog unavailable: {type(exc).__name__}") from exc

        # Both catalog searches at once (they were sequential: ~2x the wall time).
        with ThreadPoolExecutor(2) as ex:
            futures = [(key, ex.submit(contextvars.copy_context().run, search, key, kw)) for key, kw in queries]
            results = [(key, f.result()) for key, f in futures]
        for key, res in results:
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

    return upstream.manifest("asf", [round(v, 3) for v in bbox] + [start, end], _manifest_ttl(end, 24 * 3600, 30 * 86400), fetch, _FAIL)


def fetch_gibs_mosaic(layer_key: str, date: str, bounds: tuple[float, float, float, float], z: int, failed: list | None = None):
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
    cells = [(tx, ty) for ty in range(y0, y1 + 1) for tx in range(x0, x1 + 1)]

    def one(tx: int, ty: int):
        try:
            return tx, ty, _raw_tile(layer_key, date, z, tx, ty)
        except SourceUnavailable:
            if failed is not None:
                failed.append((tx, ty))
            return tx, ty, None  # a failed tile stays transparent (unknown), never invented

    # Raw tiles are shared with the map proxy cache; the global upstream slots bound the fan-out.
    with ThreadPoolExecutor(6) as ex:
        for tx, ty, content in ex.map(lambda c: contextvars.copy_context().run(one, *c), cells):
            if content:
                tiles[:, (ty - y0) * 256:(ty - y0 + 1) * 256, (tx - x0) * 256:(tx - x0 + 1) * 256] = _read_rgba(content)
    R = 6378137.0
    world = 2 * math.pi * R
    size = world / 2 ** z
    left = -world / 2 + x0 * size
    top = world / 2 - y0 * size
    transform = tf_bounds(left, top - (y1 - y0 + 1) * size, left + (x1 - x0 + 1) * size, top, tiles.shape[2], tiles.shape[1])
    return tiles, transform
