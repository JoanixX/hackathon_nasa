"""Stateful model of the job lifecycle, idempotency, leases and concurrent submission."""

from __future__ import annotations

import threading
import time

import pytest
from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, rule

from conftest import budget
from raiz_sar import jobs
from raiz_sar.db import engine, jobs as jobs_table

OUTCOMES = ["ok", "fail", "partial", "crash"]
CALLS: list[str] = []


def _handler(inputs):
    CALLS.append(inputs["key"])
    o = inputs["outcome"]
    if o == "fail":
        raise jobs.JobFailure("test_fail", "planned failure")
    if o == "partial":
        raise jobs.JobFailure("test_partial", "planned partial", partial_ref=jobs.write_artifact("test", inputs["key"], {"k": 1}))
    if o == "crash":
        raise RuntimeError("unexpected")
    return jobs.write_artifact("test", inputs["key"], {"k": inputs["key"]})


@pytest.fixture(autouse=True)
def manual_queue(monkeypatch):
    queued: list[str] = []
    monkeypatch.setitem(jobs.HANDLERS, "scene", _handler)
    monkeypatch.setattr(jobs, "_enqueue", lambda jid, q: queued.append(jid))
    import raiz_sar.tasks  # noqa: F401  (ensure real handlers are registered before overriding)
    monkeypatch.setitem(jobs.HANDLERS, "scene", _handler)
    with engine().begin() as c:
        c.execute(jobs_table.delete())
    yield queued


class JobMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.model: dict[str, str] = {}
        self.history: dict[str, list[str]] = {}

    @initialize()
    def reset(self):
        with engine().begin() as c:
            c.execute(jobs_table.delete())
        jobs.HANDLERS["scene"] = _handler

    def _observe(self, jid):
        st_ = jobs.get(jid)
        if st_ is None:
            return
        hist = self.history.setdefault(jid, [])
        if not hist or hist[-1] != st_.state:
            if hist:
                prev = hist[-1]
                # Observed changes must be compositions of legal transitions; a single observed step is
                # legal or reachable through running (run() may pass queued->running->terminal).
                assert jobs.is_legal(prev, st_.state) or (
                    jobs.is_legal(prev, "running") and jobs.is_legal("running", st_.state)
                ) or (jobs.is_legal(prev, "queued") and jobs.is_legal("queued", st_.state)), (prev, st_.state)
            hist.append(st_.state)
        self.model[jid] = st_.state

    @rule(key=st.integers(0, 4), outcome=st.sampled_from(OUTCOMES))
    def submit(self, key, outcome):
        inputs = {"key": f"k{key}", "outcome": outcome}
        before = jobs.get(jobs.job_id_for("scene", inputs))
        st_ = jobs.submit("scene", inputs, None)
        assert st_.job_id == jobs.job_id_for("scene", inputs)
        if before and before.state in ("queued", "running", "ready"):
            assert st_.state == before.state  # idempotent: active/ready jobs are returned, not duplicated
        self._observe(st_.job_id)

    @rule(data=st.data())
    def run_one(self, data):
        if not self.model:
            return
        jid = data.draw(st.sampled_from(sorted(self.model)))
        before = jobs.get(jid).state
        n = len(CALLS)
        jobs.run(jid)
        if before != "queued":
            assert len(CALLS) == n  # only queued jobs execute; ready jobs never re-run
        self._observe(jid)

    @rule(data=st.data())
    def cancel(self, data):
        if not self.model:
            return
        jid = data.draw(st.sampled_from(sorted(self.model)))
        jobs.cancel(jid)
        self._observe(jid)

    @rule(data=st.data())
    def worker_dies(self, data):
        """Simulate a worker crash: a queued job is claimed, then its lease expires."""
        queued = [j for j, s in self.model.items() if s == "queued"]
        if not queued:
            return
        jid = data.draw(st.sampled_from(sorted(queued)))
        cur = jobs.get(jid)
        if jobs.transition(jid, "queued", "running", attempts=cur.attempts + 1, lease_expires_at=int(time.time()) - 5):
            self._observe(jid)
        jobs.reap_expired()
        self._observe(jid)

    @invariant()
    def states_are_known_and_attempts_bounded(self):
        with engine().connect() as c:
            rows = c.execute(jobs_table.select()).all()
        for r in rows:
            assert r.state in jobs.LEGAL
            assert 0 <= r.attempts <= jobs.get_settings().max_job_attempts + 1
            if r.state == "ready":
                assert r.result_ref and r.error_code is None
            if r.state == "failed":
                assert r.error_code


JobMachine.TestCase.settings = settings(max_examples=budget(300), stateful_step_count=25, deadline=None)
TestJobMachine = JobMachine.TestCase


def test_illegal_transition_raises():
    with pytest.raises(jobs.IllegalTransition):
        jobs.transition("x", "ready", "running")


def test_concurrent_identical_submissions_create_one_job(manual_queue):
    inputs = {"key": "race", "outcome": "ok"}
    results = []

    def go():
        results.append(jobs.submit("scene", inputs, None).job_id)

    threads = [threading.Thread(target=go) for _ in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(set(results)) == 1
    with engine().connect() as c:
        assert len(c.execute(jobs_table.select()).all()) == 1


def test_concurrent_runs_execute_handler_once(manual_queue):
    inputs = {"key": "once", "outcome": "ok"}
    jid = jobs.submit("scene", inputs, None).job_id
    CALLS.clear()
    threads = [threading.Thread(target=jobs.run, args=(jid,)) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert CALLS.count("once") == 1
    assert jobs.get(jid).state == "ready"


def test_queue_full_raises(monkeypatch, manual_queue):
    from raiz_sar import config

    s = config.get_settings()
    monkeypatch.setattr(jobs, "get_settings", lambda: s.__class__(**{**s.__dict__, "max_queue_depth": 1}))
    jobs.submit("scene", {"key": "a", "outcome": "ok"}, None)
    with pytest.raises(jobs.QueueFull):
        jobs.submit("scene", {"key": "b", "outcome": "ok"}, None)


def test_queue_unavailable_marks_job_failed(monkeypatch):
    monkeypatch.setitem(jobs.HANDLERS, "scene", _handler)

    def boom(jid, q):
        raise ConnectionError("valkey down")

    monkeypatch.setattr(jobs, "_enqueue", boom)
    st_ = jobs.submit("scene", {"key": "down", "outcome": "ok"}, None)
    assert st_.state == "failed" and st_.error_code == "queue_unavailable"


def test_artifact_path_traversal_rejected():
    with pytest.raises(KeyError):
        jobs.read_artifact("../../etc/passwd")
