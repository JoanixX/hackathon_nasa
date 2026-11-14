"""SYNTHETIC GCOV-like HDF5 fixtures for independent development and tests.

Files follow the GCOV group layout used by the reader but contain generated values. They are
marked with the root attribute ``raiz_synthetic_fixture = 1`` and a ``SYNTHETIC_FIXTURE`` granule
identifier; every derived artifact inherits that label. They never satisfy a real-data gate.
"""

from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np
from shapely.geometry import shape

from ..geo import to_metric, union_bounds

ACQUISITIONS = {
    "baseline": ("2026-01-10T10:41:12Z", 0.0),
    "post_rainfall": ("2026-03-17T10:41:09Z", 1.0),
}


def write_synthetic_gcov(path: Path, scenario: dict, acquisition: str, spacing_m: float = 20.0, seed: int = 7) -> Path:
    if acquisition not in ACQUISITIONS:
        raise ValueError("unknown synthetic acquisition")
    start, wet = ACQUISITIONS[acquisition]
    crs = scenario["summary"]["metric_crs"]
    epsg = int(crs.split(":")[1])
    geoms = [to_metric(shape(f["geometry"]), crs) for f in scenario["sectors"]["features"]]
    minx, miny, maxx, maxy = union_bounds(geoms)
    pad = 300.0
    x = np.arange(minx - pad, maxx + pad, spacing_m) + spacing_m / 2
    y = np.arange(maxy + pad, miny - pad, -spacing_m) - spacing_m / 2  # north-up, descending
    xx, yy = np.meshgrid(x, y)
    rng = np.random.default_rng(seed + (1 if wet else 0))
    # Smooth synthetic pattern plus multiplicative speckle-like noise (gamma distributed, 4 looks).
    base_hh = 0.035 + 0.02 * np.sin((xx - minx) / 380.0) * np.cos((yy - miny) / 260.0)
    base_hv = 0.006 + 0.003 * np.cos((xx - minx) / 300.0)
    base_hh *= 1.0 + 0.45 * wet
    base_hv *= 1.0 + 0.15 * wet
    speck = rng.gamma(4.0, 1 / 4.0, size=(2, *xx.shape))
    hh = (base_hh * speck[0]).astype("float32")
    hv = (base_hv * speck[1]).astype("float32")
    mask = np.ones(xx.shape, dtype="uint8")
    mask[:, :3] = 255  # synthetic fill edge
    hh[:, :3] = np.nan
    hv[:, :3] = np.nan
    path.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(path, "w") as f:
        f.attrs["raiz_synthetic_fixture"] = 1
        ident = f.create_group("/science/LSAR/identification")
        sid = scenario["summary"]["scenario_id"]
        ident["granuleId"] = np.bytes_(f"SYNTHETIC_FIXTURE_GCOV_{sid}_{acquisition}")
        ident["zeroDopplerStartTime"] = np.bytes_(start)
        ident["zeroDopplerEndTime"] = np.bytes_(start)
        ident["productVersion"] = np.bytes_("synthetic-0.1")
        ident["orbitPassDirection"] = np.bytes_("Descending")
        ident["trackNumber"] = np.int32(0)
        ident["frameNumber"] = np.int32(0)
        params = f.create_group("/science/LSAR/GCOV/metadata/processingInformation/parameters")
        params["outputBackscatterNormalizationConvention"] = np.bytes_("gamma0")
        g = f.create_group("/science/LSAR/GCOV/grids/frequencyA")
        g["HHHH"] = hh
        g["HVHV"] = hv
        g["mask"] = mask
        g["xCoordinates"] = x
        g["yCoordinates"] = y
        proj = g.create_dataset("projection", data=np.uint32(epsg))
        proj.attrs["epsg_code"] = np.int32(epsg)
        g["listOfCovarianceTerms"] = np.array([b"HHHH", b"HVHV"])
    return path
