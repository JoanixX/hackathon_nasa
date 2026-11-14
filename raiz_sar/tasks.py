"""Job handlers executed by the SAR and AI/report workers (and inline in tests)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import db
from .ai_provider import AIError, AIUnavailable, make_provider
from .config import get_settings
from .contracts import FutureSceneSpecification, PlantingPlan
from .jobs import JobFailure, handler, read_artifact, run, write_artifact
from .plans import resolve_dataset
from .report import build_report, fixture_report_responder
from .scenarios import get_scenario


def execute(job_id: str) -> str:
    """The only function the queue may call. ``job_id`` is a string key into the jobs table."""
    if not isinstance(job_id, str) or len(job_id) > 40:
        raise ValueError("invalid job id")
    return run(job_id)


def latest_evidence(scenario_id: str, dataset_version: str) -> dict[str, Any] | None:
    """Most recent derived SAR manifest for this exact dataset version (no cross-version mixing)."""
    base = get_settings().artifact_dir / "sar_manifests"
    best = None
    for p in base.glob("*.json") if base.exists() else []:
        try:
            m = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if m.get("scenario_id") == scenario_id and m.get("dataset_version") == dataset_version:
            if best is None or (m["product"].get("start_time_utc") or "") > (best["product"].get("start_time_utc") or ""):
                best = m
    return best


def _plan(plan_version: str) -> PlantingPlan:
    body = db.load_plan(plan_version)
    if body is None:
        raise JobFailure("plan_not_found", "The planting plan version does not exist.")
    return PlantingPlan.model_validate(body)


@handler("scene")
def scene_job(inputs: dict[str, Any]) -> str:
    from .scene import fixture_scene_responder, generate_scene

    plan = _plan(inputs["plan_version"])
    dataset = resolve_dataset(plan.request)
    s = get_settings()
    try:
        provider = make_provider(s, fixture_scene_responder)
        evidence = None
        if inputs.get("evidence_run_id"):
            try:
                evidence = read_artifact(f"sar_manifests/{inputs['evidence_run_id']}.json")
            except (KeyError, FileNotFoundError, ValueError):
                evidence = None  # evidence removed: build the scene without the overlay
        spec = generate_scene(plan, dataset, provider, evidence=evidence)
    except AIError as exc:
        raise JobFailure(exc.code, str(exc)) from exc
    return write_artifact("scenes", spec.scene_version, spec.model_dump(mode="json"))


@handler("report")
def report_job(inputs: dict[str, Any]) -> str:
    plan = _plan(inputs["plan_version"])
    dataset = resolve_dataset(plan.request)
    scene = None
    if inputs.get("scene_ref"):
        try:
            scene = FutureSceneSpecification.model_validate(read_artifact(inputs["scene_ref"]))
        except (KeyError, FileNotFoundError, ValueError) as exc:
            raise JobFailure("scene_not_found", "The referenced scene artifact is unavailable.") from exc
        if scene.plan_version != plan.plan_version:
            raise JobFailure("stale_scene", "The scene was generated for a different plan version.")
    s = get_settings()
    try:
        provider = make_provider(s, fixture_report_responder)
    except AIUnavailable:
        provider = None
    draft = build_report(plan, dataset, scene, provider)
    ref = write_artifact("reports", draft.report_version, draft.model_dump(mode="json"))
    if draft.ai_status == "not_generated":
        raise JobFailure("ai_unavailable", draft.ai_error or "AI narrative not generated.", partial_ref=ref)
    return ref


def _safe_data_path(rel: str) -> Path:
    base = get_settings().data_dir.resolve()
    p = (base / rel).resolve()
    if base not in p.parents or p.suffix.lower() not in (".h5", ".hdf5"):
        raise JobFailure("invalid_input", "GCOV path must be an .h5 file inside the server data directory.")
    if not p.exists():
        raise JobFailure("input_missing", f"GCOV file not found in the data directory: {rel}")
    return p


@handler("sar_process")
def sar_process_job(inputs: dict[str, Any]) -> str:
    from .sar.pipeline import process_gcov
    from .sar.synthetic import write_synthetic_gcov

    scenario = get_scenario(inputs["scenario_id"])
    s = get_settings()
    if inputs["source"] == "synthetic":
        acq = inputs.get("acquisition", "baseline")
        path = s.runtime_dir / "synthetic" / f"{inputs['scenario_id']}_{acq}.h5"
        write_synthetic_gcov(path, scenario, acq)
    else:
        path = _safe_data_path(inputs["source"])
    try:
        manifest = process_gcov(path, scenario, s.artifact_dir / "sar")
    except (ValueError, OSError, KeyError) as exc:
        raise JobFailure("sar_processing_error", str(exc)[:300]) from exc
    return write_artifact("sar_manifests", manifest["run_id"], manifest)


@handler("sar_discover")
def sar_discover_job(inputs: dict[str, Any]) -> str:
    from .sar.discovery import discover_gcov
    from .sar.pipeline import aoi_wkt

    scenario = get_scenario(inputs["scenario_id"])
    try:
        out = discover_gcov(aoi_wkt(scenario), inputs["start"], inputs["end"])
    except Exception as exc:  # network/catalog errors are reported, not simulated
        raise JobFailure("catalog_unavailable", f"{type(exc).__name__}: {str(exc)[:250]}") from exc
    out["scenario_id"] = inputs["scenario_id"]
    name = f"{inputs['scenario_id']}-{json.dumps([inputs['start'], inputs['end']])}"
    import hashlib

    return write_artifact("sar_discovery", hashlib.sha256(name.encode()).hexdigest()[:16], out)
