"""Terrain hydrology and debris-flow (huayco) geomorphometry on the Copernicus DEM (pure numpy + scipy).

Methods (each output names its method):
- Depression filling: priority-flood (Barnes, Lehman & Mulla 2014, Computers & Geosciences 62:117-127).
  Fill depth = filled - original: closed depressions where runoff collects (ponding potential).
- Flow direction D8 (O'Callaghan & Mark 1984) on the filled surface; flow accumulation = number of upslope cells.
- Topographic Wetness Index TWI = ln(a / tan(beta)), a = specific catchment area (Beven & Kirkby 1979). Relative index.
- Melton ruggedness number R = H_b / sqrt(A_b) (Melton 1965), with the basin-type classes of Wilford et al. 2004
  (Landslides 1:61-66): debris-flow prone when R > 0.6 (and channel length < 2.7 km), debris flood 0.3-0.6, flood < 0.3.
- Ravine (quebrada) support: a mapped OSM waterway near the point AND the DEM steepest-descent path from the point
  following that waterway. Tolerance = one DEM cell diagonal (source scale), not a pixel guess.

Copernicus DEM GLO-30 is a surface model (includes buildings/canopy); its stated absolute vertical accuracy is < 4 m
(LE90). Depressions shallower than that are reported but flagged as within the DEM's uncertainty.
"""

from __future__ import annotations

import heapq
import math
from typing import Any

import numpy as np

D8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
DEM_VERTICAL_LE90_M = 4.0
WILFORD = {"debris_flow": 0.6, "debris_flood": 0.3}


def priority_flood(dem: np.ndarray, epsilon: float = 0.0) -> np.ndarray:
    """Fill depressions so every cell drains to the edge (NaN cells act as outlets).

    With ``epsilon`` > 0 (priority-flood + epsilon, Barnes et al. 2014) filled flats get a tiny gradient towards
    their outlet, so steepest descent never stalls on a flat and never goes uphill on the filled surface."""
    h, w = dem.shape
    filled = np.where(np.isfinite(dem), dem, -np.inf).astype("float64")
    closed = np.zeros((h, w), dtype=bool)
    pq: list[tuple[float, int, int]] = []
    for r in range(h):
        for c in range(w):
            if r in (0, h - 1) or c in (0, w - 1) or not np.isfinite(dem[r, c]):
                heapq.heappush(pq, (filled[r, c], r, c))
                closed[r, c] = True
    while pq:
        z, r, c = heapq.heappop(pq)
        for dr, dc in D8:
            rr, cc = r + dr, c + dc
            if 0 <= rr < h and 0 <= cc < w and not closed[rr, cc]:
                closed[rr, cc] = True
                if filled[rr, cc] <= z:
                    filled[rr, cc] = z + epsilon if epsilon else max(filled[rr, cc], z)
                heapq.heappush(pq, (filled[rr, cc], rr, cc))
    return np.where(np.isfinite(dem), filled, np.nan)


def d8_receivers(filled: np.ndarray, res_m: float) -> np.ndarray:
    """Index of the steepest-descent neighbour for each cell (-1 = outlet/flat)."""
    h, w = filled.shape
    z = np.where(np.isfinite(filled), filled, np.inf)
    best = np.zeros((h, w))
    rec = np.full((h, w), -1, dtype=np.int64)
    pad = np.pad(z, 1, constant_values=-np.inf)  # edges drain outward
    for dr, dc in D8:
        nb = pad[1 + dr:1 + dr + h, 1 + dc:1 + dc + w]
        dist = res_m * (math.sqrt(2) if dr and dc else 1)
        drop = (z - nb) / dist
        better = drop > best
        best = np.where(better, drop, best)
        rr = np.clip(np.arange(h)[:, None] + dr, -1, h)
        cc = np.clip(np.arange(w)[None, :] + dc, -1, w)
        inside = (rr >= 0) & (rr < h) & (cc >= 0) & (cc < w)
        idx = np.where(inside, rr * w + cc, -1)
        rec = np.where(better, idx, rec)
    return rec


def accumulation(filled: np.ndarray, rec: np.ndarray) -> np.ndarray:
    """Upslope cell count including the cell itself (topological order = descending elevation)."""
    h, w = filled.shape
    acc = np.ones(h * w, dtype="float64")
    order = np.argsort(-np.where(np.isfinite(filled), filled, -np.inf), axis=None, kind="stable")
    r = rec.ravel()
    for i in order:
        j = r[i]
        if j >= 0:
            acc[j] += acc[i]
    return acc.reshape(h, w)


def slope_rad(dem: np.ndarray, res_m: float) -> np.ndarray:
    gy, gx = np.gradient(np.where(np.isfinite(dem), dem, np.nanmean(dem)), res_m)
    return np.arctan(np.hypot(gx, gy))


def twi(acc: np.ndarray, slope: np.ndarray, res_m: float) -> np.ndarray:
    a = acc * res_m  # specific catchment area: contributing area per unit contour width (m^2/m)
    return np.log(a / np.maximum(np.tan(slope), 1e-3))


def upstream_mask(rec: np.ndarray, outlet: int) -> np.ndarray:
    """Cells draining to the outlet (inverse receiver graph, breadth-first)."""
    n = rec.size
    r = rec.ravel()
    donors: dict[int, list[int]] = {}
    for i in np.nonzero(r >= 0)[0]:
        donors.setdefault(int(r[i]), []).append(int(i))
    seen = np.zeros(n, dtype=bool)
    stack = [outlet]
    seen[outlet] = True
    while stack:
        k = stack.pop()
        for d in donors.get(k, ()):
            if not seen[d]:
                seen[d] = True
                stack.append(d)
    return seen.reshape(rec.shape)


def melton(dem: np.ndarray, basin: np.ndarray, res_m: float, outlet_rc: tuple[int, int]) -> dict[str, Any]:
    area_km2 = float(basin.sum()) * res_m * res_m / 1e6
    z = dem[basin & np.isfinite(dem)]
    if z.size == 0 or area_km2 <= 0:
        return {"basin_area_km2": area_km2, "relief_m": None, "melton_ratio": None, "class": "unknown"}
    relief_m = float(z.max() - dem[outlet_rc])
    R = (relief_m / 1000.0) / math.sqrt(area_km2)
    cls = "debris_flow_prone" if R > WILFORD["debris_flow"] else "debris_flood" if R > WILFORD["debris_flood"] else "flood"
    return {"basin_area_km2": round(area_km2, 4), "relief_m": round(relief_m, 1), "melton_ratio": round(R, 3), "class": cls,
            "method": "Melton (1965) ruggedness; classes after Wilford et al. (2004)"}


def depressions(dem: np.ndarray, filled: np.ndarray, res_m: float) -> dict[str, Any]:
    from scipy import ndimage

    depth = np.where(np.isfinite(dem), filled - dem, 0.0)
    m = depth > 0.01
    lab, n = ndimage.label(m, structure=np.ones((3, 3), bool))
    out = []
    for k in range(1, n + 1):
        sel = lab == k
        d = depth[sel]
        out.append({"cells": int(sel.sum()), "area_m2": round(float(sel.sum()) * res_m * res_m, 1), "max_depth_m": round(float(d.max()), 2),
                    "volume_m3": round(float(d.sum()) * res_m * res_m, 1), "within_dem_uncertainty": bool(d.max() < DEM_VERTICAL_LE90_M)})
    out.sort(key=lambda x: -x["volume_m3"])
    return {"count": n, "depressions": out[:50], "label": lab, "depth": depth}


def upstream_stats(dem: np.ndarray, filled: np.ndarray, rec: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """For every cell, in one pass: highest elevation of its upslope basin, and whether that basin reaches the grid edge.

    Cells are processed from high to low on the filled surface, pushing values to their receiver (same order as
    :func:`accumulation`), so Melton relief and truncation for any outlet are read in O(1)."""
    h, w = filled.shape
    zmax = np.where(np.isfinite(dem), dem, -np.inf).ravel().copy()
    edge = np.zeros(h * w, dtype=bool)
    edge.reshape(h, w)[[0, -1], :] = True
    edge.reshape(h, w)[:, [0, -1]] = True
    order = np.argsort(-np.where(np.isfinite(filled), filled, -np.inf), axis=None, kind="stable")
    r = rec.ravel()
    for i in order:
        j = r[i]
        if j >= 0:
            if zmax[i] > zmax[j]:
                zmax[j] = zmax[i]
            if edge[i]:
                edge[j] = True
    return zmax.reshape(h, w), edge.reshape(h, w)
