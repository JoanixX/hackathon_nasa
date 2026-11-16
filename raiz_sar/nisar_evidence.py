"""NISAR water evidence for an area: real GCOV windows -> calibrated water/change classes -> measurements.

Flow (all steps recorded in the artifact):
1. ASF catalog: NISAR L2 GCOV acquisitions over the area; one track/frame is used so every date has the same
   viewing geometry and grid (comparable observations).
2. Server-side windowed reads (HTTP range requests with the configured Earthdata login): only the HDF5 chunks
   covering the area are transferred and cached; whole granules are never downloaded here.
3. Rain context per acquisition from NASA POWER (modeled reanalysis): dry baseline = antecedent 7-day total
   below ``DRY_7D_MM``; event candidates = antecedent 3-day total of at least ``EVENT_3D_MM``.
4. Water threshold on HH (dB) calibrated against an independent optical reference: OPERA DSWx-HLS open water
   vs not-water on clear pixels within +/-``REF_MAX_DAYS`` days of a NISAR acquisition. Training uses the
   reference pairs that are not the evaluated event; the event pair (when the optical reference saw it) is the
   held-out test. The threshold maximises F1 on the training pixels. Metrics are reported, not assumed.
5. Classification and change (raiz_sar.sar.water), polygons, per-zone measurements and images.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import time
from pathlib import Path
from typing import Any

import numpy as np

from . import perf
from .config import get_settings
from .sar import water as W

DRY_7D_MM = 5.0
EVENT_3D_MM = 10.0
REF_MAX_DAYS = 2
MIN_REF_PIXELS = 200
METHOD_VERSION = "nisar-water-1.0"


class EvidenceError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _cache_dir(name: str) -> Path:
    p = get_settings().runtime_dir / "cache" / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def snap_aoi(bbox: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    """Snap an area to a 0.01 deg grid (cache reuse) and bound it (at most 0.25 x 0.25 deg)."""
    w, s, e, n = bbox
    if not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
        raise EvidenceError("invalid_input", "invalid bounding box")
    w, s = math.floor(w * 100) / 100, math.floor(s * 100) / 100
    e, n = math.ceil(e * 100) / 100, math.ceil(n * 100) / 100
    if e - w > 0.25 or n - s > 0.25:
        raise EvidenceError("invalid_input", "area too large for NISAR evidence (max 0.25 x 0.25 degrees)")
    return (round(w, 2), round(s, 2), round(e, 2), round(n, 2))


# ------------------------------------------------------------------ catalog
def catalog(aoi: tuple[float, float, float, float], start: str, end: str) -> dict[str, Any]:
    import asf_search as asf

    from . import upstream

    w, s, e, n = aoi
    wkt = f"POLYGON(({w} {s},{e} {s},{e} {n},{w} {n},{w} {s}))"
    with upstream.slot(60), perf.span("asf.search", dataset="nisar_gcov_evidence"):
        res = asf.search(intersectsWith=wkt, dataset="NISAR", processingLevel="GCOV", start=start, end=end, maxResults=300)
    rows = []
    for r in res:
        p = r.properties
        url = p.get("url") or ""
        if not url.endswith(".h5"):
            continue
        name = url.rsplit("/", 1)[-1]
        rows.append({"granule_id": name[:-3], "url": url, "start_time": p.get("startTime"), "date": (p.get("startTime") or "")[:10],
                     "track": p.get("pathNumber"), "frame": p.get("frameNumber"), "direction": p.get("flightDirection"),
                     "pol_mode": name.split("_")[9] if len(name.split("_")) > 9 else None})
    if not rows:
        raise EvidenceError("no_nisar_coverage", "No NISAR GCOV acquisition intersects this area in the period.")
    groups: dict[tuple, list] = {}
    for r in rows:
        groups.setdefault((r["track"], r["frame"], r["direction"]), []).append(r)
    # The track/frame with the most acquisitions (ties: smaller files = ascending frames listed first by date).
    key = max(groups, key=lambda k: (len(groups[k]), k[2] == "ASCENDING"))
    acq = sorted(groups[key], key=lambda r: r["start_time"])
    dedup: dict[str, dict] = {}
    for r in acq:  # one granule per date (latest processing wins)
        dedup[r["date"]] = r
    return {"track": key[0], "frame": key[1], "direction": key[2], "acquisitions": list(dedup.values()),
            "other_geometries": [{"track": k[0], "frame": k[1], "direction": k[2], "count": len(v)} for k, v in groups.items() if k != key]}


# ------------------------------------------------------------------ remote windows
def _window_key(granule_id: str, aoi) -> Path:
    h = hashlib.sha256(json.dumps([granule_id, aoi]).encode()).hexdigest()[:20]
    return _cache_dir("nisar_windows") / f"{h}.npz"


def read_window(acq: dict[str, Any], aoi: tuple[float, float, float, float]) -> dict[str, Any]:
    """HH (and HV when present), mask and coordinates for the area, read by HTTP range requests and cached."""
    path = _window_key(acq["granule_id"], aoi)
    if path.exists():
        with perf.span("nisar.window_cache_hit"):
            z = np.load(path, allow_pickle=False)
            out = {k: z[k] for k in z.files}
        out["meta"] = json.loads(str(out.pop("meta_json")))
        return out
    import earthaccess
    import h5py
    from pyproj import Transformer

    from . import upstream

    last_exc: Exception | None = None
    for attempt in range(3):  # a stalled HTTP read is abandoned after the socket timeout and retried
        try:
            return _read_window_once(acq, aoi, path)
        except EvidenceError:
            raise
        except Exception as exc:  # noqa: BLE001 - network/HDF5 read failures: retry, then report
            last_exc = exc
            perf.log({"evt": "nisar_read_retry", "granule": acq["granule_id"][:60], "attempt": attempt + 1, "error": type(exc).__name__})
            time.sleep(2 * (attempt + 1))
    raise EvidenceError("nisar_read_failed", f"Could not read {acq['granule_id']}: {type(last_exc).__name__}")


def _https_fs():
    """fsspec HTTPS session with the Earthdata token and socket timeouts (a stalled read must not hang the job)."""
    import aiohttp
    import earthaccess
    import fsspec

    auth = earthaccess.login(strategy="environment")
    token = (getattr(auth, "token", None) or {}).get("access_token")
    if not token:
        return earthaccess.get_fsspec_https_session()
    return fsspec.filesystem("https", client_kwargs={"headers": {"Authorization": f"Bearer {token}"},
                                                     "timeout": aiohttp.ClientTimeout(total=None, sock_connect=30, sock_read=90)})


def _read_window_once(acq: dict[str, Any], aoi, path: Path) -> dict[str, Any]:
    import h5py
    from pyproj import Transformer

    from . import upstream

    with perf.span("nisar.window_read", granule=acq["granule_id"][:40]):
        fs = _https_fs()
        with upstream.slot(120), fs.open(acq["url"], block_size=2 * 1024 * 1024) as fh, h5py.File(fh, "r") as h:
            g = h["science/LSAR/GCOV/grids/frequencyA"]
            epsg = int(np.asarray(g["projection"][()]).reshape(-1)[0])
            tr = Transformer.from_crs(4326, epsg, always_xy=True)
            w, s, e, n = aoi
            xs, ys = tr.transform([w, e, w, e], [s, s, n, n])
            x = np.asarray(g["xCoordinates"][()], dtype="float64")
            y = np.asarray(g["yCoordinates"][()], dtype="float64")
            c0, c1 = int(np.searchsorted(x, min(xs))), int(np.searchsorted(x, max(xs)))
            r0, r1 = int(np.searchsorted(-y, -max(ys))), int(np.searchsorted(-y, -min(ys)))
            if c1 - c0 < 2 or r1 - r0 < 2:
                raise EvidenceError("no_nisar_coverage", f"{acq['granule_id']} does not cover the area.")
            hh = np.asarray(g["HHHH"][r0:r1, c0:c1], dtype="float32")
            hv = np.asarray(g["HVHV"][r0:r1, c0:c1], dtype="float32") if "HVHV" in g else np.full(hh.shape, np.nan, "float32")
            mask = np.asarray(g["mask"][r0:r1, c0:c1], dtype="uint8") if "mask" in g else np.ones(hh.shape, "uint8")
            ident = h["science/LSAR/identification"]

            def sv(k):
                if k not in ident:
                    return None
                v = ident[k][()]
                return v.decode() if isinstance(v, bytes) else str(v)

            meta = {"granule_id": acq["granule_id"], "zero_doppler_start": sv("zeroDopplerStartTime"), "product_version": sv("productVersion"),
                    "processing_type": sv("processingType"), "epsg": epsg, "spacing_m": [float(x[1] - x[0]), float(y[1] - y[0])],
                    "normalization": "gamma0" if "rtcGammaToSigmaFactor" in g else "unknown",
                    "has_hv": "HVHV" in g, "mask_semantics": str(g["mask"].attrs.get("description", b""))[:200] if "mask" in g else None}
    out = {"hh": hh, "hv": hv, "mask": mask, "x": x[c0:c1], "y": y[r0:r1], "meta_json": np.array(json.dumps(meta))}
    tmp = path.with_suffix(".tmp.npz")
    np.savez_compressed(tmp, **out)
    tmp.replace(path)
    out.pop("meta_json")
    out["meta"] = meta
    return out


def valid_db(win: dict[str, Any], term: str = "hh") -> np.ndarray:
    a = win[term].astype("float64")
    m = win["mask"]
    ok = np.isfinite(a) & (a > 0) & (m != 255) & (m != 0)
    return np.where(ok, W.to_db(np.where(ok, a, np.nan)), np.nan)


def align(wins: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Crop every window to the common grid cells (same track/frame grids share the posting)."""
    x0 = max(w["x"][0] for w in wins)
    x1 = min(w["x"][-1] for w in wins)
    y0 = min(w["y"][0] for w in wins)  # y descends
    y1 = max(w["y"][-1] for w in wins)
    out = []
    for w in wins:
        cx = np.nonzero((w["x"] >= x0 - 1e-6) & (w["x"] <= x1 + 1e-6))[0]
        cy = np.nonzero((w["y"] <= y0 + 1e-6) & (w["y"] >= y1 - 1e-6))[0]
        sl = (slice(cy[0], cy[-1] + 1), slice(cx[0], cx[-1] + 1))
        out.append({**w, "hh": w["hh"][sl], "hv": w["hv"][sl], "mask": w["mask"][sl], "x": w["x"][sl[1]], "y": w["y"][sl[0]]})
    shapes = {o["hh"].shape for o in out}
    if len(shapes) != 1:
        raise EvidenceError("grid_mismatch", f"Acquisitions do not share a grid: {sorted(shapes)}")
    return out


# ------------------------------------------------------------------ references and context
def dswx_on_grid(date: str, aoi, x: np.ndarray, y: np.ndarray, epsg: int) -> dict[str, Any] | None:
    """DSWx-HLS classes resampled (nearest) to the NISAR grid: water = open water; valid = open or not-water."""
    from rasterio.crs import CRS
    from rasterio.transform import from_origin
    from rasterio.warp import Resampling, reproject

    from .sources import DSWX_CLASSES, SourceUnavailable, fetch_gibs_mosaic

    try:
        rgba, tf = fetch_gibs_mosaic("dswx", date, aoi, 12)
    except (SourceUnavailable, ValueError):
        return None
    rgb = rgba[:3].astype("int32")
    code = np.full(rgba.shape[1:], 0, dtype="uint8")  # 0 unknown
    for (r_, g_, b_), name in DSWX_CLASSES.items():
        hit = (rgb[0] == r_) & (rgb[1] == g_) & (rgb[2] == b_) & (rgba[3] > 0)
        code[hit] = {"not_water": 1, "open_water": 2, "partial_water": 3}.get(name, 0)
    dst = np.zeros((len(y), len(x)), dtype="uint8")
    sx = float(x[1] - x[0])
    sy = float(y[0] - y[1])
    reproject(code, dst, src_transform=tf, src_crs=CRS.from_epsg(3857),
              dst_transform=from_origin(x[0] - sx / 2, y[0] + sy / 2, sx, sy), dst_crs=CRS.from_epsg(epsg),
              resampling=Resampling.nearest, src_nodata=0, dst_nodata=0)
    valid = (dst == 1) | (dst == 2)
    if valid.sum() < MIN_REF_PIXELS:
        return None
    return {"date": date, "water": dst == 2, "valid": valid, "partial": dst == 3, "valid_pixels": int(valid.sum()),
            "water_pixels": int((dst == 2).sum())}


def rain_context(aoi, dates: list[str]) -> dict[str, dict[str, float | None]]:
    from .sources import SourceUnavailable, rainfall

    lon, lat = (aoi[0] + aoi[2]) / 2, (aoi[1] + aoi[3]) / 2
    d0 = (dt.date.fromisoformat(min(dates)) - dt.timedelta(days=8)).isoformat()
    d1 = max(dates)
    try:
        r = rainfall(lat, lon, d0, d1)
    except SourceUnavailable:
        return {d: {"antecedent_3d_mm": None, "antecedent_7d_mm": None} for d in dates}
    mm = {x["date"]: x["mm"] for x in r["days"]}

    def total(d: str, k: int) -> float | None:
        vals = [mm.get((dt.date.fromisoformat(d) - dt.timedelta(days=i)).isoformat()) for i in range(1, k + 1)]
        return None if any(v is None for v in vals) else round(sum(vals), 2)

    return {d: {"antecedent_3d_mm": total(d, 3), "antecedent_7d_mm": total(d, 7), "same_day_mm": mm.get(d)} for d in dates}


def calibrate(pairs: list[tuple[np.ndarray, dict[str, Any]]]) -> dict[str, Any]:
    """HH dB threshold maximising F1 against reference water on reference-valid pixels (training pairs)."""
    hh = np.concatenate([db[ref["valid"] & np.isfinite(db)] for db, ref in pairs]) if pairs else np.array([])
    wat = np.concatenate([ref["water"][ref["valid"] & np.isfinite(db)] for db, ref in pairs]) if pairs else np.array([], bool)
    if hh.size < MIN_REF_PIXELS or wat.sum() < 20 or (~wat).sum() < 20:
        return {"threshold_db": None, "reason": "not enough reference water and land pixels to calibrate", "train_pixels": int(hh.size),
                "train_water_pixels": int(wat.sum())}
    cands = np.arange(-30.0, -8.0, 0.25)
    best = (-1.0, None)
    for t in cands:
        pred = hh < t
        tp = float((pred & wat).sum())
        fp = float((pred & ~wat).sum())
        fn = float((~pred & wat).sum())
        f1 = 2 * tp / (2 * tp + fp + fn) if tp else 0.0
        if f1 > best[0]:
            best = (f1, float(t))
    return {"threshold_db": best[1], "train_f1": round(best[0], 3), "train_pixels": int(hh.size), "train_water_pixels": int(wat.sum()),
            "reason": "maximum F1 against DSWx-HLS open water on training pairs"}


# ------------------------------------------------------------------ images
def _png(rgba: np.ndarray) -> bytes:
    import warnings

    from rasterio.errors import NotGeoreferencedWarning
    from rasterio.io import MemoryFile

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", NotGeoreferencedWarning)
        with MemoryFile() as mf:
            with mf.open(driver="PNG", width=rgba.shape[2], height=rgba.shape[1], count=rgba.shape[0], dtype="uint8") as d:
                d.write(rgba)
            return mf.read()


def radar_composite(hh_db: np.ndarray, hv_db: np.ndarray) -> np.ndarray:
    """Dual-pol false colour: R = HH [-25, 0] dB, G = HV [-32, -8] dB, B = HH-HV [0, 15] dB. Invalid -> transparent."""
    def sc(a, lo, hi):
        return np.clip((a - lo) / (hi - lo) * 255, 0, 255)
    ok = np.isfinite(hh_db)
    hv = np.where(np.isfinite(hv_db), hv_db, hh_db - 7)  # single-pol dates: G/B follow HH only (stated in the legend)
    rgb = np.stack([sc(hh_db, -25, 0), sc(hv, -32, -8), sc(hh_db - hv, 0, 15)])
    a = np.where(ok, 255, 0)
    return np.concatenate([np.nan_to_num(rgb), a[None]]).astype("uint8")


CLASS_RGBA = {W.NEW_WATER: (31, 120, 255, 230), W.PERSISTENT: (20, 40, 120, 200), W.RECEDED: (240, 170, 40, 220), W.UNKNOWN: (150, 150, 150, 110)}


def class_overlay(classes: np.ndarray) -> np.ndarray:
    out = np.zeros((4, *classes.shape), dtype="uint8")
    for k, col in CLASS_RGBA.items():
        sel = classes == k
        for i in range(4):
            out[i][sel] = col[i]
    return out


# ------------------------------------------------------------------ polygons and zones
def polygons(classes: np.ndarray, x: np.ndarray, y: np.ndarray, epsg: int, keep=(W.NEW_WATER, W.PERSISTENT, W.RECEDED), limit: int = 600):
    from rasterio.features import shapes
    from rasterio.transform import from_origin
    from shapely.geometry import mapping, shape

    from .geo import to_wgs84

    sx = float(x[1] - x[0])
    sy = float(y[0] - y[1])
    tf = from_origin(x[0] - sx / 2, y[0] + sy / 2, sx, sy)
    feats = []
    for k in keep:
        m = classes == k
        if not m.any():
            continue
        for geom, _ in shapes(m.astype("uint8"), mask=m, transform=tf):
            g = shape(geom)
            g84 = to_wgs84(g, f"EPSG:{epsg}")
            feats.append({"type": "Feature", "geometry": mapping(g84),
                          "properties": {"class": W.CLASS_NAMES[k], "area_m2": round(g.area, 1)}})
    feats.sort(key=lambda f: -f["properties"]["area_m2"])
    for f in feats:
        c = f["geometry"]["coordinates"]
        f["geometry"]["coordinates"] = [[[round(p[0], 6), round(p[1], 6)] for p in ring] for ring in c] if f["geometry"]["type"] == "Polygon" else c
    return feats[:limit]


def zone_masks(zones: list[dict[str, Any]], x, y, epsg):
    from rasterio.features import geometry_mask
    from rasterio.transform import from_origin
    from shapely.geometry import mapping, shape

    from .geo import to_metric

    sx = float(x[1] - x[0])
    sy = float(y[0] - y[1])
    tf = from_origin(x[0] - sx / 2, y[0] + sy / 2, sx, sy)
    out = []
    for z in zones:
        g = to_metric(shape(z["geometry"]), f"EPSG:{epsg}")
        m = geometry_mask([mapping(g)], out_shape=(len(y), len(x)), transform=tf, invert=True)
        out.append((z, m))
    return out


# ------------------------------------------------------------------ orchestration
def build(aoi_in, event_date: str | None = None, zones: list[dict[str, Any]] | None = None, start: str = "2026-06-01",
          end: str | None = None, params: W.Params = W.Params()) -> dict[str, Any]:
    t0 = time.time()
    aoi = snap_aoi(tuple(aoi_in))
    end = end or dt.date.today().isoformat()
    cat = catalog(aoi, start, end)
    acqs = cat["acquisitions"]
    rain = rain_context(aoi, [a["date"] for a in acqs])
    for a in acqs:
        a["rain"] = rain.get(a["date"])
    dry = [a for a in acqs if a["rain"] and a["rain"]["antecedent_7d_mm"] is not None and a["rain"]["antecedent_7d_mm"] < DRY_7D_MM]
    if event_date:
        ev = next((a for a in acqs if a["date"] == event_date), None)
        if ev is None:
            raise EvidenceError("invalid_input", f"No NISAR acquisition on {event_date} for this area/track.")
    else:
        wet = [a for a in acqs if a["rain"] and (a["rain"]["antecedent_3d_mm"] or 0) >= EVENT_3D_MM]
        ev = wet[-1] if wet else acqs[-1]
    baseline = [a for a in dry if a["date"] < ev["date"]][-3:]
    if not baseline:
        raise EvidenceError("no_dry_baseline", "No dry NISAR acquisition before the event on this track: change cannot be measured.")
    # Grid from the event window (range reads only, cached), then the optical reference on that grid for every
    # acquisition date (+/- REF_MAX_DAYS). Dry-date pairs train the threshold; wet-date pairs are held out.
    ev_win = read_window(ev, aoi)
    gx, gy, gepsg = ev_win["x"], ev_win["y"], int(ev_win["meta"]["epsg"])
    refs: dict[str, dict[str, Any]] = {}
    for a in acqs:
        for k in range(0, REF_MAX_DAYS + 1):
            hit = None
            for sign in ((0,) if k == 0 else (-1, 1)):
                d = (dt.date.fromisoformat(a["date"]) + dt.timedelta(days=sign * k)).isoformat()
                r = dswx_on_grid(d, aoi, gx, gy, gepsg)
                if r and r["water_pixels"] >= 5:
                    hit = r
                    break
            if hit:
                refs[a["date"]] = {**hit, "offset_days": (dt.date.fromisoformat(hit["date"]) - dt.date.fromisoformat(a["date"])).days}
                break
    dry_dates = {a["date"] for a in dry}
    used = {a["date"]: a for a in baseline + [ev]}
    for a in acqs:
        if a["date"] in refs:
            used.setdefault(a["date"], a)
    wins = {d: (ev_win if d == ev["date"] else read_window(a, aoi)) for d, a in sorted(used.items())}
    aligned = align(list(wins.values()))
    wins = dict(zip(wins.keys(), aligned))
    w0 = aligned[0]
    x, y, epsg = w0["x"], w0["y"], int(w0["meta"]["epsg"])
    db = {d: valid_db(w) for d, w in wins.items()}
    hv = {d: valid_db(w, "hv") for d, w in wins.items()}
    # References were resampled on the event grid; crop them to the common grid as well.
    ex0 = int(np.searchsorted(gx, x[0] - 1e-6))
    ey0 = int(np.searchsorted(-gy, -y[0] - 1e-6))
    sl = (slice(ey0, ey0 + len(y)), slice(ex0, ex0 + len(x)))
    refs = {d: {**r, "water": r["water"][sl], "valid": r["valid"][sl], "partial": r["partial"][sl]} for d, r in refs.items()}
    train = [(db[d], r) for d, r in refs.items() if d in dry_dates and d != ev["date"]]
    held_out = {d: r for d, r in refs.items() if d not in dry_dates or d == ev["date"]}
    cal = calibrate(train)
    thr = cal["threshold_db"]
    if thr is None:
        raise EvidenceError("uncalibrated", "No clear optical reference with water near the dry acquisitions: the NISAR water threshold "
                                            "cannot be calibrated here. Backscatter images and change are still available.")
    tests = []
    for d, r in sorted(held_out.items()):
        pred = db[d] < thr
        tests.append({"nisar_date": d, "reference": f"OPERA DSWx-HLS {r['date']} (offset {r['offset_days']} d)",
                      **W.confusion(pred & np.isfinite(db[d]), r["water"], r["valid"] & np.isfinite(db[d]))})
    # Steep terrain -> unknown (possible radar shadow/layover).
    steep = _steep_mask(aoi, x, y, epsg, params.max_slope_deg)
    classes = W.classify(db[ev["date"]], [db[a["date"]] for a in baseline], thr, steep, params)
    pix_m2 = abs(float(x[1] - x[0]) * float(y[0] - y[1]))
    delta = db[ev["date"]] - np.nanmean(np.stack([db[a["date"]] for a in baseline]), axis=0)
    zones_out = []
    for z, m in zone_masks(zones or [], x, y, epsg):
        inside = m
        n_in = int(inside.sum())
        valid_in = int((inside & (classes != W.UNKNOWN)).sum())  # valid on the event AND every baseline date
        zones_out.append({"sector_id": z.get("sector_id"), "name": z.get("name"), "pixels": n_in, "geometry_hash_basis": z.get("geometry"),
                          "valid_coverage": round(valid_in / n_in, 4) if n_in else None,
                          "hh_db_event": W.stats_db(db[ev["date"]], inside), "hv_db_event": W.stats_db(hv[ev["date"]], inside),
                          "hh_db_baseline": W.stats_db(np.nanmean(np.stack([db[a["date"]] for a in baseline]), axis=0), inside),
                          "delta_hh_db": W.stats_db(delta, inside), "areas_ha": W.class_areas_ha(classes, pix_m2, inside)})
    # Repeated detections across all read dates (observations, not continuous monitoring).
    stack = np.stack([db[d] < thr for d in sorted(db)])
    valid_stack = np.stack([np.isfinite(db[d]) for d in sorted(db)])
    repeated = {"dates": sorted(db), "max_detections": int((stack & valid_stack).sum(axis=0).max())}
    run_id = hashlib.sha256(json.dumps([METHOD_VERSION, aoi, ev["granule_id"], [a["granule_id"] for a in baseline], params.as_dict(), thr,
                                     [[z.get("sector_id"), z.get("geometry")] for z in (zones or [])]], sort_keys=True).encode()).hexdigest()[:16]
    out_dir = get_settings().artifact_dir / "nisar_water" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    images = {}
    for d in [a["date"] for a in baseline] + [ev["date"]]:
        (out_dir / f"radar_{d}.png").write_bytes(_png(radar_composite(db[d], hv[d])))
        images[f"radar_{d}"] = f"radar_{d}.png"
    (out_dir / "classes.png").write_bytes(_png(class_overlay(classes)))
    images["classes"] = "classes.png"
    from .geo import to_wgs84
    from shapely.geometry import box as sbox

    sx = float(x[1] - x[0])
    sy = float(y[0] - y[1])
    footprint = to_wgs84(sbox(x[0] - sx / 2, y[-1] - sy / 2, x[-1] + sx / 2, y[0] + sy / 2), f"EPSG:{epsg}")
    feats = polygons(classes, x, y, epsg)
    areas = W.class_areas_ha(classes, pix_m2)
    result = {
        "evidence_version": f"{METHOD_VERSION}:{run_id}", "run_id": run_id, "method_version": METHOD_VERSION,
        "source": "NISAR L2 GCOV (provisional products, ASF DAAC), read server-side by HTTP range requests",
        "aoi_lonlat": list(aoi), "image_bounds_lonlat": [round(v, 6) for v in footprint.bounds], "grid": {"epsg": epsg, "spacing_m": [sx, -sy], "shape": list(classes.shape)},
        "track": cat["track"], "frame": cat["frame"], "direction": cat["direction"], "other_geometries": cat["other_geometries"],
        "event": {k: ev[k] for k in ("date", "start_time", "granule_id", "pol_mode")} | {"rain": ev["rain"], "meta": wins[ev["date"]]["meta"]},
        "baseline": [{k: a[k] for k in ("date", "start_time", "granule_id", "pol_mode")} | {"rain": a["rain"], "meta": wins[a["date"]]["meta"]} for a in baseline],
        "acquisitions": [{k: a[k] for k in ("date", "start_time", "granule_id", "pol_mode")} | {"rain": a["rain"]} for a in acqs],
        "rain_rule": {"dry_baseline": f"antecedent 7-day total < {DRY_7D_MM} mm", "event": f"antecedent 3-day total >= {EVENT_3D_MM} mm",
                      "source": "NASA POWER PRECTOTCORR (MERRA-2 reanalysis, modeled)"},
        "threshold": {"hh_db": thr, **cal, "reference_dates": {d: {"reference_date": r["date"], "offset_days": r["offset_days"],
                                                                     "valid_pixels": r["valid_pixels"], "water_pixels": r["water_pixels"]} for d, r in refs.items()}},
        "validation": {"held_out": tests, "event_measured": any(t["nisar_date"] == ev["date"] for t in tests),
                       "note": "Threshold detector (HH < threshold) on acquisitions not used for calibration, against OPERA DSWx-HLS open water on "
                               "cloud-free pixels; partial-water pixels excluded. Precision/recall are local to these dates."},
        "params": params.as_dict(), "areas_ha": areas,
        "scene_hh_db_event": W.stats_db(db[ev["date"]]), "scene_delta_hh_db": W.stats_db(delta),
        "repeated_detections": repeated, "zones": zones_out, "features": feats, "images": images,
        "limits": ["20 m grid: ponds smaller than about 0.16 ha (minimum mapping unit) are not resolved.",
                   "Persistent low backscatter can be open water or a smooth dry surface (sand, tarmac); it is not labelled water without the optical reference.",
                   "Water depth, volume, duration between acquisitions, soil fertility and planting suitability are not measured by NISAR.",
                   "Products are provisional (PR); calibration and validation are local to this area and period."],
        "processing_s": round(time.time() - t0, 1),
    }
    (out_dir / "evidence.json").write_text(json.dumps(result), encoding="utf-8")
    return result


def _steep_mask(aoi, x, y, epsg, max_deg) -> np.ndarray:
    from rasterio.crs import CRS
    from rasterio.transform import from_origin
    from rasterio.warp import Resampling, reproject

    from .terrain import TerrainUnavailable, read_dem

    try:
        dem, tf, covered = read_dem(aoi[0] - 0.01, aoi[1] - 0.01, aoi[2] + 0.01, aoi[3] + 0.01)
    except (TerrainUnavailable, OSError, ValueError):
        return np.zeros((len(y), len(x)), dtype=bool)
    sx = float(x[1] - x[0])
    sy = float(y[0] - y[1])
    dst = np.full((len(y), len(x)), np.nan, dtype="float32")
    reproject(dem.astype("float32"), dst, src_transform=tf, src_crs=CRS.from_epsg(4326), dst_transform=from_origin(x[0] - sx / 2, y[0] + sy / 2, sx, sy),
              dst_crs=CRS.from_epsg(epsg), resampling=Resampling.bilinear, src_nodata=np.nan, dst_nodata=np.nan)
    sl = W.slope_deg(np.where(np.isfinite(dst), dst, np.nanmean(dst)), sx)
    return np.isfinite(sl) & (sl > max_deg)
