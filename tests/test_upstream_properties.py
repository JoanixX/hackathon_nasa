"""Phase 3 evidence-job properties: bounded upstream concurrency, bounded retries, single flight,
explicit staleness, worker-built ponding and API responsiveness under upstream saturation."""

from __future__ import annotations

import multiprocessing as mp
import threading
import time

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st

from conftest import budget
from raiz_sar import upstream as U


class FakeResp:
    def __init__(self, status: int, headers: dict | None = None, content: bytes = b"x"):
        self.status_code = status
        self.headers = headers or {}
        self.content = content


class FakeClient:
    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def get(self, url, **kw):
        self.calls += 1
        item = self.script[min(self.calls - 1, len(self.script) - 1)]
        if isinstance(item, Exception):
            raise item
        return item


# ------------------------------------------------------------------ retries
@settings(max_examples=budget(1500))
@given(st.lists(st.sampled_from([200, 404, 500, 429, 502, 503, 504, "err"]), min_size=1, max_size=6), st.integers(0, 3),
       st.one_of(st.none(), st.integers(0, 120)))
def test_retries_are_bounded_and_only_for_transient_failures(seq, retries, retry_after):
    script = [httpx.ConnectError("x") if s == "err" else FakeResp(s, {"Retry-After": str(retry_after)} if retry_after is not None else {}) for s in seq]
    client, sleeps = FakeClient(script), []
    try:
        r = U.get(client, "https://gibs.example/x", retries=retries, cap_s=4.0, sleep=sleeps.append)
        out = r.status_code
    except U.UpstreamError:
        out = "error"
    # Oracle: walk the script the way the contract says.
    expected_calls, expected = 0, None
    for attempt in range(retries + 1):
        item = seq[min(attempt, len(seq) - 1)]
        expected_calls += 1
        if item != "err" and item not in U.RETRY_STATUSES:
            expected = item
            break
        expected = item
    if expected == "err":
        expected = "error"
    assert client.calls == expected_calls <= retries + 1
    assert out == expected
    assert len(sleeps) == expected_calls - 1  # no sleep after the final attempt
    assert all(0 <= s <= 4.0 for s in sleeps)  # backoff and Retry-After are capped


# ------------------------------------------------------------------ host-wide slots
def _hold(n_slots, hold_s, q, wait_s):
    import os

    os.environ["RAIZ_UPSTREAM_SLOTS"] = str(n_slots)
    try:
        with U.slot(wait_s):
            q.put(("in", time.monotonic()))
            time.sleep(hold_s)
            q.put(("out", time.monotonic()))
    except U.UpstreamBusy:
        q.put(("busy", time.monotonic()))


@settings(max_examples=budget(12), deadline=None)
@given(st.integers(1, 4), st.integers(2, 7))
def test_slots_bound_concurrency_across_processes(n_slots, n_procs):
    import os

    os.environ["RAIZ_UPSTREAM_SLOTS"] = str(n_slots)
    ctx = mp.get_context("fork")
    q = ctx.Queue()
    procs = [ctx.Process(target=_hold, args=(n_slots, 0.25, q, 10.0)) for _ in range(n_procs)]
    for p in procs:
        p.start()
    for p in procs:
        p.join(30)
    events = sorted([q.get(timeout=5) for _ in range(2 * n_procs)], key=lambda e: e[1])
    level = peak = 0
    for kind, _t in events:
        level += 1 if kind == "in" else -1
        peak = max(peak, level)
    assert peak <= n_slots
    assert sum(k == "in" for k, _ in events) == n_procs  # everyone eventually got a slot


def test_saturated_slots_raise_busy_instead_of_waiting_forever(monkeypatch):
    monkeypatch.setenv("RAIZ_UPSTREAM_SLOTS", "1")
    held, release = threading.Event(), threading.Event()

    def holder():
        with U.slot(1.0):
            held.set()
            release.wait(5)

    t = threading.Thread(target=holder)
    t.start()
    held.wait(5)
    t0 = time.monotonic()
    with pytest.raises(U.UpstreamBusy):
        with U.slot(0.3):
            pass
    assert time.monotonic() - t0 < 2.0
    release.set()
    t.join()


# ------------------------------------------------------------------ manifests and single flight
@settings(max_examples=budget(40), deadline=None)
@given(st.integers(2, 10), st.text("abcdef", min_size=1, max_size=6))
def test_concurrent_identical_builds_run_once(n_threads, key):
    calls = []

    def build():
        calls.append(1)
        time.sleep(0.05)
        return {"v": key}

    kind = f"t_once_{time.time_ns()}"
    out = []
    ts = [threading.Thread(target=lambda: out.append(U.manifest(kind, [key], 3600, build))) for _ in range(n_threads)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert len(calls) == 1
    assert all(o["v"] == key and o["cache"]["stale"] is False for o in out)


def test_failed_refresh_serves_last_valid_copy_marked_stale():
    kind = f"t_stale_{time.time_ns()}"
    first = U.manifest(kind, ["k"], 0, lambda: {"dates": ["2026-02-12"]})  # ttl 0: next call refreshes
    assert first["cache"]["stale"] is False

    def broken():
        raise U.UpstreamError("down")

    second = U.manifest(kind, ["k"], 0, broken)
    assert second["dates"] == ["2026-02-12"] and second["cache"]["stale"] is True and second["cache"]["age_s"] >= 0
    assert "refresh failed" in second["cache"]["stale_reason"]


def test_failure_without_any_copy_propagates_and_validation_errors_never_fall_back():
    kind = f"t_none_{time.time_ns()}"
    with pytest.raises(U.UpstreamError):
        U.manifest(kind, ["k"], 3600, lambda: (_ for _ in ()).throw(U.UpstreamError("down")))
    U.manifest(kind, ["v"], 0, lambda: {"ok": 1})
    with pytest.raises(ValueError):
        U.manifest(kind, ["v"], 0, lambda: (_ for _ in ()).throw(ValueError("bad input")))


@settings(max_examples=budget(300))
@given(st.integers(0, 5), st.booleans())
def test_ttl_function_shortens_incomplete_results(errors, recent):
    import datetime as dt

    from raiz_sar.sources import _manifest_ttl

    end = (dt.date.today() - dt.timedelta(days=1 if recent else 400)).isoformat()
    ttl = _manifest_ttl(end, 6 * 3600, 7 * 86400)({"probe_errors": errors})
    assert ttl == (600 if errors else (6 * 3600 if recent else 7 * 86400))


# ------------------------------------------------------------------ provider errors in date probes
def test_probe_5xx_is_unknown_not_zero_and_not_cached(monkeypatch):
    import raiz_sar.sources as S

    client = FakeClient([FakeResp(500)])
    monkeypatch.setattr(U, "get", lambda c, url, **kw: client.get(url))
    assert S._probe(client, "dswx", "2026-02-12", 10, 280, 529) is None
    assert S._probe(client, "dswx", "2026-02-12", 10, 280, 529) is None
    assert client.calls == 2  # the failure was not cached as "no data"


# ------------------------------------------------------------------ ponding as an evidence job
def _water_tile():
    import warnings

    from rasterio.errors import NotGeoreferencedWarning
    from rasterio.io import MemoryFile

    a = np.zeros((4, 256, 256), dtype="uint8")
    a[:3] = 255
    a[3] = 255
    a[0, 100:140, 100:140], a[1, 100:140, 100:140], a[2, 100:140, 100:140] = 0, 0, 255  # open water
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", NotGeoreferencedWarning)
        with MemoryFile() as mf:
            with mf.open(driver="PNG", width=256, height=256, count=4, dtype="uint8") as d:
                d.write(a)
            return mf.read()


def test_ponding_runs_once_as_a_job_then_is_served_from_cache(monkeypatch):
    import raiz_sar.sources as S
    from raiz_sar.api import app

    png = _water_tile()
    calls = []

    def fake_get(client, url, **kw):
        calls.append(url)
        return FakeResp(200, content=png)

    monkeypatch.setattr(U, "get", fake_get)
    c = TestClient(app)
    q = {"west": -80.64, "south": -5.21, "east": -80.62, "north": -5.19, "date": "2026-02-12"}
    r1 = c.get("/api/sources/ponding", params=q)
    assert r1.status_code == 202, r1.text
    job = r1.json()
    assert job["state"] == "ready" and job["result"]["features"], job  # inline queue in tests
    n_fetch = len(calls)
    assert n_fetch >= 1
    r2 = c.get("/api/sources/ponding", params=q)
    assert r2.status_code == 200 and r2.json()["cache"]["stale"] is False
    r3 = c.get("/api/sources/ponding", params=q)
    assert r3.status_code == 200 and len(calls) == n_fetch  # identical requests do no external work
    assert job["result"]["pixel_counts"]["open_water"] > 0


def test_invalid_ponding_request_never_creates_a_job():
    from raiz_sar.api import app

    c = TestClient(app)
    r = c.get("/api/sources/ponding", params={"west": -80, "south": -5, "east": -79, "north": -4, "date": "2026-02-12"})
    assert r.status_code == 422
    r = c.get("/api/sources/ponding", params={"west": -80.64, "south": -5.21, "east": -80.62, "north": -5.19, "date": "12/02/2026"})
    assert r.status_code == 422


# ------------------------------------------------------------------ API under upstream saturation
def test_busy_upstream_is_503_with_retry_after_and_interactive_reads_stay_fast(monkeypatch):
    from raiz_sar.api import app

    monkeypatch.setenv("RAIZ_UPSTREAM_SLOTS", "1")
    monkeypatch.setenv("RAIZ_UPSTREAM_WAIT_S", "0.2")
    held, release = threading.Event(), threading.Event()

    def holder():
        with U.slot(1.0):
            held.set()
            release.wait(10)

    t = threading.Thread(target=holder)
    t.start()
    held.wait(5)
    try:
        c = TestClient(app)
        r = c.get("/api/sources/dates", params={"layer": "hls_s30", "lon": -80.63, "lat": -5.2, "start": "2026-01-03", "end": "2026-01-04"})
        assert r.status_code == 503 and r.json()["error"] == "upstream_busy" and int(r.headers["Retry-After"]) > 0
        t0 = time.monotonic()
        assert c.get("/api/health").status_code == 200
        assert c.get("/api/scenarios").status_code == 200
        assert time.monotonic() - t0 < 2.0  # health/scenario reads never wait for upstream slots
    finally:
        release.set()
        t.join()
