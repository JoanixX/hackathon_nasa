"""Background warm-up so the first visit is fast: DEM cells, catalog timelines, coverage probes and
terrain tiles for the owner's focus areas. Runs in one API process at a time (file lock)."""

from __future__ import annotations

import datetime as dt
import os
import time

from . import perf
from .config import get_settings
from .scenarios import get_scenario, scenario_ids


_held = None  # keeps the locked file open for the life of the warm-up


def _lock():
    """Advisory flock: the kernel releases it if the process dies, so a restart never leaves it stuck."""
    import fcntl

    global _held
    path = get_settings().runtime_dir / "warmup.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(path, "a+")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None
    _held = fh
    return path


def run() -> None:
    lock = _lock()
    if lock is None:
        return
    t0 = time.perf_counter()
    spans = perf.begin()
    try:
        from .sources import acquisitions, coverage, gibs_tile_transparent, lonlat_to_tile
        from .terrain import prefetch_region, terrain_tile_png

        today = dt.date.today().isoformat()
        for sid in scenario_ids():
            summary = get_scenario(sid)["summary"]
            if not summary.get("listed", True) and not summary.get("primary"):
                continue
            with perf.span("warm.dem_cells", scenario=sid):
                for b in [f["bounds"] for f in summary.get("focus_areas", []) if f.get("bounds")] or [summary["region_bbox"]]:
                    prefetch_region(b)
            for fa in summary.get("focus_areas", []):
                lon, lat = fa["lon"], fa["lat"]
                try:
                    with perf.span("warm.acquisitions", area=fa["name"]):
                        acq = acquisitions(tuple(fa.get("bounds", (lon - 0.015, lat - 0.015, lon + 0.015, lat + 0.015))), "2025-10-01", today)
                    dates = [d["date"] for d in acq["datasets"]["nisar_gcov"]][-60:]
                    if dates:
                        with perf.span("warm.nisar_coverage", area=fa["name"]):
                            cov = coverage("nisar_gcov", lon, lat, dates)["coverage"]
                        # Pre-render the radar tiles the interface shows first (best-covered date).
                        best = sorted(cov, key=lambda c: (c["valid_fraction"], c["date"]))[-1]["date"]
                        with perf.span("warm.nisar_tiles", area=fa["name"]):
                            for z, r in ((10, 1), (11, 1), (12, 1), (13, 1)):
                                x0, y0 = lonlat_to_tile(lon, lat, z)
                                for dx in range(-r, r + 1):
                                    for dy in range(-r, r + 1):
                                        try:
                                            gibs_tile_transparent("nisar_gcov", best, z, x0 + dx, y0 + dy)
                                        except Exception:
                                            pass
                    rtc = [d["date"] for d in acq["datasets"]["opera_rtc"] if "2026-01-01" <= d["date"] <= "2026-05-31"][-45:]
                    if rtc:
                        with perf.span("warm.rtc_coverage", area=fa["name"]):
                            coverage("opera_rtc", lon, lat, rtc)
                except Exception as exc:  # warm-up is best effort; the request path reports real errors
                    perf.log({"evt": "warm_error", "area": fa["name"], "error": f"{type(exc).__name__}: {exc}"[:200]})
                with perf.span("warm.terrain_tiles", area=fa["name"]):
                    for z, r in ((8, 0), (9, 0), (10, 1), (11, 1), (12, 2)):
                        x, y = lonlat_to_tile(lon, lat, z)
                        for dx in range(-r, r + 1):
                            for dy in range(-r, r + 1):
                                try:
                                    terrain_tile_png(z, x + dx, y + dy)
                                except Exception:
                                    pass
    finally:
        perf.log({"evt": "job", "kind": "warmup", "state": "done", "ms": round((time.perf_counter() - t0) * 1000, 1), "spans": spans})
        global _held
        if _held is not None:
            _held.close()  # releases the flock
            _held = None
