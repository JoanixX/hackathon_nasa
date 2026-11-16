"""Summarize .local/runtime/logs/perf.jsonl: where time goes per API route, span, job and browser phase.

Usage: python tools/perf_report.py [path] [--since SECONDS]
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path


def pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    return s[min(len(s) - 1, int(round(q * (len(s) - 1))))]


def table(title: str, rows: dict[str, list[float]], limit: int = 25) -> None:
    print(f"\n== {title} ==")
    print(f"{'name':58} {'n':>5} {'p50':>9} {'p95':>9} {'max':>9} {'total s':>9}")
    for name, v in sorted(rows.items(), key=lambda kv: -sum(kv[1]))[:limit]:
        print(f"{name[:58]:58} {len(v):5d} {pct(v, .5):9.1f} {pct(v, .95):9.1f} {max(v):9.1f} {sum(v) / 1000:9.1f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default=".local/runtime/logs/perf.jsonl")
    ap.add_argument("--since", type=float, default=None, help="only events from the last N seconds")
    a = ap.parse_args()
    cutoff = time.time() - a.since if a.since else 0
    routes, spans, jobs, client = defaultdict(list), defaultdict(list), defaultdict(list), defaultdict(list)
    durations = defaultdict(list)
    sessions = set()
    statuses, rejected = Counter(), Counter()
    for line in Path(a.path).open(encoding="utf-8"):
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("ts", 0) < cutoff:
            continue
        if e["evt"] == "http":
            routes[f"{e['method']} {e['route']}"].append(e["ms"])
            statuses[(e["route"], e["status"])] += 1
            for s in e.get("spans", []):
                spans[s["name"]].append(s["ms"])
        elif e["evt"] == "job":
            jobs[f"{e['kind']} ({e['state']})"].append(e["ms"])
            for s in e.get("spans", []):
                spans["job:" + s["name"]].append(s["ms"])
        elif e["evt"] == "client":
            sessions.add(e.get("session_id", "legacy"))
            if "duration_ms" in e:
                durations[e["name"]].append(e["duration_ms"])
            else:
                client[e["name"]].append(e["ms"])
        elif e["evt"] == "ai_rejected":
            for err in e.get("errors", []):
                rejected[err[:90]] += 1
    table("API routes (ms)", routes)
    table("Spans inside requests and jobs (ms)", spans)
    table("Jobs (ms)", jobs)
    table("Browser durations (ms, independent of session age)", durations)
    table("Browser marks (ms since page start; compare within a session)", client)
    print(f"\nBrowser sessions: {len(sessions)} (legacy records have no session identity)")
    bad = {k: v for k, v in statuses.items() if k[1] >= 400}
    if bad:
        print("\n== Error responses ==")
        for (route, st), n in sorted(bad.items(), key=lambda kv: -kv[1]):
            print(f"{st} x{n} {route}")
    if rejected:
        print("\n== AI output rejection reasons ==")
        for msg, n in rejected.most_common(10):
            print(f"x{n} {msg}")


if __name__ == "__main__":
    main()
