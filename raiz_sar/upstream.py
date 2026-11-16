"""Bounded, deduplicated access to external providers (GIBS, NASA POWER, ASF).

- Server-wide concurrency: at most ``RAIZ_UPSTREAM_SLOTS`` requests in flight across every API and worker
  process on this host (file-lock slots under the runtime directory; locks die with their process).
  Waiting longer than ``RAIZ_UPSTREAM_WAIT_S`` raises :class:`UpstreamBusy` (HTTP 503 + Retry-After)
  instead of piling up threads.
- Retries: 429/502/503/504 and transport errors are retried a bounded number of times with capped
  backoff (``Retry-After`` honoured up to a cap). Other statuses are returned to the caller unchanged.
- Single flight: identical cache builds in different processes run once; the others wait and read it.
- Manifests: cached results carry ``cache.cached_at``/``age_s``. When a refresh fails, the last valid
  result is returned with ``cache.stale = true`` and its age, never silently presented as fresh.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import random
import threading
import time
from pathlib import Path
from typing import Any, Callable, Iterator

import httpx

from . import perf
from .config import get_settings

try:  # Linux containers (the supported runtime); a process-local fallback keeps Windows tooling usable
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

RETRY_STATUSES = frozenset({429, 502, 503, 504})


class UpstreamError(Exception):
    """An external provider failed after bounded retries."""


class UpstreamBusy(UpstreamError):
    def __init__(self, retry_after_s: int = 5):
        super().__init__("External data providers are busy on this server; retry shortly.")
        self.retry_after_s = retry_after_s


def slots() -> int:
    return max(1, int(os.environ.get("RAIZ_UPSTREAM_SLOTS", "12")))


def max_wait_s() -> float:
    return max(0.05, float(os.environ.get("RAIZ_UPSTREAM_WAIT_S", "20")))


def _lock_dir(name: str) -> Path:
    p = get_settings().runtime_dir / "locks" / name
    p.mkdir(parents=True, exist_ok=True)
    return p


_local_sem: threading.BoundedSemaphore | None = None
_local_lock = threading.Lock()


@contextlib.contextmanager
def slot(wait_s: float | None = None) -> Iterator[int]:
    """Hold one of the host-wide upstream slots; raise UpstreamBusy if none frees up in time."""
    wait_s = max_wait_s() if wait_s is None else wait_s
    t0 = time.perf_counter()
    if fcntl is None:  # pragma: no cover - development fallback
        global _local_sem
        with _local_lock:
            if _local_sem is None:
                _local_sem = threading.BoundedSemaphore(slots())
        if not _local_sem.acquire(timeout=wait_s):
            raise UpstreamBusy()
        try:
            yield -1
        finally:
            _local_sem.release()
        return
    d = _lock_dir("upstream")
    n = slots()
    start = random.randrange(n)  # spread contention across slot files
    delay = 0.01
    while True:
        for k in range(n):
            i = (start + k) % n
            fh = open(d / f"{i}.lock", "a+")
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                fh.close()
                continue
            waited = (time.perf_counter() - t0) * 1000
            if waited > 5:
                perf.record("upstream.wait", waited)
            try:
                yield i
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
                fh.close()
            return
        if time.perf_counter() - t0 >= wait_s:
            perf.log({"evt": "upstream_busy", "slots": n, "waited_ms": round((time.perf_counter() - t0) * 1000, 1)})
            raise UpstreamBusy()
        time.sleep(delay)
        delay = min(0.2, delay * 1.6)


def _retry_after(r: httpx.Response, attempt: int, cap_s: float) -> float:
    ra = r.headers.get("Retry-After") if r is not None else None
    if ra and ra.strip().isdigit():
        return min(cap_s, float(ra))
    return min(cap_s, 0.4 * (2 ** attempt)) * (0.75 + random.random() * 0.5)


def get(client: httpx.Client, url: str, *, retries: int = 2, cap_s: float = 4.0, sleep: Callable[[float], None] = time.sleep,
        **kw: Any) -> httpx.Response:
    """GET through a host-wide slot with bounded retries for 429/502/503/504 and transport errors.

    The slot is released while backing off, so a throttled provider does not block other work.
    Returns the last response (possibly a retryable status after the budget); raises UpstreamError when
    every attempt failed at the transport level.
    """
    last_exc: Exception | None = None
    resp: httpx.Response | None = None
    for attempt in range(retries + 1):
        try:
            with slot():
                resp = client.get(url, **kw)
            last_exc = None
        except UpstreamBusy:
            raise
        except httpx.HTTPError as exc:
            last_exc, resp = exc, None
        if resp is not None and resp.status_code not in RETRY_STATUSES:
            return resp
        if attempt < retries:
            if resp is not None:
                perf.log({"evt": "upstream_retry", "status": resp.status_code, "host": httpx.URL(url).host, "attempt": attempt + 1})
            sleep(_retry_after(resp, attempt, cap_s))
    if resp is not None:
        return resp
    raise UpstreamError(f"{httpx.URL(url).host} unreachable: {type(last_exc).__name__}") from last_exc


# ------------------------------------------------------------------ single flight and manifests
@contextlib.contextmanager
def single_flight(key: str, wait_s: float = 120.0) -> Iterator[None]:
    """Exclusive build lock for one cache key across processes (blocking, bounded)."""
    if fcntl is None:  # pragma: no cover
        yield
        return
    path = _lock_dir("build") / (hashlib.sha256(key.encode()).hexdigest()[:24] + ".lock")
    fh = open(path, "a+")
    t0 = time.perf_counter()
    try:
        while True:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.perf_counter() - t0 > wait_s:
                    raise UpstreamBusy(10)
                time.sleep(0.05)
        waited = (time.perf_counter() - t0) * 1000
        if waited > 5:
            perf.record("single_flight.wait", waited)
        yield
    finally:
        with contextlib.suppress(OSError):
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        fh.close()


def _cache_path(kind: str, key: Any) -> Path:
    d = get_settings().runtime_dir / "cache" / kind
    d.mkdir(parents=True, exist_ok=True)
    return d / (hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()[:24] + ".json")


def _read(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write(path: Path, envelope: dict[str, Any]) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(envelope), encoding="utf-8")
    os.replace(tmp, path)


def _view(env: dict[str, Any], stale: bool, reason: str | None = None) -> Any:
    value = env["value"]
    if isinstance(value, dict):
        age = max(0.0, time.time() - env["cached_at"])
        value = {**value, "cache": {"cached_at": round(env["cached_at"], 3), "age_s": round(age, 1), "ttl_s": env["ttl_s"],
                                    "stale": stale, **({"stale_reason": reason} if reason else {})}}
    return value


def peek(kind: str, key: Any) -> Any | None:
    """Fresh cached manifest or None (never builds)."""
    env = _read(_cache_path(kind, key))
    if env and "value" in env and time.time() - env["cached_at"] < env["ttl_s"]:
        return _view(env, False)
    return None


def manifest(kind: str, key: Any, ttl_s: int | Callable[[Any], int], build: Callable[[], Any],
             failures: tuple[type[BaseException], ...] = (UpstreamError, httpx.HTTPError)) -> Any:
    """Cached result with explicit age; serves the last valid result (marked stale) if a refresh fails.

    ``ttl_s`` may be a function of the built value (e.g. a short TTL for an incomplete result).
    Only exceptions in ``failures`` fall back to the stale copy; validation errors propagate.
    """
    path = _cache_path(kind, key)
    env = _read(path)
    now = time.time()
    if env and "value" in env and now - env["cached_at"] < env["ttl_s"]:
        return _view(env, False)
    with single_flight(f"{kind}:{path.name}"):
        env = _read(path)  # another process may have built it while we waited
        if env and "value" in env and time.time() - env["cached_at"] < env["ttl_s"]:
            return _view(env, False)
        try:
            value = build()
        except failures as exc:
            if env and "value" in env:
                perf.log({"evt": "stale_served", "kind": kind, "age_s": round(time.time() - env["cached_at"], 1), "error": type(exc).__name__})
                return _view(env, True, f"refresh failed: {type(exc).__name__}")
            raise
        ttl = ttl_s(value) if callable(ttl_s) else ttl_s
        new = {"cached_at": time.time(), "ttl_s": int(ttl), "value": value}
        _write(path, new)
        return _view(new, False)
