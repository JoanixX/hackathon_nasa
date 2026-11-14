"""GCOV window -> masked dB layers -> zonal sector statistics -> COG + map preview + manifest.

Outputs are derived evidence for specialist assessment. They do not retrieve buried moisture,
dielectric constant, survival or root reinforcement.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.errors import NotGeoreferencedWarning
from rasterio.features import geometry_mask
from rasterio.transform import from_origin
from rasterio.warp import calculate_default_transform, reproject
from shapely.geometry import box, mapping, shape

from ..geo import to_metric, union_bounds
from .gcov import inspect_gcov, quad_pol_rvi, read_window, to_db

ALGORITHM_VERSION = "gcov-zonal-1"
DB_RANGE = (-30.0, 0.0)  # fixed preview stretch so dates remain visually comparable


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_cog(path: Path, arr: np.ndarray, transform, epsg: int) -> None:
    profile = dict(driver="COG", width=arr.shape[1], height=arr.shape[0], count=1, dtype="float32",
                   crs=CRS.from_epsg(epsg), transform=transform, nodata=float("nan"), compress="deflate")
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(arr.astype("float32"), 1)


def _preview_png(path: Path, db: np.ndarray, transform, epsg: int) -> list[list[float]]:
    src_crs, dst_crs = CRS.from_epsg(epsg), CRS.from_epsg(4326)
    h, w = db.shape
    left, top = transform.c, transform.f
    right, bottom = left + transform.a * w, top + transform.e * h
    dt_, dw, dh = calculate_default_transform(src_crs, dst_crs, w, h, left, bottom, right, top)
    out = np.full((dh, dw), np.nan, dtype="float32")
    reproject(db.astype("float32"), out, src_transform=transform, src_crs=src_crs, dst_transform=dt_, dst_crs=dst_crs,
              resampling=Resampling.nearest, src_nodata=np.nan, dst_nodata=np.nan)
    lo, hi = DB_RANGE
    norm = np.clip((out - lo) / (hi - lo), 0, 1)
    ok = np.isfinite(out)
    # Perceptual dark-blue -> cyan -> pale-yellow ramp; transparent where invalid.
    r = np.where(ok, 20 + 220 * norm ** 1.6, 0)
    g = np.where(ok, 40 + 200 * norm, 0)
    b = np.where(ok, 90 + 120 * (1 - abs(norm - 0.5) * 2) + 30 * (1 - norm), 0)
    a = np.where(ok, 200, 0)
    rgba = np.stack([r, g, b, a]).astype("uint8")
    # The PNG is a display overlay; its lon/lat bounds are returned explicitly, so no geotransform.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", NotGeoreferencedWarning)
        with rasterio.open(path, "w", driver="PNG", width=dw, height=dh, count=4, dtype="uint8") as dst:
            dst.write(rgba)
    west, north = dt_.c, dt_.f
    east, south = west + dt_.a * dw, north + dt_.e * dh
    return [[south, west], [north, east]]


def _stat(values: np.ndarray) -> dict[str, Any]:
    v = values[np.isfinite(values)]
    if v.size == 0:
        return {"median": None, "p10": None, "p90": None, "valid_pixels": 0}
    return {"median": round(float(np.median(v)), 3), "p10": round(float(np.percentile(v, 10)), 3),
            "p90": round(float(np.percentile(v, 90)), 3), "valid_pixels": int(v.size)}


def process_gcov(gcov_path: Path, scenario: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    info = inspect_gcov(gcov_path)
    grid = next((g for g in info.grids if g.band == "LSAR"), info.grids[0])
    if grid.epsg is None:
        raise ValueError("Product grid has no EPSG code; cannot georeference safely.")
    crs = f"EPSG:{grid.epsg}"
    feats = scenario["sectors"]["features"]
    geoms = {f["properties"]["sector_id"]: to_metric(shape(f["geometry"]), crs) for f in feats}
    minx, miny, maxx, maxy = union_bounds(geoms.values())
    pad = 100.0
    bounds = (minx - pad, miny - pad, maxx + pad, maxy + pad)
    run_id = hashlib.sha256(f"{info.sha256}:{scenario['summary']['dataset_version']}:{ALGORITHM_VERSION}".encode()).hexdigest()[:16]
    run_dir = out_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    layers: dict[str, Any] = {}
    linear: dict[str, np.ndarray] = {}
    transform = None
    for term in grid.terms:
        w = read_window(gcov_path, grid, term, bounds)
        if w is None:
            continue
        linear[term] = w["linear"]
        xs, ys = w["x"], w["y"]
        sx = abs(grid.spacing_x)
        sy = abs(grid.spacing_y)
        transform = from_origin(float(xs[0] - sx / 2), float(ys[0] + sy / 2), sx, sy)
        if grid.spacing_y > 0:  # south-up grid: flip to north-up for GeoTIFF
            linear[term] = linear[term][::-1]
            transform = from_origin(float(xs[0] - sx / 2), float(ys[-1] + sy / 2), sx, sy)
        db = to_db(linear[term])
        cog = run_dir / f"{term}_db.tif"
        _write_cog(cog, db, transform, grid.epsg)
        png = run_dir / f"{term}_db_preview.png"
        bounds_ll = _preview_png(png, db, transform, grid.epsg)
        layers[term] = {"cog": cog.name, "preview_png": png.name, "preview_bounds_latlon": bounds_ll,
                        "unit": "dB", "valid_fraction": round(float(np.isfinite(db).mean()), 4),
                        "cog_sha256": _sha(cog)}
    if not linear:
        raise ValueError("The product does not cover the scenario AOI.")

    rvi_status = "not_computed: quad-pol RVI requires HH, HV and VV linear power"
    rvi = None
    if {"HHHH", "HVHV", "VVVV"} <= set(linear):
        rvi = quad_pol_rvi(linear["HHHH"], linear["HVHV"], linear["VVVV"])
        rvi_status = "computed: 8*HV/(HH+VV+2*HV) in linear power"

    sectors = []
    shape_hw = next(iter(linear.values())).shape
    for sid, g in geoms.items():
        m = ~geometry_mask([mapping(g)], out_shape=shape_hw, transform=transform, all_touched=False)
        row: dict[str, Any] = {"sector_id": sid, "pixels_in_polygon": int(m.sum())}
        for term, arr in linear.items():
            row[f"{term}_db"] = _stat(to_db(arr)[m])
        row["rvi"] = _stat(rvi[m]) if rvi is not None else None
        n_valid = row[f"{grid.terms[0]}_db"]["valid_pixels"] if f"{grid.terms[0]}_db" in row else 0
        row["valid_coverage_fraction"] = round(n_valid / row["pixels_in_polygon"], 4) if row["pixels_in_polygon"] else 0.0
        row["coverage_status"] = ("unknown_coverage" if row["valid_coverage_fraction"] < 0.5 else "covered")
        sectors.append(row)

    manifest = {
        "manifest_version": "1",
        "run_id": run_id,
        "algorithm_version": ALGORITHM_VERSION,
        "scenario_id": scenario["summary"]["scenario_id"],
        "dataset_version": scenario["summary"]["dataset_version"],
        "data_mode": "synthetic_fixture" if info.synthetic_fixture else "real",
        "evidence_class": "derived",
        "product": info.summary(),
        "band": grid.band, "frequency": grid.frequency, "crs": crs,
        "grid_spacing_m": [abs(grid.spacing_x), abs(grid.spacing_y)],
        "note_spacing": "Grid spacing is not effective resolution; speckle is not filtered.",
        "layers": layers,
        "rvi_status": rvi_status,
        "s_band_available": any(g.band == "SSAR" for g in info.grids),
        "sectors": sectors,
        "interpretation_limits": [
            "Backscatter is not a direct measurement of underground moisture depth or dielectric constant.",
            "No survival, root reinforcement or slope-stability inference is made from these values.",
            "Compare acquisitions only with matching band, polarization, geometry and normalization.",
        ],
        "processed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }
    if not (math.isfinite(grid.spacing_x) and math.isfinite(grid.spacing_y)):
        raise ValueError("Invalid grid spacing.")
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=1, allow_nan=False), encoding="utf-8")
    return manifest


def aoi_wkt(scenario: dict[str, Any]) -> str:
    b = union_bounds(shape(f["geometry"]) for f in scenario["sectors"]["features"])
    return box(*b).wkt
