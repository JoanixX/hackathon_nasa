"""SQLite pilot metadata store (WAL, foreign keys, short transactions)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import Column, Integer, MetaData, String, Table, Text, create_engine, event, select
from sqlalchemy.engine import Engine

from .config import get_settings

metadata = MetaData()

plans = Table(
    "plans", metadata,
    Column("plan_version", String(32), primary_key=True),
    Column("scenario_id", String(64), nullable=False),
    Column("body", Text, nullable=False),
    Column("created_at", String(40), nullable=False),
)

datasets = Table(
    "datasets", metadata,
    Column("dataset_version", String(64), primary_key=True),
    Column("scenario_id", String(64), nullable=False),
    Column("body", Text, nullable=False),
)

jobs = Table(
    "jobs", metadata,
    Column("job_id", String(40), primary_key=True),
    Column("kind", String(32), nullable=False),
    Column("queue", String(16), nullable=False),
    Column("state", String(16), nullable=False),
    Column("plan_version", String(32)),
    Column("inputs", Text, nullable=False),
    Column("attempts", Integer, nullable=False, default=0),
    Column("lease_expires_at", Integer),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
    Column("result_ref", String(256)),
    Column("error_code", String(64)),
    Column("error_message", Text),
)


def _configure(dbapi_conn, _record):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA busy_timeout=5000")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.close()


@lru_cache(maxsize=4)
def _engine_for(path: str) -> Engine:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    eng = create_engine(f"sqlite:///{path}", future=True, connect_args={"timeout": 5, "check_same_thread": False})
    event.listen(eng, "connect", _configure)
    metadata.create_all(eng)
    return eng


def engine() -> Engine:
    return _engine_for(str(get_settings().database_path))


def save_plan(plan_version: str, scenario_id: str, body: dict[str, Any], created_at: str) -> None:
    with engine().begin() as c:
        exists = c.execute(select(plans.c.plan_version).where(plans.c.plan_version == plan_version)).first()
        if not exists:
            c.execute(plans.insert().values(plan_version=plan_version, scenario_id=scenario_id,
                                            body=json.dumps(body, ensure_ascii=False), created_at=created_at))


def load_plan(plan_version: str) -> dict[str, Any] | None:
    with engine().connect() as c:
        row = c.execute(select(plans.c.body).where(plans.c.plan_version == plan_version)).first()
    return json.loads(row[0]) if row else None


def save_dataset(dataset_version: str, scenario_id: str, body: dict[str, Any]) -> None:
    with engine().begin() as c:
        exists = c.execute(select(datasets.c.dataset_version).where(datasets.c.dataset_version == dataset_version)).first()
        if not exists:
            c.execute(datasets.insert().values(dataset_version=dataset_version, scenario_id=scenario_id,
                                               body=json.dumps(body, ensure_ascii=False)))


def load_dataset(dataset_version: str) -> dict[str, Any] | None:
    with engine().connect() as c:
        row = c.execute(select(datasets.c.body).where(datasets.c.dataset_version == dataset_version)).first()
    return json.loads(row[0]) if row else None
