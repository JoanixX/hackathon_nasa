"""Copernicus DEM GLO-30 access: windowed reads, Terrarium terrain tiles, slope statistics and AR heightmaps.

Copernicus DEM is a digital *surface* model (it includes canopy and buildings). Values are metres
above the EGM2008 geoid. One source feeds slope statistics, MapLibre terrain and the AR mesh so the
2D, 3D and AR views agree.
"""

from __future__ import annotations

import io
import math
import os
import threading
from functools import lru_cache
from pathlib import Path

import numpy as np
import rasterio
import rasterio.windows
from affine import Affine
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from rasterio.transform import from_bounds
from rasterio.warp import reproject
from rasterio.windows import from_bounds as window_from_bounds
from scipy.ndimage import map_coordinates
from shapely.geometry import mapping

from . import perf
from .config import get_settings
from .geo import to_metric, utm_epsg_for

SOURCE = "Copernicus DEM GLO-30 (DSM, EGM2008 heights), © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA"
BUCKET = "https://copernicus-dem-30m.s3.amazonaws.com"
NATIVE_DEG = 1 / 3600  # 1 arc-second
TERRAIN_MAX_ZOOM = 12
GDAL_ENV = dict(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
                VSI_CACHE="TRUE", GDAL_HTTP_TIMEOUT="30", GDAL_HTTP_MAX_RETRY="2", AWS_NO_SIGN_REQUEST="YES")
_lock = threading.Lock()


class TerrainUnavailable(Exception):
    pass


def tile_name(lat_floor: int, lon_floor: int) -> str:
    ns = f"{'N' if lat_floor >= 0 else 'S'}{abs(lat_floor):02d}"
    ew = f"{'E' if lon_floor >= 0 else 'W'}{abs(lon_floor):03d}"
    return f"Copernicus_DSM_COG_10_{ns}_00_{ew}_00_DEM"


def _local_dir() -> Path:
    return get_settings().runtime_dir / "cache" / "dem"


def tile_url(lat_floor: int, lon_floor: int) -> str:
    """Local copy when prefetched (fast), otherwise windowed HTTP reads from the public bucket."""
    n = tile_name(lat_floor, lon_floor)
    local = _local_dir() / f"{n}.tif"
    if local.exists():
        return str(local)
    return f"/vsicurl/{BUCKET}/{n}/{n}.tif"


def prefetch_region(bbox: list[float] | tuple[float, ...]) -> list[str]:
    """Download the 1° DEM cells covering bbox once (about 40 MB each); skips ocean and cached cells."""
    import httpx

    w, s, e, n = bbox
    done = []
    _local_dir().mkdir(parents=True, exist_ok=True)
    for lat in range(math.floor(s), math.ceil(n)):
        for lon in range(math.floor(w), math.ceil(e)):
            name = tile_name(lat, lon)
            dest = _local_dir() / f"{name}.tif"
            if dest.exists():
                done.append(name)
                continue
            tmp = dest.with_name(f".{name}.part")
            try:
                with httpx.stream("GET", f"{BUCKET}/{name}/{name}.tif", timeout=300) as r:
                    if r.status_code != 200:
                        continue  # ocean / not public: no data, nothing invented
                    with open(tmp, "wb") as fh:
                        for chunk in r.iter_bytes(1 << 20):
                            fh.write(chunk)
                os.replace(tmp, dest)
                _tile_exists.cache_clear()
                done.append(name)
            except httpx.HTTPError:
                if tmp.exists():
                    tmp.unlink()
    return done


@lru_cache(maxsize=64)
def _tile_exists(lat_floor: int, lon_floor: int) -> bool:
    try:
        with rasterio.Env(**GDAL_ENV), rasterio.open(tile_url(lat_floor, lon_floor)):
            return True
    except rasterio.errors.RasterioIOError:
        return False  # ocean or not-yet-public tile: no data, never invented


def read_dem(west: float, south: float, east: float, north: float, res_deg: float = NATIVE_DEG, cell_ok=None) -> tuple[np.ndarray, object, bool]:
    """Return (heights float32 with NaN nodata, transform in EPSG:4326, any_coverage).

    `cell_ok(lat, lon)` can skip 1° cells (map tiles skip cells outside every study region, which are
    not in the local cache and would otherwise be read remotely: a z7 tile took 78 s that way).
    """
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("invalid bounds")
    width = max(1, int(math.ceil((east - west) / res_deg)))
    height = max(1, int(math.ceil((north - south) / res_deg)))
    if width * height > 9_000_000:
        raise ValueError("DEM request too large; reduce the area or resolution")
    out = np.full((height, width), np.nan, dtype="float32")
    transform = from_bounds(west, south, west + width * res_deg, south + height * res_deg, width, height)
    covered = False
    with rasterio.Env(**GDAL_ENV):
        for lat in range(math.floor(south), math.ceil(north)):
            for lon in range(math.floor(west), math.ceil(east)):
                if cell_ok is not None and not cell_ok(lat, lon):
                    continue
                if not _tile_exists(lat, lon):
                    continue
                ds = _open_cell(lat, lon)
                win = window_from_bounds(max(west, lon), max(south, lat), min(east, lon + 1), min(north, lat + 1), ds.transform)
                win = win.round_offsets().round_lengths().intersection(rasterio.windows.Window(0, 0, ds.width, ds.height))
                if win.width < 1 or win.height < 1:
                    continue
                # Read at (about) the requested resolution: GDAL serves decimated reads from the COG
                # overviews instead of reading every native pixel (the main cost at low zooms).
                step = max(1.0, res_deg / NATIVE_DEG)
                ow, oh = max(1, int(math.ceil(win.width / step))), max(1, int(math.ceil(win.height / step)))
                src = ds.read(1, window=win, out_shape=(oh, ow), resampling=Resampling.bilinear).astype("float32")
                if ds.nodata is not None:
                    src[src == ds.nodata] = np.nan
                src_tf = ds.window_transform(win) * Affine.scale(win.width / ow, win.height / oh)
                tmp = np.full((height, width), np.nan, dtype="float32")
                reproject(src, tmp, src_transform=src_tf, src_crs="EPSG:4326", dst_transform=transform, dst_crs="EPSG:4326",
                          resampling=Resampling.bilinear, src_nodata=np.nan, dst_nodata=np.nan)
                sel = np.isfinite(tmp)
                out[sel] = tmp[sel]
                covered = covered or bool(sel.any())
    return out, transform, covered


_cells = threading.local()


def _open_cell(lat: int, lon: int):
    """Keep DEM datasets open per thread (rasterio datasets are not shared across threads)."""
    cache = getattr(_cells, "open", None)
    if cache is None:
        cache = _cells.open = {}
    url = tile_url(lat, lon)
    ds = cache.get((lat, lon))
    if ds is None or ds.name != url and not url.startswith("/vsicurl") and ds.name.startswith("/vsicurl"):
        if ds is not None:
            ds.close()  # a local copy has replaced the remote one
        ds = cache[(lat, lon)] = rasterio.open(url)
    return ds


# ---------------------------------------------------------------- web-mercator tiles

def tile_bounds(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    n = 2 ** z
    west = x / n * 360 - 180
    east = (x + 1) / n * 360 - 180
    north = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    south = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))))
    return west, south, east, north


def encode_terrarium(h: np.ndarray) -> np.ndarray:
    """Terrarium RGB encoding: height = R*256 + G + B/256 - 32768 (NaN encoded as sea level 0)."""
    v = np.where(np.isfinite(h), h, 0.0).astype("float64") + 32768.0
    v = np.clip(v, 0, 65535.996)
    r = np.floor(v / 256)
    g = np.floor(v - r * 256)
    b = np.floor((v - r * 256 - g) * 256)
    return np.stack([r, g, b]).astype("uint8")


def decode_terrarium(rgb: np.ndarray) -> np.ndarray:
    r, g, b = (rgb[i].astype("float64") for i in range(3))
    return r * 256 + g + b / 256 - 32768


_tile_slots = threading.BoundedSemaphore(4)  # bound concurrent remote COG reads


@lru_cache(maxsize=1)
def _regions() -> tuple[tuple[float, float, float, float], ...]:
    from .scenarios import get_scenario, scenario_ids

    return tuple(tuple(get_scenario(s)["summary"]["region_bbox"]) for s in scenario_ids() if get_scenario(s)["summary"].get("region_bbox"))


@lru_cache(maxsize=1)
def _region_shapes() -> tuple:
    """(bbox, prepared exact boundary or None) per scenario region."""
    from .region import boundary
    from .scenarios import get_scenario, scenario_ids

    out = []
    for s in scenario_ids():
        summ = get_scenario(s)["summary"]
        if summ.get("region_bbox"):
            out.append((tuple(summ["region_bbox"]), boundary(summ["region_boundary"])[1] if summ.get("region_boundary") else None))
    return tuple(out)


def _in_regions(b: tuple[float, float, float, float]) -> bool:
    """True when the box touches a study region (its exact boundary when one is stored)."""
    from shapely.geometry import box

    w, s, e, n = b
    for R, poly in _region_shapes():
        if w < R[2] and e > R[0] and s < R[3] and n > R[1] and (poly is None or poly.intersects(box(w, s, e, n))):
            return True
    return False


@lru_cache(maxsize=1)
def _flat_tile() -> bytes:
    import warnings

    from rasterio.errors import NotGeoreferencedWarning
    from rasterio.io import MemoryFile

    rgb = encode_terrarium(np.zeros((256, 256)))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", NotGeoreferencedWarning)
        with MemoryFile() as mf:
            with mf.open(driver="PNG", width=256, height=256, count=3, dtype="uint8") as d:
                d.write(rgb)
            return mf.read()
_tile_locks: dict[tuple[int, int, int], threading.Lock] = {}


def _tile_lock(z: int, x: int, y: int) -> threading.Lock:
    """One lock per tile: identical concurrent requests (terrain + hillshade) render it once."""
    with _lock:
        return _tile_locks.setdefault((z, x, y), threading.Lock())


def terrain_tile_png(z: int, x: int, y: int) -> bytes:
    if not (0 <= z <= TERRAIN_MAX_ZOOM and 0 <= x < 2 ** z and 0 <= y < 2 ** z):
        raise ValueError("tile outside the supported range")
    cache = get_settings().runtime_dir / "cache" / "terrain" / str(z) / str(x)
    path = cache / f"{y}.png"
    if path.exists():
        with perf.span("terrain.cache_hit"):
            return path.read_bytes()
    if not _in_regions(tile_bounds(z, x, y)):
        # Outside every study region: a flat sea-level tile, instantly, instead of remote reads.
        with perf.span("terrain.outside_region"):
            return _flat_tile()
    last: Exception | None = None
    with _tile_lock(z, x, y), _tile_slots:
        if path.exists():  # rendered by a concurrent request for the same tile
            return path.read_bytes()
        for attempt in range(3):  # transient HTTP failures from the public bucket are retried
            try:
                with perf.span("terrain.render", z=z):
                    return _render_tile(z, x, y, cache, path)
            except (rasterio.errors.RasterioIOError, OSError) as exc:
                last = exc
                import time

                time.sleep(0.5 * (attempt + 1))
    raise TerrainUnavailable(f"DEM read failed after retries: {type(last).__name__}")


def _render_tile(z: int, x: int, y: int, cache: Path, path: Path) -> bytes:
    west, south, east, north = tile_bounds(z, x, y)
    size = 256
    res = max(NATIVE_DEG, (east - west) / size)
    pad = 2 * res
    with perf.span("dem.read"):
        dem, tf, covered = read_dem(west - pad, max(-89.9, south - pad), east + pad, min(89.9, north + pad), res,
                                    cell_ok=lambda la, lo: _in_regions((lo, la, lo + 1, la + 1)))
    # Exact web-mercator sampling: each output row has its own latitude.
    n = 2 ** z
    ys = (y + (np.arange(size) + 0.5) / size) / n
    lats = np.degrees(np.arctan(np.sinh(np.pi * (1 - 2 * ys))))
    lons = west + (np.arange(size) + 0.5) / size * (east - west)
    lon_g, lat_g = np.meshgrid(lons, lats)
    cols = (lon_g - tf.c) / tf.a - 0.5
    rows = (lat_g - tf.f) / tf.e - 0.5
    filled = np.where(np.isfinite(dem), dem, 0.0)
    h = map_coordinates(filled, [rows, cols], order=1, mode="nearest")
    rgb = encode_terrarium(h)
    import warnings

    from rasterio.errors import NotGeoreferencedWarning
    from rasterio.io import MemoryFile

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", NotGeoreferencedWarning)
        with MemoryFile() as mf:
            with mf.open(driver="PNG", width=size, height=size, count=3, dtype="uint8") as dst:
                dst.write(rgb)
            data = mf.read()
    import tempfile

    cache.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=cache, prefix=f".{y}-", suffix=".tmp")  # unique per writer
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
    os.replace(tmp, path)
    return data


# ---------------------------------------------------------------- slope and heightmaps

def metric_dem(geom_lonlat, margin_m: float = 120.0, res_m: float = 30.0):
    """DEM reprojected to the area's UTM zone at `res_m`, covering the geometry plus a margin."""
    c = geom_lonlat.centroid
    crs = utm_epsg_for(c.x, c.y)
    gm = to_metric(geom_lonlat, crs)
    minx, miny, maxx, maxy = gm.bounds
    minx, miny, maxx, maxy = minx - margin_m, miny - margin_m, maxx + margin_m, maxy + margin_m
    w = int(math.ceil((maxx - minx) / res_m))
    h = int(math.ceil((maxy - miny) / res_m))
    if w * h > 4_000_000:
        raise ValueError("Area too large for slope analysis (limit about 3,600 km² at 30 m).")
    lw, ls, le, ln = geom_lonlat.buffer(0.01).bounds
    dem, tf, covered = read_dem(lw, ls, le, ln)
    if not covered:
        raise TerrainUnavailable("No Copernicus DEM coverage for this area.")
    out = np.full((h, w), np.nan, dtype="float32")
    dst_tf = from_bounds(minx, miny, minx + w * res_m, miny + h * res_m, w, h)
    reproject(dem, out, src_transform=tf, src_crs="EPSG:4326", dst_transform=dst_tf, dst_crs=crs,
              resampling=Resampling.bilinear, src_nodata=np.nan, dst_nodata=np.nan)
    return out, dst_tf, crs, gm


def slope_percent(dem: np.ndarray, res_m: float) -> np.ndarray:
    gy, gx = np.gradient(dem.astype("float64"), res_m)
    return (100.0 * np.hypot(gx, gy)).astype("float32")


def zone_terrain_stats(geom_lonlat) -> dict:
    with perf.span("dem.zone_window"):
        dem, tf, crs, gm = metric_dem(geom_lonlat)
    slope = slope_percent(dem, 30.0)
    inside = ~geometry_mask([mapping(gm)], out_shape=dem.shape, transform=tf, all_touched=False)
    if inside.sum() == 0:  # polygon thinner than one cell: use touched cells
        inside = ~geometry_mask([mapping(gm)], out_shape=dem.shape, transform=tf, all_touched=True)
    s = slope[inside & np.isfinite(slope)]
    e = dem[inside & np.isfinite(dem)]
    if s.size == 0:
        raise TerrainUnavailable("The zone has no valid DEM cells.")
    hist_edges = [0, 5, 15, 30, 60, 100, 1000]
    hist, _ = np.histogram(np.clip(s, 0, 999), bins=hist_edges)
    return {
        "source": SOURCE, "grid": f"{crs} at 30 m (resampled from 1 arc-second)", "cells": int(s.size),
        "slope_percent_median": round(float(np.median(s)), 1), "slope_percent_p10": round(float(np.percentile(s, 10)), 1),
        "slope_percent_p90": round(float(np.percentile(s, 90)), 1),
        "elevation_m_min": round(float(e.min()), 1), "elevation_m_max": round(float(e.max()), 1),
        "slope_histogram": {"edges_percent": hist_edges, "cells": [int(v) for v in hist]},
        "note": "Surface model: canopy and buildings raise heights. Slope is a terrain indicator, not a stability assessment.",
    }


def heightmap(metric_bounds: tuple[float, float, float, float], crs: str, nx: int = 72, ny: int = 52) -> dict:
    """Regular grid of DEM heights over metric bounds (row 0 = north) for the AR terrain mesh."""
    from .geo import to_wgs84
    from shapely.geometry import box

    minx, miny, maxx, maxy = metric_bounds
    lw, ls, le, ln = to_wgs84(box(minx, miny, maxx, maxy), crs).buffer(0.005).bounds
    dem, tf, covered = read_dem(lw, ls, le, ln)
    if not covered:
        raise TerrainUnavailable("No DEM coverage for the AR frame.")
    out = np.full((ny, nx), np.nan, dtype="float32")
    dst_tf = from_bounds(minx, miny, maxx, maxy, nx, ny)
    reproject(dem, out, src_transform=tf, src_crs="EPSG:4326", dst_transform=dst_tf, dst_crs=crs,
              resampling=Resampling.average, src_nodata=np.nan, dst_nodata=np.nan)
    finite = out[np.isfinite(out)]
    base = float(finite.min()) if finite.size else 0.0
    filled = np.where(np.isfinite(out), out, base)
    return {"nx": nx, "ny": ny, "min_m": round(base, 1), "max_m": round(float(filled.max()), 1),
            "heights_m": [round(float(v) - base, 1) for v in filled.ravel()], "source": SOURCE}


def flow_path(lon: float, lat: float, max_km: float = 8.0, res_m: float = 30.0) -> dict:
    """Downhill path on the Copernicus DEM from a start point: priority-flood + epsilon fill, then D8 steepest descent.

    The path never rises on the filled surface (it can cross a closed depression, which fills with water first:
    the raw-DEM rise inside depressions is reported). It traces where water and debris tend to run; it is a
    terrain path, not a debris-flow model (no volume, rheology or runout physics).
    """
    from shapely.geometry import LineString, Point

    from . import hydro
    from .geo import lonlat_to_metric, metric_to_lonlat

    if not (-180 <= lon <= 180 and -60 <= lat <= 60):
        raise ValueError("invalid start point")
    start = Point(lon, lat)
    half = max_km * 1000
    with perf.span("dem.flow_window"):
        dem, tf, crs, gm = metric_dem(start.buffer(half / 111_000), margin_m=0, res_m=res_m)
    h, w = dem.shape
    col, row = ~tf * lonlat_to_metric(lon, lat, crs)
    r, c = int(row), int(col)
    if not (0 <= r < h and 0 <= c < w) or not np.isfinite(dem[r, c]):
        raise TerrainUnavailable("No DEM value at the start point.")
    with perf.span("dem.flow_trace"):
        filled = hydro.priority_flood(dem, epsilon=1e-3)
        rec = hydro.d8_receivers(filled, res_m).ravel()
        path = [(r, c)]
        k = r * w + c
        limit = int(max_km * 1000 / res_m) * 2
        for _ in range(limit):
            k2 = int(rec[k])
            if k2 < 0:
                break
            k = k2
            path.append(divmod(k, w))
    pts_m = [tf * (cc + 0.5, rr + 0.5) for rr, cc in path]
    coords = [metric_to_lonlat(x, y, crs) for x, y in pts_m]
    elev = [round(float(dem[rr, cc]), 1) for rr, cc in path]
    fill_z = [float(filled[rr, cc]) for rr, cc in path]
    pond_rise = max([0.0] + [elev[i] - elev[i - 1] for i in range(1, len(elev))])
    line = LineString(pts_m) if len(pts_m) > 1 else None
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": [[round(x, 6), round(y, 6)] for x, y in coords]},
        "properties": {"length_m": round(line.length, 1) if line else 0.0, "drop_m": round(elev[0] - elev[-1], 1),
                       "start_elevation_m": elev[0], "end_elevation_m": elev[-1],
                       "monotone_on_filled_surface": all(fill_z[i] <= fill_z[i - 1] + 1e-9 for i in range(1, len(fill_z))),
                       "max_rise_inside_depressions_m": round(pond_rise, 2),
                       "elevations_m": elev[:: max(1, len(elev) // 200)], "grid": f"{crs} at {res_m:g} m",
                       "method": "priority-flood + epsilon (Barnes et al. 2014), D8 steepest descent (O'Callaghan & Mark 1984)",
                       "source": SOURCE,
                       "note": "Downhill terrain path. Not a debris-flow model: no volume or runout physics."},
    }


def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p
