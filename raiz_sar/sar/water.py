"""Surface-water / ponding detection from NISAR GCOV backscatter time series (pure functions, tested).

Method (documented, parameters returned with every result):

1. Scene threshold. Open water is a specular reflector: low HH backscatter. The water/land split is found
   automatically with *split-based Otsu thresholding* (Martinis, Twele & Voigt 2009, NHESS 9:303-314): the
   HH dB image is cut into tiles, tiles whose histogram is bimodal are selected (high standard deviation and
   a coefficient of variation test), and Otsu's method (Otsu 1979) is applied to the pooled selected tiles.
   If no tile is bimodal there is no defensible split: the result says so and nothing is classified as water.
2. Change against a dry reference. Dark is not the same as wet: smooth dry soil and sand are also dark at
   L-band. Each pixel's baseline is the mean HH dB over the dry reference acquisitions (same track/frame,
   same geometry). "Newly observed water" requires the event HH below the threshold **and** a drop of at
   least ``delta_db`` (default -3 dB, a common flood change criterion) from the baseline.
3. Classes: 0 not water, 1 newly observed water, 2 persistent low backscatter (water in the baseline and the
   event: open water *or* a smooth dry surface; ambiguous without an independent reference), 3 receded
   (water in the baseline, not in the event, with a rise >= |delta_db|), 255 unknown (no valid sample on the
   event or baseline, or steep terrain where radar shadow/layover is possible).
4. Minimum mapping unit: connected groups smaller than ``mmu_pixels`` are not reported as water (speckle);
   they stay counted as unresolved, never invented as puddles.

Nothing here estimates depth, volume, soil fertility or planting suitability.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

NOT_WATER, NEW_WATER, PERSISTENT, RECEDED, UNKNOWN = 0, 1, 2, 3, 255
CLASS_NAMES = {NOT_WATER: "not_water", NEW_WATER: "new_water", PERSISTENT: "persistent_low_backscatter",
               RECEDED: "receded", UNKNOWN: "unknown"}


@dataclass(frozen=True)
class Params:
    tile_px: int = 50            # split-based thresholding tile size (1 km at 20 m)
    min_tile_std_db: float = 2.0  # tile must have spread to be bimodal
    min_tile_valid: float = 0.9   # share of valid pixels in a selected tile
    delta_db: float = -3.0        # minimum HH drop vs. the dry baseline for "newly observed water"
    mmu_pixels: int = 4           # minimum mapping unit (4 x 400 m2 = 0.16 ha at 20 m)
    max_slope_deg: float = 20.0   # steeper terrain -> unknown (possible radar shadow/layover)
    baseline_water_share: float = 0.5  # baseline water if below threshold on at least this share of dry dates

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def to_db(linear: np.ndarray) -> np.ndarray:
    out = np.full(linear.shape, np.nan, dtype="float64")
    ok = np.isfinite(linear) & (linear > 0)
    out[ok] = 10.0 * np.log10(linear[ok])
    return out


def otsu(values: np.ndarray, bins: int = 256) -> float | None:
    """Otsu threshold of finite values; None when undefined (fewer than 2 distinct values)."""
    v = values[np.isfinite(values)]
    if v.size < 2 or float(v.min()) == float(v.max()):
        return None
    hist, edges = np.histogram(v, bins=bins)
    centers = (edges[:-1] + edges[1:]) / 2
    w0 = np.cumsum(hist)
    w1 = w0[-1] - w0
    m = np.cumsum(hist * centers)
    mu0 = np.divide(m, w0, out=np.zeros_like(m, dtype="float64"), where=w0 > 0)
    mu1 = np.divide(m[-1] - m, w1, out=np.zeros_like(m, dtype="float64"), where=w1 > 0)
    between = w0 * w1 * (mu0 - mu1) ** 2
    between[(w0 == 0) | (w1 == 0)] = -1
    k = int(np.argmax(between))
    if between[k] <= 0:
        return None
    return float(edges[k + 1])


def split_threshold(db: np.ndarray, valid: np.ndarray, p: Params = Params()) -> dict[str, Any]:
    """Split-based Otsu on HH dB. Returns {"threshold_db": float|None, "tiles_total", "tiles_selected", "reason"}."""
    h, w = db.shape
    t = p.tile_px
    stats = []
    for r in range(0, h - t + 1, t):
        for c in range(0, w - t + 1, t):
            vv = valid[r:r + t, c:c + t]
            if vv.mean() < p.min_tile_valid:
                continue
            x = db[r:r + t, c:c + t][vv]
            stats.append((r, c, float(x.mean()), float(x.std())))
    total = len(stats)
    if not stats:
        return {"threshold_db": None, "tiles_total": 0, "tiles_selected": 0, "reason": "no tile with enough valid pixels"}
    means = np.array([s[2] for s in stats])
    # Bimodal candidates: spread above the minimum and darker than the scene's typical tile (they contain water).
    sel = [s for s in stats if s[3] >= p.min_tile_std_db and s[2] < float(np.median(means))]
    sel = sorted(sel, key=lambda s: -s[3])[: max(5, len(sel) // 5)]  # the most bimodal fifth (at least 5)
    if len(sel) < 3:
        return {"threshold_db": None, "tiles_total": total, "tiles_selected": len(sel), "reason": "too few bimodal tiles"}
    pooled = np.concatenate([db[r:r + t, c:c + t][valid[r:r + t, c:c + t]] for r, c, _, _ in sel])
    thr = otsu(pooled)
    if thr is None:
        return {"threshold_db": None, "tiles_total": total, "tiles_selected": len(sel), "reason": "Otsu undefined"}
    return {"threshold_db": round(thr, 3), "tiles_total": total, "tiles_selected": len(sel), "reason": "split-based Otsu"}


def _components_at_least(mask: np.ndarray, n: int) -> np.ndarray:
    from scipy import ndimage

    if n <= 1 or not mask.any():
        return mask
    lab, k = ndimage.label(mask, structure=np.ones((3, 3), dtype=bool))
    sizes = np.bincount(lab.ravel())
    keep = sizes >= n
    keep[0] = False
    return keep[lab]


def classify(event_db: np.ndarray, baseline_dbs: list[np.ndarray], threshold_db: float, unknown_extra: np.ndarray | None = None,
             p: Params = Params()) -> np.ndarray:
    """Per-pixel classes (see module docstring). Inputs are HH dB arrays on one grid (NaN = invalid)."""
    if not baseline_dbs:
        raise ValueError("at least one dry baseline acquisition is required")
    base = np.stack(baseline_dbs)
    base_valid = np.isfinite(base).all(axis=0)
    ev_valid = np.isfinite(event_db)
    known = base_valid & ev_valid
    if unknown_extra is not None:
        known &= ~unknown_extra
    with np.errstate(invalid="ignore"):
        base_mean = np.where(base_valid, np.nanmean(np.where(np.isfinite(base), base, np.nan), axis=0), np.nan)
        base_water = (np.sum(base < threshold_db, axis=0) >= max(1, int(np.ceil(p.baseline_water_share * base.shape[0])))) & base_valid
        ev_water = (event_db < threshold_db) & ev_valid
        delta = event_db - base_mean
    new = ev_water & ~base_water & (delta <= p.delta_db) & known
    persistent = ev_water & base_water & known
    receded = base_water & ~ev_water & (delta >= -p.delta_db) & known
    new = _components_at_least(new, p.mmu_pixels)
    persistent = _components_at_least(persistent, p.mmu_pixels)
    receded = _components_at_least(receded, p.mmu_pixels)
    out = np.full(event_db.shape, NOT_WATER, dtype="uint8")
    out[receded] = RECEDED
    out[persistent] = PERSISTENT
    out[new] = NEW_WATER
    out[~known] = UNKNOWN
    return out


def class_areas_ha(classes: np.ndarray, pixel_area_m2: float, inside: np.ndarray | None = None) -> dict[str, float]:
    sel = np.ones(classes.shape, dtype=bool) if inside is None else inside
    return {CLASS_NAMES[k]: round(float(((classes == k) & sel).sum()) * pixel_area_m2 / 10_000, 4) for k in CLASS_NAMES}


def stats_db(db: np.ndarray, inside: np.ndarray | None = None) -> dict[str, Any]:
    sel = np.isfinite(db) & (inside if inside is not None else True)
    v = db[sel]
    if v.size == 0:
        return {"median": None, "p10": None, "p90": None, "n": 0}
    p10, p50, p90 = np.percentile(v, [10, 50, 90])
    return {"median": round(float(p50), 2), "p10": round(float(p10), 2), "p90": round(float(p90), 2), "n": int(v.size)}


def confusion(pred_water: np.ndarray, ref_water: np.ndarray, ref_valid: np.ndarray) -> dict[str, Any]:
    """Pixel agreement with an independent reference on pixels the reference observed."""
    tp = int((pred_water & ref_water & ref_valid).sum())
    fp = int((pred_water & ~ref_water & ref_valid).sum())
    fn = int((~pred_water & ref_water & ref_valid).sum())
    n = int(ref_valid.sum())
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    iou = tp / (tp + fp + fn) if tp + fp + fn else None
    return {"reference_pixels": n, "true_positive": tp, "false_positive": fp, "false_negative": fn,
            "precision": None if precision is None else round(precision, 3), "recall": None if recall is None else round(recall, 3),
            "iou": None if iou is None else round(iou, 3)}


def slope_deg(dem: np.ndarray, res_m: float) -> np.ndarray:
    gy, gx = np.gradient(dem, res_m)
    return np.degrees(np.arctan(np.hypot(gx, gy)))
