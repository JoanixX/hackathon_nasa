"""FastAPI application: same-origin frontend, versioned planning resources and job status."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError

from . import APP_NAME, SCHEMA_VERSION, db, jobs
from .config import REPO_ROOT, get_settings
from .contracts import PlanRequest
from .gis_import import ImportErrorReport, normalize_feature_collection
from .plans import PlanInputError, build_plan
from .scenarios import SPECIES, get_scenario, scenario_ids

MAX_BODY = 6 * 1024 * 1024
app = FastAPI(title=APP_NAME, version=SCHEMA_VERSION, docs_url="/api/docs", openapi_url="/api/openapi.json")


@app.middleware("http")
async def limits_and_headers(request: Request, call_next):
    cl = request.headers.get("content-length")
    if cl and (not cl.isdigit() or int(cl) > MAX_BODY):
        return JSONResponse({"error": "payload_too_large", "message": "Request body exceeds 6 MB."}, status_code=413)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "camera=(self), geolocation=(), microphone=()"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


def _error(status: int, code: str, message: str, **extra: Any) -> HTTPException:
    return HTTPException(status_code=status, detail={"error": code, "message": message, **extra})


@app.exception_handler(HTTPException)
async def http_error(_request: Request, exc: HTTPException):
    body = exc.detail if isinstance(exc.detail, dict) else {"error": "http_error", "message": str(exc.detail)}
    headers = getattr(exc, "headers", None)
    return JSONResponse(body, status_code=exc.status_code, headers=headers)


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(REPO_ROOT / "index.html", media_type="text/html")


app.mount("/assets", StaticFiles(directory=REPO_ROOT / "assets", check_dir=False), name="assets")


@app.get("/api/health")
def health():
    s = get_settings()
    queue = "inline" if s.queue_mode == "inline" else "unknown"
    if s.queue_mode == "rq":
        try:
            from redis import Redis

            Redis.from_url(s.valkey_url, socket_timeout=2, socket_connect_timeout=2).ping()
            queue = "available"
        except Exception:
            queue = "unavailable"
    if s.ai_provider == "fixture":
        ai = {"mode": "fixture", "configured": True, "model": "fixture-scripted-v1",
              "note": "Fixture provider: scenes are NOT actual AI inference."}
    else:
        ai = {"mode": "gemini", "configured": bool(s.gemini_api_key), "model": s.gemini_model,
              "note": "Actual inference on the server." if s.gemini_api_key else "GEMINI_API_KEY not configured: AI generation blocked."}
    return {"app": APP_NAME, "schema_version": SCHEMA_VERSION, "queue": queue, "ai": ai,
            "earthdata_configured": bool(s.earthdata_username and s.earthdata_password)}


@app.get("/api/scenarios")
def list_scenarios():
    return [get_scenario(sid)["summary"] for sid in scenario_ids()]


@app.get("/api/scenarios/{scenario_id}")
def scenario(scenario_id: str):
    try:
        return get_scenario(scenario_id)
    except KeyError:
        raise _error(404, "scenario_not_found", "Unknown scenario.")


@app.get("/api/species")
def species():
    return [s.model_dump(mode="json") for s in SPECIES]


class GisImportBody(BaseModel):
    scenario_id: str
    source_label: str = Field(default="uploaded GeoJSON", max_length=200)
    geojson: dict[str, Any]


@app.post("/api/gis/normalize")
def gis_normalize(body: GisImportBody):
    if body.scenario_id not in scenario_ids():
        raise _error(404, "scenario_not_found", "Unknown scenario.")
    label = re.sub(r"[^\w .:/@-]", "", body.source_label)[:200] or "uploaded GeoJSON"
    try:
        out = normalize_feature_collection(body.geojson, body.scenario_id, label)
    except ImportErrorReport as exc:
        raise _error(422, "invalid_geojson", str(exc), details=exc.details)
    except RecursionError:
        raise _error(422, "invalid_geojson", "GeoJSON nesting is too deep.")
    db.save_dataset(out["dataset_version"], body.scenario_id, out)
    return out


@app.post("/api/plans")
def create_plan(body: dict[str, Any]):
    try:
        if isinstance(body.get("imported_dataset_version"), str):
            ds = db.load_dataset(body.pop("imported_dataset_version"))
            if ds is None:
                raise _error(404, "dataset_not_found", "Imported dataset version not found; import it again.")
            body["imported_sectors"] = ds
        req = PlanRequest.model_validate(body)
        plan = build_plan(req)
    except ValidationError as exc:
        raise _error(422, "invalid_plan_request", "Plan request failed validation.",
                     details=[f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()[:20]])
    except PlanInputError as exc:
        raise _error(409 if "Stale" in str(exc) else 422, "plan_input_error", str(exc))
    out = plan.model_dump(mode="json")
    db.save_plan(plan.plan_version, plan.scenario_id, out, plan.created_at)
    return out


@app.get("/api/plans/{plan_version}")
def get_plan(plan_version: str):
    body = db.load_plan(plan_version)
    if body is None:
        raise _error(404, "plan_not_found", "Plan version not found.")
    return body


class SceneBody(BaseModel):
    plan_version: str = Field(min_length=8, max_length=32)


class ReportBody(BaseModel):
    plan_version: str = Field(min_length=8, max_length=32)
    scene_job_id: str | None = Field(default=None, max_length=40)


class SarProcessBody(BaseModel):
    scenario_id: str
    source: str = Field(default="synthetic", max_length=200)
    acquisition: str = Field(default="baseline", pattern=r"^(baseline|post_rainfall)$")
    granule_url: str | None = Field(default=None, max_length=400)


class SarDiscoverBody(BaseModel):
    scenario_id: str
    start: str = Field(default="2025-10-01", pattern=r"^\d{4}-\d{2}-\d{2}$")
    end: str = Field(default="2026-11-14", pattern=r"^\d{4}-\d{2}-\d{2}$")


def _submit(kind: str, inputs: dict[str, Any], plan_version: str | None):
    try:
        st = jobs.submit(kind, inputs, plan_version)
    except jobs.QueueFull as exc:
        raise HTTPException(status_code=429, detail={"error": "queue_full", "message": str(exc)},
                            headers={"Retry-After": str(exc.retry_after_s)})
    return JSONResponse(_job_view(st), status_code=202)


def _job_view(st) -> dict[str, Any]:
    out = st.model_dump(mode="json")
    if st.state in ("ready", "partial") and st.result_ref:
        try:
            out["result"] = jobs.read_artifact(st.result_ref)
        except (KeyError, FileNotFoundError, json.JSONDecodeError):
            out["result"] = None
            out["error_code"] = out["error_code"] or "artifact_missing"
    return out


@app.post("/api/scenes", status_code=202)
def create_scene(body: SceneBody):
    plan = db.load_plan(body.plan_version)
    if plan is None:
        raise _error(404, "plan_not_found", "Plan version not found.")
    from .tasks import latest_evidence

    ev = latest_evidence(plan["scenario_id"], plan["dataset_version"])
    # The evidence run is part of the job identity, so new evidence yields a new scene version.
    return _submit("scene", {"plan_version": body.plan_version, "evidence_run_id": ev["run_id"] if ev else None},
                   body.plan_version)


@app.post("/api/reports", status_code=202)
def create_report(body: ReportBody):
    if db.load_plan(body.plan_version) is None:
        raise _error(404, "plan_not_found", "Plan version not found.")
    scene_ref = None
    if body.scene_job_id:
        st = jobs.get(body.scene_job_id)
        if st is None or st.state != "ready" or not st.result_ref:
            raise _error(409, "scene_not_ready", "The referenced scene job is not ready.")
        if st.plan_version != body.plan_version:
            raise _error(409, "stale_scene", "The scene belongs to a different plan version.")
        scene_ref = st.result_ref
    return _submit("report", {"plan_version": body.plan_version, "scene_ref": scene_ref}, body.plan_version)


@app.post("/api/sar/process", status_code=202)
def sar_process(body: SarProcessBody):
    if body.scenario_id not in scenario_ids():
        raise _error(404, "scenario_not_found", "Unknown scenario.")
    return _submit("sar_process", body.model_dump(), None)


@app.post("/api/sar/discover", status_code=202)
def sar_discover(body: SarDiscoverBody):
    if body.scenario_id not in scenario_ids():
        raise _error(404, "scenario_not_found", "Unknown scenario.")
    return _submit("sar_discover", body.model_dump(), None)


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    jobs.reap_expired()
    st = jobs.get(job_id)
    if st is None:
        raise _error(404, "job_not_found", "Job not found.")
    return _job_view(st)


@app.post("/api/jobs/{job_id}/cancel")
def job_cancel(job_id: str):
    st = jobs.cancel(job_id)
    if st is None:
        raise _error(404, "job_not_found", "Job not found.")
    return _job_view(st)


@app.get("/api/evidence/{scenario_id}")
def evidence(scenario_id: str):
    if scenario_id not in scenario_ids():
        raise _error(404, "scenario_not_found", "Unknown scenario.")
    base = get_settings().artifact_dir / "sar_manifests"
    out = []
    if base.exists():
        for p in sorted(base.glob("*.json")):
            try:
                m = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if m.get("scenario_id") == scenario_id:
                out.append(m)
    out.sort(key=lambda m: m["product"].get("start_time_utc") or "")
    return out


_SAFE_FILE = re.compile(r"^[A-Za-z0-9_]+\.(png|tif)$")


@app.get("/api/evidence-files/{run_id}/{name}")
def evidence_file(run_id: str, name: str):
    if not re.fullmatch(r"[0-9a-f]{16}", run_id) or not _SAFE_FILE.fullmatch(name):
        raise _error(404, "file_not_found", "File not found.")
    p = get_settings().artifact_dir / "sar" / run_id / name
    if not p.exists():
        raise _error(404, "file_not_found", "File not found.")
    return FileResponse(p, media_type="image/png" if name.endswith(".png") else "image/tiff")


@app.post("/api/ai/selftest")
def ai_selftest():
    """One tiny structured request proving actual server-side inference (records trace, no secrets)."""
    from .ai_provider import AIError, make_provider

    class Probe(BaseModel):
        status: str = Field(max_length=20)
        sum: int

    s = get_settings()
    try:
        provider = make_provider(s, lambda p, sc: json.dumps({"status": "fixture", "sum": 5}))
        from .ai_provider import inline_schema

        gen = provider.generate_json("Return JSON only.", "Return status 'ok' and the sum of 2 and 3.",
                                     inline_schema(Probe.model_json_schema()), seed=1)
        probe = Probe.model_validate_json(gen.text)
    except AIError as exc:
        raise _error(503, exc.code, str(exc))
    except ValidationError:
        raise _error(502, "ai_invalid_output", "Provider output failed schema validation.")
    return {"mode": gen.mode, "provider": gen.provider, "model": gen.model, "response_id": gen.response_id,
            "latency_ms": gen.latency_ms, "usage": gen.usage, "parsed": probe.model_dump(),
            "schema_valid": True, "correct": probe.sum == 5}
