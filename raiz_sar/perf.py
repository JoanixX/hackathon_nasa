"""Timing instrumentation: per-request spans, structured JSON lines and Server-Timing headers.

Every API request and job writes one JSON line to stdout and to
``<runtime>/logs/perf.jsonl``. ``tools/perf_report.py`` summarizes p50/p95/max per route and span.
"""

from __future__ import annotations

import contextvars
import json
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .config import get_settings

_spans: contextvars.ContextVar[list | None] = contextvars.ContextVar("raiz_spans", default=None)
_write_lock = threading.Lock()


def begin() -> list:
    spans: list = []
    _spans.set(spans)
    return spans


@contextmanager
def span(name: str, **meta: Any):
    """Time a block; recorded on the current request/job when one is active."""
    t0 = time.perf_counter()
    try:
        yield
    finally:
        ms = (time.perf_counter() - t0) * 1000
        spans = _spans.get()
        if spans is not None:
            spans.append({"name": name, "ms": round(ms, 1), **meta})


def record(name: str, ms: float, **meta: Any) -> None:
    """Attach an already-measured duration (e.g. time spent waiting for a slot) to the current request/job."""
    spans = _spans.get()
    if spans is not None:
        spans.append({"name": name, "ms": round(float(ms), 1), **meta})


def log(event: dict[str, Any]) -> None:
    event = {"ts": round(time.time(), 3), "pid": os.getpid(), **event}
    line = json.dumps(event, separators=(",", ":"), default=str)
    print(line, flush=True)
    try:
        path = Path(get_settings().runtime_dir) / "logs" / "perf.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with _write_lock, open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def server_timing(spans: list, total_ms: float) -> str:
    parts = [f"app;dur={total_ms:.1f}"]
    agg: dict[str, float] = {}
    for s in spans:
        agg[s["name"]] = agg.get(s["name"], 0.0) + s["ms"]
    for k, v in list(agg.items())[:12]:
        parts.append(f"{k.replace('.', '_').replace(' ', '_')};dur={v:.1f}")
    return ", ".join(parts)
