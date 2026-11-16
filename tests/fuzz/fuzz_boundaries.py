"""Bounded mutation fuzzing of input boundaries (GIS import, AI scene output, report output, plan API).

Mutation-based (byte and structure level) with per-input time limits and a process memory cap.
This is NOT coverage-guided fuzzing. Unexpected exception types, timeouts and invariant breaks are
saved under .local/fuzz/<target>/ with the input bytes for replay.

Usage (Linux container): python tests/fuzz/fuzz_boundaries.py --iterations 20000 --seed 1
Replay one file:          python tests/fuzz/fuzz_boundaries.py --replay .local/fuzz/gis/crash-*.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import resource
import signal
import sys
import time
from pathlib import Path

os.environ.setdefault("RAIZ_QUEUE_MODE", "inline")
os.environ.setdefault("RAIZ_AI_PROVIDER", "fixture")
os.environ.setdefault("RAIZ_RUNTIME_DIR", "/tmp/raiz-fuzz")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from raiz_sar.api import ClientPerf  # noqa: E402
from raiz_sar.contracts import AIReportSections, PlanRequest  # noqa: E402
from raiz_sar.gis_import import ImportErrorReport, normalize_feature_collection  # noqa: E402
from raiz_sar.plans import PlanInputError, build_plan, resolve_dataset  # noqa: E402
from raiz_sar.scenarios import get_scenario  # noqa: E402
from raiz_sar.scene import build_prompt, fixture_scene_responder, scene_context, validate_ai_plan  # noqa: E402

OUT = Path(".local/fuzz")
MAX_INPUT = 256 * 1024
PER_CASE_S = 5
TOKENS = [b"NaN", b"Infinity", b"-1e309", b"1e309", b"null", b"[]", b"{}", b'"\\u0000"', b'"<script>"', b"-0",
          b"9" * 400, b'"' + b"A" * 5000 + b'"', b"true", b"[" * 200, b'{"type":"Polygon"}']


class Timeout(Exception):
    pass


def _alarm(_s, _f):
    raise Timeout()


def mutate(data: bytes, rng: random.Random) -> bytes:
    b = bytearray(data)
    for _ in range(rng.randint(1, 6)):
        op = rng.randrange(6)
        pos = rng.randrange(len(b) + 1) if b else 0
        if op == 0 and b:
            b[rng.randrange(len(b))] ^= 1 << rng.randrange(8)
        elif op == 1 and b:
            del b[pos:pos + rng.randint(1, 32)]
        elif op == 2:
            b[pos:pos] = rng.choice(TOKENS)
        elif op == 3 and b:
            j = rng.randrange(len(b))
            b[pos:pos] = b[j:j + rng.randint(1, 64)]
        elif op == 4:
            b = b[: rng.randrange(len(b) + 1)]
        else:
            b[pos:pos] = bytes(rng.randrange(256) for _ in range(rng.randint(1, 8)))
    return bytes(b[:MAX_INPUT])


VALUES = [None, True, False, 0, -1, 1e308, -1e308, 2**63, "", "x" * 3000, "<script>", "NaN", [], {}, [[]], {"type": "Polygon"},
          -77.0, -11.8, 1000.0, "tara", "CRB-04", "ZZZ", 0.5, 12, [0, 3, 6, 12]]


def mutate_structure(data: bytes, rng: random.Random) -> bytes:
    """JSON-tree mutation: replace, delete or duplicate random nodes so inputs stay parseable."""
    try:
        doc = json.loads(data)
    except ValueError:
        return mutate(data, rng)
    for _ in range(rng.randint(1, 4)):
        nodes = []

        def walk(n, parent, key, depth):
            nodes.append((parent, key))
            if depth > 12:
                return
            if isinstance(n, dict):
                for k, v in list(n.items()):
                    walk(v, n, k, depth + 1)
            elif isinstance(n, list):
                for i, v in enumerate(n):
                    walk(v, n, i, depth + 1)

        walk(doc, None, None, 0)
        parent, key = rng.choice(nodes)
        if parent is None:
            continue
        op = rng.randrange(4)
        if op == 0:
            parent[key] = rng.choice(VALUES)
        elif op == 1:
            del parent[key]
        elif op == 2 and isinstance(parent, list):
            parent.insert(key, parent[key])
        else:
            v = parent[key]
            parent[key] = v * rng.choice([-1, 10, 1e6]) if isinstance(v, (int, float)) and not isinstance(v, bool) else rng.choice(VALUES)
    return json.dumps(doc, allow_nan=True).encode()[:MAX_INPUT]


def _scene_ctx():
    sid = "carabayllo-rio-seco"
    req = PlanRequest(scenario_id=sid, dataset_version=get_scenario(sid)["summary"]["dataset_version"], budget_pen=12000)
    plan = build_plan(req)
    return scene_context(plan, resolve_dataset(req))


SCENE_CTX = _scene_ctx()


def t_gis(data: bytes):
    try:
        obj = json.loads(data)
    except (ValueError, RecursionError):
        return
    try:
        out = normalize_feature_collection(obj, "carabayllo-rio-seco", "fuzz")
    except (ImportErrorReport, RecursionError):
        return
    from shapely.geometry import shape

    for f in out["sectors"]["features"]:
        assert shape(f["geometry"]).is_valid, "accepted invalid geometry"


def t_scene(data: bytes):
    ai, errors = validate_ai_plan(data.decode("utf-8", "replace"), SCENE_CTX)
    assert (ai is None) == bool(errors), "validator verdict inconsistent"
    if ai is not None:
        funded = {s["sector_id"] for s in SCENE_CTX["funded_sectors"]}
        assert {z.sector_id for z in ai.zones} <= funded, "accepted a non-funded sector"


def t_report(data: bytes):
    try:
        AIReportSections.model_validate_json(data)
    except ValueError:
        return


def t_plan(data: bytes):
    try:
        req = PlanRequest.model_validate_json(data)
    except ValueError:
        return
    try:
        plan = build_plan(req)
    except PlanInputError:
        return
    assert plan.budget.total_cost_cents >= 0


def t_perf(data: bytes):
    try:
        out = ClientPerf.model_validate_json(data)
    except ValueError:
        return
    import math

    assert len(out.events) <= 200
    for event in out.events:
        assert math.isfinite(event.ms) and 0 <= event.ms <= 604800000
        if event.duration_ms is not None:
            assert math.isfinite(event.duration_ms) and 0 <= event.duration_ms <= 604800000


def seeds():
    gis = json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature", "id": "A", "geometry": {"type": "Polygon",
          "coordinates": [[[-77.02, -11.84], [-77.01, -11.84], [-77.01, -11.83], [-77.02, -11.84]]]},
          "properties": {"nombre": "x", "hectareas": 10, "pendiente": 30, "sigma_hh": -12, "especie": "tara"}}]}).encode()
    scene = fixture_scene_responder(build_prompt(SCENE_CTX), {}).encode()
    report = json.dumps({"executive_summary": "x", "field_checks": ["a"], "monitoring_protocol": ["b"], "risks_and_limitations": ["c"]}).encode()
    ds = get_scenario("lower-piura-sechura")["summary"]["dataset_version"]
    plan = json.dumps({"scenario_id": "lower-piura-sechura", "dataset_version": ds, "budget_pen": 9000}).encode()
    telemetry = json.dumps({"session_id": "fuzz-session", "events": [{"name": "api.request", "ms": 8000, "duration_ms": 30, "detail": "local"}]}).encode()
    return {"perf": (t_perf, [telemetry]), "gis": (t_gis, [gis]), "scene": (t_scene, [scene]), "report": (t_report, [report]), "plan": (t_plan, [plan])}


def run(iterations: int, seed: int) -> dict:
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    signal.signal(signal.SIGALRM, _alarm)
    rng = random.Random(seed)
    summary = {"seed": seed, "iterations_per_target": iterations, "engine": "mutation (not coverage-guided)", "targets": {}}
    for name, (fn, corpus) in seeds().items():
        found, t0, executed, parseable = 0, time.monotonic(), 0, 0
        corpus = list(corpus)
        for i in range(iterations):
            base = rng.choice(corpus)
            data = mutate_structure(base, rng) if rng.random() < 0.7 else mutate(base, rng)
            try:
                json.loads(data)
                parseable += 1
            except (ValueError, RecursionError):
                pass
            signal.alarm(PER_CASE_S)
            try:
                fn(data)
                if i % 50 == 0 and len(corpus) < 64:
                    corpus.append(data)  # keep some mutants as further seeds
            except Timeout:
                found += _save(name, "timeout", data, "exceeded per-case time limit")
            except AssertionError as exc:
                found += _save(name, "invariant", data, str(exc))
            except MemoryError:
                found += _save(name, "oom", data, "memory limit")
            except Exception as exc:  # unexpected exception type at a validated boundary
                found += _save(name, "crash", data, f"{type(exc).__name__}: {exc}"[:500])
            finally:
                signal.alarm(0)
            executed += 1
        summary["targets"][name] = {"executed": executed, "parseable_json": parseable, "findings": found,
                                    "seconds": round(time.monotonic() - t0, 1)}
    return summary


def _save(target: str, kind: str, data: bytes, why: str) -> int:
    d = OUT / target
    d.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256(data).hexdigest()[:12]
    (d / f"{kind}-{h}.bin").write_bytes(data)
    (d / f"{kind}-{h}.txt").write_text(why, encoding="utf-8")
    return 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iterations", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--replay")
    a = ap.parse_args()
    if a.replay:
        p = Path(a.replay)
        target = p.parent.name
        seeds()[target][0](p.read_bytes())
        print("replay passed")
        return
    s = run(a.iterations, a.seed)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(s, indent=1), encoding="utf-8")
    print(json.dumps(s))


if __name__ == "__main__":
    main()
