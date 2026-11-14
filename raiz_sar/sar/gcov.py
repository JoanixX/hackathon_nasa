"""NISAR GCOV (Level-2 geocoded polarimetric covariance) reader built on h5py.

The reader discovers the bands, frequencies and covariance terms actually present instead of
assuming a fixed layout or S-band availability. Diagonal terms (e.g. HHHH) are linear power;
dB conversion is ``10*log10`` on positive, valid values only. The backscatter normalization is
read from product metadata when present and otherwise reported as unknown.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import h5py
import numpy as np

DIAGONAL_TERMS = ("HHHH", "HVHV", "VHVH", "VVVV", "RHRH", "RVRV")
MAX_WINDOW_PIXELS = 4_000_000


@dataclass
class FrequencyGrid:
    band: str
    frequency: str
    group: str
    terms: list[str]
    epsg: int | None
    x: np.ndarray
    y: np.ndarray
    spacing_x: float
    spacing_y: float
    has_mask: bool


@dataclass
class GcovInfo:
    path: str
    sha256: str
    granule_id: str | None
    start_time: str | None
    end_time: str | None
    product_version: str | None
    orbit_pass: str | None
    track: str | None
    frame: str | None
    normalization: str
    normalization_source: str
    synthetic_fixture: bool
    grids: list[FrequencyGrid] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            "path_name": Path(self.path).name, "sha256": self.sha256, "granule_id": self.granule_id,
            "start_time_utc": self.start_time, "end_time_utc": self.end_time, "product_version": self.product_version,
            "orbit_pass_direction": self.orbit_pass, "track": self.track, "frame": self.frame,
            "backscatter_normalization": self.normalization, "normalization_source": self.normalization_source,
            "synthetic_fixture": self.synthetic_fixture,
            "grids": [{"band": g.band, "frequency": g.frequency, "covariance_terms": g.terms, "epsg": g.epsg,
                       "spacing_x_m": g.spacing_x, "spacing_y_m": g.spacing_y, "shape": [len(g.y), len(g.x)],
                       "has_mask": g.has_mask} for g in self.grids],
        }


def _sha256(path: Path, limit_bytes: int | None = None) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        read = 0
        while chunk := fh.read(1 << 20):
            h.update(chunk)
            read += len(chunk)
            if limit_bytes and read >= limit_bytes:
                break
    return h.hexdigest()


def _scalar(ds) -> str | None:
    try:
        v = ds[()]
    except (TypeError, ValueError, KeyError, OSError):
        return None
    if isinstance(v, bytes):
        return v.decode("utf-8", "replace").strip()
    if isinstance(v, np.ndarray):
        if v.size == 1:
            v = v.reshape(-1)[0]
            return v.decode("utf-8", "replace").strip() if isinstance(v, bytes) else str(v)
        return None
    return str(v)


def _get(f: h5py.File, path: str) -> str | None:
    return _scalar(f[path]) if path in f else None


def _normalization(f: h5py.File, band: str) -> tuple[str, str]:
    """Look for an explicit backscatter normalization convention in product metadata."""
    found: list[tuple[str, str]] = []

    def visit(name: str, obj) -> None:
        low = name.lower()
        if isinstance(obj, h5py.Dataset) and ("normalization" in low or "backscatterconvention" in low) and obj.size <= 4:
            v = _scalar(obj)
            if v:
                found.append((name, v))

    root = f"/science/{band}"
    if root in f:
        f[root].visititems(visit)
    for name, value in found:
        v = value.lower()
        for key in ("gamma0", "sigma0", "beta0"):
            if key in v:
                return key, f"metadata:{name}"
    return "unknown", "no explicit normalization metadata found"


def inspect_gcov(path: str | Path) -> GcovInfo:
    path = Path(path)
    with h5py.File(path, "r") as f:
        bands = [b for b in ("LSAR", "SSAR") if f"/science/{b}" in f]
        if not bands:
            raise ValueError("No /science/LSAR or /science/SSAR group: not a NISAR product layout.")
        band = bands[0]
        ident = f"/science/{band}/identification"
        norm, norm_src = _normalization(f, band)
        info = GcovInfo(
            path=str(path), sha256=_sha256(path), granule_id=_get(f, f"{ident}/granuleId"),
            start_time=_get(f, f"{ident}/zeroDopplerStartTime"), end_time=_get(f, f"{ident}/zeroDopplerEndTime"),
            product_version=_get(f, f"{ident}/productVersion"), orbit_pass=_get(f, f"{ident}/orbitPassDirection"),
            track=_get(f, f"{ident}/trackNumber"), frame=_get(f, f"{ident}/frameNumber"),
            normalization=norm, normalization_source=norm_src,
            synthetic_fixture=bool(f.attrs.get("raiz_synthetic_fixture", 0)),
        )
        for b in bands:
            grids_path = f"/science/{b}/GCOV/grids"
            if grids_path not in f:
                continue
            for freq in sorted(k for k in f[grids_path].keys() if k.startswith("frequency")):
                g = f[f"{grids_path}/{freq}"]
                terms = [t for t in DIAGONAL_TERMS if t in g]
                if not terms or "xCoordinates" not in g or "yCoordinates" not in g:
                    continue
                x = np.asarray(g["xCoordinates"][()], dtype="float64")
                y = np.asarray(g["yCoordinates"][()], dtype="float64")
                epsg = None
                if "projection" in g:
                    epsg_attr = g["projection"].attrs.get("epsg_code")
                    if epsg_attr is not None:
                        epsg = int(np.asarray(epsg_attr).reshape(-1)[0])
                    else:
                        v = _scalar(g["projection"])
                        epsg = int(v) if v and v.isdigit() else None
                sx = float(x[1] - x[0]) if len(x) > 1 else math.nan
                sy = float(y[1] - y[0]) if len(y) > 1 else math.nan
                info.grids.append(FrequencyGrid(band=b, frequency=freq, group=g.name, terms=terms, epsg=epsg, x=x, y=y,
                                                spacing_x=sx, spacing_y=sy, has_mask="mask" in g))
    if not info.grids:
        raise ValueError("No GCOV grid with diagonal covariance terms and coordinates was found.")
    return info


def window_indices(coords: np.ndarray, lo: float, hi: float) -> tuple[int, int] | None:
    """Index range [i0, i1) of coordinate cells (centres) intersecting [lo, hi]; handles descending axes."""
    if len(coords) == 0 or not (math.isfinite(lo) and math.isfinite(hi)) or hi < lo:
        return None
    half = abs(coords[1] - coords[0]) / 2 if len(coords) > 1 else 0.0
    inside = np.nonzero((coords + half >= lo) & (coords - half <= hi))[0]
    if inside.size == 0:
        return None
    return int(inside.min()), int(inside.max()) + 1


def read_window(path: str | Path, grid: FrequencyGrid, term: str, bounds: tuple[float, float, float, float]):
    """Read a linear-power window and its validity mask for (minx, miny, maxx, maxy) in grid CRS."""
    ix = window_indices(grid.x, bounds[0], bounds[2])
    iy = window_indices(grid.y, bounds[1], bounds[3])
    if ix is None or iy is None:
        return None
    (c0, c1), (r0, r1) = ix, iy
    if (c1 - c0) * (r1 - r0) > MAX_WINDOW_PIXELS:
        raise ValueError("Requested window exceeds the pixel budget; reduce the AOI.")
    with h5py.File(path, "r") as f:
        g = f[grid.group]
        data = np.asarray(g[term][r0:r1, c0:c1], dtype="float64")
        valid = np.isfinite(data) & (data > 0)
        fill = g[term].attrs.get("_FillValue")
        if fill is not None:
            valid &= data != float(np.asarray(fill).reshape(-1)[0])
        if grid.has_mask:
            mask = np.asarray(g["mask"][r0:r1, c0:c1])
            valid &= (mask != 255) & (mask != 0)
    return {"linear": np.where(valid, data, np.nan), "valid": valid, "rows": (r0, r1), "cols": (c0, c1),
            "x": grid.x[c0:c1], "y": grid.y[r0:r1]}


def to_db(linear: np.ndarray) -> np.ndarray:
    out = np.full(linear.shape, np.nan, dtype="float64")
    ok = np.isfinite(linear) & (linear > 0)
    out[ok] = 10.0 * np.log10(linear[ok])
    return out


def quad_pol_rvi(hh: np.ndarray, hv: np.ndarray, vv: np.ndarray) -> np.ndarray:
    """Quad-pol radar vegetation index 8*HV/(HH+VV+2*HV) in linear power. NaN where undefined."""
    den = hh + vv + 2 * hv
    out = np.full(hh.shape, np.nan, dtype="float64")
    ok = np.isfinite(den) & (den > 0) & np.isfinite(hv) & (hv >= 0)
    out[ok] = 8 * hv[ok] / den[ok]
    return np.clip(out, 0, 1, out=out, where=np.isfinite(out))
