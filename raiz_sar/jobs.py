"""Job lifecycle: idempotent submission, legal state transitions, leases and atomic artifacts.

States: validating -> queued -> running -> ready | partial | failed | cancelled.
Transitions use compare-and-set updates so concurrent workers or API calls cannot apply an
illegal or lost update. Retries do not imply exactly-once execution; handlers are idempotent
because artifacts are keyed by job inputs and written atomically.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import and_, func, select, update

from .config import get_settings
from .contracts import JobStatus, content_hash
from .db import engine, jobs

LEGAL: dict[str, set[str]] = {
    "validating": {"queued", "failed"},
    "queued": {"running", "cancelled", "failed"},
    "running": {"ready", "partial", "failed", "cancelled", "queued"},
    "failed": {"queued"},
    "cancelled": {"queued"},
    "partial": {"queued"},
    "ready": {"queued"},  # only when its artifact is missing (see submit); a ready job is never re-run otherwise
}
ACTIVE = {"validating", "queued", "running"}
QUEUE_FOR = {"scene": "ai", "report": "ai", "sar_process": "sar", "sar_discover": "sar"}


class QueueFull(Exception):
    def __init__(self, retry_after_s: int = 15):
        super().__init__("Job queue is full; retry later.")
        self.retry_after_s = retry_after_s


class IllegalTransition(Exception):
    pass


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds")


def is_legal(old: str, new: str) -> bool:
    return new in LEGAL.get(old, set())


def job_id_for(kind: str, inputs: dict[str, Any]) -> str:
    return f"{kind[:6]}-" + content_hash({"kind": kind, "inputs": inputs}, 24)


def _row_to_status(row) -> JobStatus:
    return JobStatus(job_id=row.job_id, kind=row.kind, state=row.state, plan_version=row.plan_version,
                     attempts=row.attempts, created_at=row.created_at, updated_at=row.updated_at,
                     result_ref=row.result_ref, error_code=row.error_code, error_message=row.error_message)


def get(job_id: str) -> JobStatus | None:
    with engine().connect() as c:
        row = c.execute(select(jobs).where(jobs.c.job_id == job_id)).first()
    return _row_to_status(row) if row else None


def inputs_of(job_id: str) -> dict[str, Any]:
    with engine().connect() as c:
        row = c.execute(select(jobs.c.inputs).where(jobs.c.job_id == job_id)).first()
    if not row:
        raise KeyError(job_id)
    return json.loads(row[0])


def transition(job_id: str, old: str, new: str, **fields: Any) -> bool:
    """Atomic compare-and-set. Returns False if the job is no longer in ``old``."""
    if not is_legal(old, new):
        raise IllegalTransition(f"{old} -> {new}")
    values = {"state": new, "updated_at": _now(), **fields}
    with engine().begin() as c:
        res = c.execute(update(jobs).where(and_(jobs.c.job_id == job_id, jobs.c.state == old)).values(**values))
    return res.rowcount == 1


def _enqueue(job_id: str, queue: str) -> None:
    s = get_settings()
    if s.queue_mode == "inline":
        run(job_id)
        return
    from redis import Redis
    from rq import Queue

    conn = Redis.from_url(s.valkey_url, socket_timeout=5, socket_connect_timeout=3)
    q = Queue(queue, connection=conn, default_timeout=7200 if queue == "sar" else 900)
    # Only this fixed function is ever enqueued, with a job-id string argument (no client callables).
    q.enqueue("raiz_sar.tasks.execute", job_id, job_id=f"rq-{job_id}-{int(time.time() * 1000)}",
              result_ttl=3600, failure_ttl=86400)


def submit(kind: str, inputs: dict[str, Any], plan_version: str | None) -> JobStatus:
    s = get_settings()
    queue = QUEUE_FOR[kind]
    jid = job_id_for(kind, inputs)
    reap_expired()
    existing = get(jid)
    if existing and existing.state == "ready" and existing.result_ref and not artifact_exists(existing.result_ref):
        pass  # the result was lost (disk cleanup): re-run instead of returning an empty ready job
    elif existing and existing.state in ACTIVE | {"ready"}:
        return existing  # idempotent: identical request returns the same job
    with engine().connect() as c:
        depth = c.execute(select(func.count()).select_from(jobs).where(
            and_(jobs.c.queue == queue, jobs.c.state.in_(["queued", "running"])))).scalar_one()
    if depth >= s.max_queue_depth:
        raise QueueFull()
    if existing:
        if not transition(jid, existing.state, "queued", error_code=None, error_message=None, attempts=0):
            return get(jid)  # another request re-queued it first
    else:
        now = _now()
        try:
            with engine().begin() as c:
                c.execute(jobs.insert().values(job_id=jid, kind=kind, queue=queue, state="validating",
                                               plan_version=plan_version, inputs=json.dumps(inputs, sort_keys=True),
                                               attempts=0, created_at=now, updated_at=now))
        except Exception:
            cur = get(jid)
            if cur:
                return cur  # concurrent identical insert won the race
            raise
        transition(jid, "validating", "queued")
    try:
        _enqueue(jid, queue)
    except Exception as exc:  # queue backend unavailable
        cur = get(jid)
        if cur and cur.state == "queued":
            transition(jid, "queued", "failed", error_code="queue_unavailable", error_message=str(exc)[:300])
    return get(jid)


def cancel(job_id: str) -> JobStatus | None:
    cur = get(job_id)
    if cur and cur.state in ("queued", "running"):
        transition(job_id, cur.state, "cancelled", error_code="cancelled", error_message="Cancelled by the user.")
    return get(job_id)


def reap_expired() -> int:
    """Recover jobs whose worker died (lease expired): requeue within attempt budget, else fail."""
    s = get_settings()
    now = int(time.time())
    with engine().connect() as c:
        rows = c.execute(select(jobs.c.job_id, jobs.c.attempts, jobs.c.queue).where(
            and_(jobs.c.state == "running", jobs.c.lease_expires_at < now))).all()
    n = 0
    for jid, attempts, queue in rows:
        if attempts < s.max_job_attempts:
            if transition(jid, "running", "queued", lease_expires_at=None, error_code="worker_lost",
                          error_message="Worker lease expired; job re-queued."):
                n += 1
                try:
                    _enqueue(jid, queue)
                except Exception as exc:
                    transition(jid, "queued", "failed", error_code="queue_unavailable", error_message=str(exc)[:300])
        else:
            if transition(jid, "running", "failed", lease_expires_at=None, error_code="worker_lost",
                          error_message="Worker lease expired and the attempt budget is exhausted."):
                n += 1
    return n


def write_artifact(kind: str, name: str, body: dict[str, Any]) -> str:
    base = get_settings().artifact_dir / kind
    base.mkdir(parents=True, exist_ok=True)
    final = base / f"{name}.json"
    fd, tmp = tempfile.mkstemp(dir=base, prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(body, fh, ensure_ascii=False, allow_nan=False)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, final)  # atomic publication: readers see the old or the complete new file
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return f"{kind}/{name}.json"


def artifact_exists(ref: str) -> bool:
    base = get_settings().artifact_dir.resolve()
    path = (base / ref).resolve()
    return base in path.parents and path.is_file()


def read_artifact(ref: str) -> dict[str, Any]:
    base = get_settings().artifact_dir.resolve()
    path = (base / ref).resolve()
    if base not in path.parents:
        raise KeyError(ref)
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class JobFailure(Exception):
    def __init__(self, code: str, message: str, partial_ref: str | None = None):
        super().__init__(message)
        self.code = code
        self.partial_ref = partial_ref


HANDLERS: dict[str, Callable[[dict[str, Any]], str]] = {}


def handler(kind: str):
    def deco(fn):
        HANDLERS[kind] = fn
        return fn
    return deco


def run(job_id: str) -> str:
    """Execute a job once. Safe to call repeatedly: only a queued job is started."""
    s = get_settings()
    cur = get(job_id)
    if cur is None or cur.state != "queued":
        return cur.state if cur else "missing"
    # Granule downloads (1-7 GB) need a longer lease than AI jobs; the reaper must not requeue them mid-download.
    lease = int(time.time()) + s.job_lease_s * (24 if cur.kind == "sar_process" else 1)
    if not transition(job_id, "queued", "running", attempts=cur.attempts + 1, lease_expires_at=lease):
        return get(job_id).state
    from . import tasks  # noqa: F401  (registers handlers)

    try:
        ref = HANDLERS[cur.kind](inputs_of(job_id))
    except JobFailure as exc:
        if exc.partial_ref:
            transition(job_id, "running", "partial", result_ref=exc.partial_ref, error_code=exc.code,
                       error_message=str(exc)[:500], lease_expires_at=None)
        else:
            transition(job_id, "running", "failed", error_code=exc.code, error_message=str(exc)[:500], lease_expires_at=None)
        return get(job_id).state
    except Exception as exc:  # unexpected: record without leaking internals to clients
        transition(job_id, "running", "failed", error_code="internal_error",
                   error_message=f"{type(exc).__name__}: {str(exc)[:300]}", lease_expires_at=None)
        return get(job_id).state
    transition(job_id, "running", "ready", result_ref=ref, error_code=None, error_message=None, lease_expires_at=None)
    return get(job_id).state
