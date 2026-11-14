"""GCOV reader and SAR math: dB conversion, windows, RVI and malformed HDF5 handling."""

from __future__ import annotations

import math
from pathlib import Path

import h5py
import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays

from conftest import budget
from raiz_sar.sar.gcov import inspect_gcov, quad_pol_rvi, to_db, window_indices
from raiz_sar.sar.pipeline import process_gcov
from raiz_sar.sar.synthetic import write_synthetic_gcov
from raiz_sar.scenarios import get_scenario

floats_any = st.floats(allow_nan=True, allow_infinity=True, width=64)


@settings(max_examples=budget(2000))
@given(arrays(np.float64, st.integers(1, 64), elements=floats_any))
def test_db_conversion_masks_invalid_and_round_trips(a):
    db = to_db(a)
    ok = np.isfinite(a) & (a > 0)
    assert np.all(np.isnan(db[~ok]))  # nonpositive / non-finite never become numbers
    # Independent oracle in the log domain (math.log10 per element). Reconstructing 10**(dB/10)
    # overflows to inf near float max (minimized counterexample 1.79769313e+308), so the check
    # compares exponents instead of re-exponentiating.
    for x, d in zip(a[ok], db[ok]):
        assert math.isfinite(d)
        assert abs(d / 10 - math.log10(x)) <= 1e-12 * max(1.0, abs(math.log10(x)))


def test_db_regression_float_max():
    """Minimized counterexample from the Hypothesis campaign (oracle overflow, not a code defect)."""
    db = to_db(np.array([1.79769313e308]))
    assert math.isfinite(db[0]) and abs(db[0] - 3082.547) < 1e-3


@settings(max_examples=budget(2000))
@given(st.integers(1, 300), st.floats(-1e5, 1e5), st.floats(0.5, 100), st.booleans(), st.floats(-2e5, 2e5), st.floats(0, 5e4))
def test_window_indices_match_brute_force(n, start, step, descending, lo, width):
    coords = start + step * np.arange(n)
    if descending:
        coords = coords[::-1]
    hi = lo + width
    got = window_indices(coords, lo, hi)
    half = step / 2
    inside = [i for i, c in enumerate(coords) if c + half >= lo and c - half <= hi]
    if not inside:
        assert got is None
    else:
        assert got == (min(inside), max(inside) + 1)


@settings(max_examples=budget(1500))
@given(*(arrays(np.float64, 16, elements=st.one_of(st.floats(-1, 10), st.just(math.nan), st.just(math.inf))) for _ in range(3)))
def test_quad_pol_rvi_bounded(hh, hv, vv):
    r = quad_pol_rvi(hh, hv, vv)
    fin = r[np.isfinite(r)]
    assert np.all((fin >= 0) & (fin <= 1))


def test_synthetic_pipeline_end_to_end(tmp_path: Path):
    sc = get_scenario("carabayllo-rio-seco")
    p = write_synthetic_gcov(tmp_path / "s.h5", sc, "baseline")
    info = inspect_gcov(p)
    assert info.synthetic_fixture and info.normalization == "gamma0"
    assert [g.terms for g in info.grids] == [["HHHH", "HVHV"]]
    m = process_gcov(p, sc, tmp_path / "out")
    assert m["data_mode"] == "synthetic_fixture"
    assert set(m["layers"]) == {"HHHH", "HVHV"}
    for s in m["sectors"]:
        assert 0 <= s["valid_coverage_fraction"] <= 1
        hv = s["HVHV_db"]["median"]
        assert hv is None or -60 < hv < 10
    (s, w), (n, e) = m["layers"]["HVHV"]["preview_bounds_latlon"]
    assert s < n and w < e and abs(s - (-11.83)) < 0.1


def _write(path, build):
    with h5py.File(path, "w") as f:
        build(f)
    return path


@pytest.mark.parametrize("case", ["empty", "no_grids", "no_coords", "no_terms", "bad_projection"])
def test_malformed_products_raise_value_errors(tmp_path, case):
    def build(f):
        if case == "empty":
            return
        g = f.create_group("/science/LSAR/identification")
        g["granuleId"] = np.bytes_("X")
        if case == "no_grids":
            return
        gr = f.create_group("/science/LSAR/GCOV/grids/frequencyA")
        if case != "no_terms":
            gr["HHHH"] = np.ones((4, 4), dtype="float32")
        if case != "no_coords":
            gr["xCoordinates"] = np.arange(4.0)
            gr["yCoordinates"] = np.arange(4.0)[::-1]
        if case == "bad_projection":
            gr["projection"] = np.bytes_("not-a-code")

    p = _write(tmp_path / f"{case}.h5", build)
    if case == "bad_projection":
        info = inspect_gcov(p)
        assert info.grids[0].epsg is None
        with pytest.raises(ValueError):
            process_gcov(p, get_scenario("carabayllo-rio-seco"), tmp_path / "o")
    else:
        with pytest.raises(ValueError):
            inspect_gcov(p)


def test_non_hdf5_file_raises(tmp_path):
    p = tmp_path / "x.h5"
    p.write_bytes(b"not an hdf5 file" * 10)
    with pytest.raises(OSError):
        inspect_gcov(p)


def test_aoi_outside_product_raises(tmp_path):
    sc = get_scenario("carabayllo-rio-seco")
    other = get_scenario("lower-piura-sechura")
    p = write_synthetic_gcov(tmp_path / "s.h5", other, "baseline")
    with pytest.raises(ValueError):
        process_gcov(p, sc, tmp_path / "o")
    assert math.isfinite(1.0)
