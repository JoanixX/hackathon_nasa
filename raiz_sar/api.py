"""FastAPI application: same-origin frontend, versioned planning resources and job status."""

from __future__ import annotations

import json
import re
import uuid
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
from .plans import PlanInputError, build_plan, plan_identity, resolve_dataset
from .scenarios import SPECIES, get_scenario, scenario_ids

MAX_BODY = 6 * 1024 * 1024
app = FastAPI(title=APP_NAME, version=SCHEMA_VERSION, docs_url="/api/docs", openapi_url="/api/openapi.json")


@app.middleware("http")
async def limits_and_headers(request: Request, call_next):
    cl = request.headers.get("content-length")
    if cl and (not cl.isdigit() or int(cl) > MAX_BODY):
        return JSONResponse({"error": "payload_too_large", "message": "Request body exceeds 6 MB."}, status_code=413)
    import time as _time

    from . import perf

    spans = perf.begin()  # sync endpoints run in a thread that copies this context: spans are shared
    t0 = _time.perf_counter()
    request_id = uuid.uuid4().hex
    try:
        response = await call_next(request)
    except Exception as exc:
        perf.log({"evt": "http", "request_id": request_id, "method": request.method,
                  "route": _route_of(request.url.path), "status": 500,
                  "ms": round((_time.perf_counter() - t0) * 1000, 1), "spans": spans,
                  "error_type": type(exc).__name__})
        raise
    response.headers["X-Request-ID"] = request_id
    total = (_time.perf_counter() - t0) * 1000
    response.headers["Server-Timing"] = perf.server_timing(spans, total)
    if request.url.path.startswith("/api/") and request.url.path != "/api/client-perf":
        perf.log({"evt": "http", "request_id": request_id, "method": request.method, "route": _route_of(request.url.path), "path": request.url.path[:120],
                  "status": response.status_code, "ms": round(total, 1), "spans": spans})
    response.headers["X-Content-Type-Options"] = "nosniff"
    # Tile providers (OpenFreeMap, GIBS) may require a Referer; never strip it (ADR 0002).
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(self), geolocation=(), microphone=()"
    path = request.url.path
    if path.startswith("/api/") and not path.startswith(("/api/terrain/", "/api/tiles/")):
        response.headers["Cache-Control"] = "no-store"
    elif path == "/" or path.startswith("/app/"):
        response.headers["Cache-Control"] = "no-cache"  # revalidate so clients never run a stale frontend
    return response


_ROUTE_RE = [(re.compile(p), r) for p, r in [
    (r"^/api/terrain/\d+/\d+/\d+\.png$", "/api/terrain/{z}/{x}/{y}"),
    (r"^/api/buildings/\d+/\d+/\d+\.pbf$", "/api/buildings/{z}/{x}/{y}"),
    (r"^/api/tiles/[^/]+/[^/]+/\d+/\d+/\d+\.png$", "/api/tiles/{layer}/{date}/{z}/{x}/{y}"),
    (r"^/api/jobs/[^/]+(/cancel)?$", "/api/jobs/{id}"),
    (r"^/api/plans/[^/]+$", "/api/plans/{v}"),
    (r"^/api/scenarios/[^/]+$", "/api/scenarios/{id}"),
    (r"^/api/evidence(-files)?/.+$", "/api/evidence/*"),
]]


def _route_of(path: str) -> str:
    for rx, name in _ROUTE_RE:
        if rx.match(path):
            return name
    return path


class ClientPerfEvent(BaseModel):
    name: str = Field(max_length=80)
    ms: float = Field(ge=0, le=604800000, allow_inf_nan=False)
    duration_ms: float | None = Field(default=None, ge=0, le=604800000, allow_inf_nan=False)
    detail: str = Field(default="", max_length=200)


class ClientPerf(BaseModel):
    session_id: str = Field(default="legacy", max_length=64, pattern=r"^[a-zA-Z0-9-]+$")
    events: list[ClientPerfEvent] = Field(max_length=200)


@app.post("/api/client-perf")
def client_perf(body: ClientPerf):
    """Browser timing marks (boot phases, layer readiness) written to the same perf log."""
    from . import perf

    for e in body.events:
        event = {"evt": "client", "session_id": body.session_id, "name": e.name,
                 "ms": round(e.ms, 1), "detail": e.detail}
        if e.duration_ms is not None:
            event["duration_ms"] = round(e.duration_ms, 1)
        perf.log(event)
    return {"ok": True}


def _error(status: int, code: str, message: str, **extra: Any) -> HTTPException:
    return HTTPException(status_code=status, detail={"error": code, "message": message, **extra})


from .upstream import UpstreamBusy, UpstreamError  # noqa: E402


@app.exception_handler(UpstreamBusy)
async def upstream_busy(_request: Request, exc: UpstreamBusy):
    """All host-wide upstream slots stayed taken: tell the client when to retry instead of queueing threads."""
    return JSONResponse({"error": "upstream_busy", "message": str(exc)}, status_code=503,
                        headers={"Retry-After": str(exc.retry_after_s)})


@app.exception_handler(UpstreamError)
async def upstream_error(_request: Request, exc: UpstreamError):
    return JSONResponse({"error": "source_unavailable", "message": str(exc)}, status_code=503)


@app.exception_handler(HTTPException)
async def http_error(_request: Request, exc: HTTPException):
    body = exc.detail if isinstance(exc.detail, dict) else {"error": "http_error", "message": str(exc.detail)}
    headers = getattr(exc, "headers", None)
    return JSONResponse(body, status_code=exc.status_code, headers=headers)


@app.on_event("startup")
def prefetch_dem() -> None:
    """Download the study regions' DEM cells in the background so terrain tiles render from local files."""
    import os
    import threading

    if os.environ.get("RAIZ_DEM_PREFETCH", "0") != "1" or get_settings().queue_mode == "inline":
        return
    from .warmup import run

    threading.Thread(target=run, name="warmup", daemon=True).start()


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
    return [s for s in (get_scenario(sid)["summary"] for sid in scenario_ids()) if s.get("listed", True)]


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
        ds = resolve_dataset(req)
        if req.evidence_mode != "nisar":
            cached = db.load_plan(plan_identity(req, ds))
            if cached is not None:
                return cached
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
    dataset_version: str | None = Field(default=None, max_length=80)


class SarDiscoverBody(BaseModel):
    scenario_id: str
    start: str = Field(default="2025-10-01", pattern=r"^\d{4}-\d{2}-\d{2}$")
    end: str = Field(default="2026-11-14", pattern=r"^\d{4}-\d{2}-\d{2}$")


def _submit(kind: str, inputs: dict[str, Any], plan_version: str | None, refresh_ready: bool = False):
    try:
        st = jobs.submit(kind, inputs, plan_version, refresh_ready=refresh_ready)
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


@app.post("/api/reports/preview")
def preview_report(body: ReportBody):
    """Complete reproducible municipal draft without a queue, network request or AI charge."""
    from .contracts import PlantingPlan, FutureSceneSpecification
    from .report import build_report
    stored = db.load_plan(body.plan_version)
    if stored is None:
        raise _error(404, "plan_not_found", "Plan version not found.")
    plan = PlantingPlan.model_validate(stored)
    scene = None
    if body.scene_job_id:
        st = jobs.get(body.scene_job_id)
        if st is None or st.state != "ready" or not st.result_ref or st.plan_version != plan.plan_version:
            raise _error(409, "stale_scene", "The scene must be ready and belong to this plan.")
        scene = FutureSceneSpecification.model_validate(jobs.read_artifact(st.result_ref))
    return build_report(plan, resolve_dataset(plan.request), scene, None).model_dump(mode="json")


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
def evidence(scenario_id: str, dataset_version: str | None = None):
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
            if m.get("scenario_id") == scenario_id and (dataset_version is None or m.get("dataset_version") == dataset_version):
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


# ------------------------------------------------------------------ NISAR evidence, ravines and zone hydrology
class NisarWaterBody(BaseModel):
    aoi: list[float] = Field(min_length=4, max_length=4)
    event_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    zones: list[dict[str, Any]] = Field(default_factory=list, max_length=12)


@app.post("/api/nisar/water", status_code=202)
def nisar_water(body: NisarWaterBody):
    """Idempotent NISAR water-evidence job for an area (worker 'sar' queue; cached windows make re-runs fast)."""
    from shapely.geometry import shape

    from .nisar_evidence import EvidenceError, snap_aoi

    try:
        aoi = snap_aoi(tuple(body.aoi))
        zones = []
        for z in body.zones:
            g = shape(z["geometry"])
            if not g.is_valid or g.geom_type not in ("Polygon", "MultiPolygon"):
                raise ValueError("invalid zone geometry")
            zones.append({"sector_id": str(z.get("sector_id", ""))[:20], "name": str(z.get("name", ""))[:120], "geometry": z["geometry"]})
    except (EvidenceError, ValueError, KeyError, TypeError) as exc:
        raise _error(422, "invalid_request", str(exc))
    return _submit("nisar_water", {"aoi": list(aoi), "event_date": body.event_date, "zones": zones}, None)


@app.get("/api/nisar/files/{run_id}/{name}")
def nisar_file(run_id: str, name: str):
    if not re.fullmatch(r"[0-9a-f]{16}", run_id) or not re.fullmatch(r"[a-z0-9_\-]{1,40}\.png", name):
        raise _error(404, "file_not_found", "File not found.")
    p = get_settings().artifact_dir / "nisar_water" / run_id / name
    if not p.exists():
        raise _error(404, "file_not_found", "File not found.")
    return FileResponse(p, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})


@app.get("/api/buildings/{z}/{x}/{y}.pbf")
def building_tile(z: int, x: int, y: int):
    """Overture building footprints (MVT) for the study region, cached per release."""
    from fastapi.responses import Response

    from . import overture
    from .terrain import _in_regions, tile_bounds
    from .upstream import UpstreamError

    if not (overture.MIN_ZOOM <= z <= overture.MAX_ZOOM and 0 <= x < 2 ** z and 0 <= y < 2 ** z):
        raise _error(404, "tile_out_of_range", "Building tiles exist at zoom 13-14.")
    if not _in_regions(tile_bounds(z, x, y)):
        return Response(b"", media_type="application/x-protobuf", headers={"Cache-Control": "public, max-age=86400"})
    try:
        data = overture.tile_gzip(z, x, y)
    except (UpstreamError, ValueError, OSError) as exc:
        raise _error(502, "source_unavailable", f"Overture buildings unavailable: {type(exc).__name__}")
    headers = {"Cache-Control": "public, max-age=86400"}
    if data[:2] == b"\x1f\x8b":
        headers["Content-Encoding"] = "gzip"
    return Response(data, media_type="application/x-protobuf", headers=headers)


@app.get("/api/region/{scenario_id}/boundary")
def region_boundary(scenario_id: str):
    """Exact study-region boundary (GeoJSON Feature with provenance) for map masking."""
    from .region import geojson

    if scenario_id not in scenario_ids():
        raise _error(404, "scenario_not_found", "Unknown scenario.")
    name = get_scenario(scenario_id)["summary"].get("region_boundary")
    if not name:
        raise _error(404, "no_boundary", "This scenario has no stored boundary.")
    return JSONResponse(geojson(name), headers={"Cache-Control": "public, max-age=86400"})


@app.get("/api/landscape")
def landscape(west: float, south: float, east: float, north: float):
    """Area overview: mapped quebradas classified by basin type (Melton), steep terrain (FAO classes), elevation range."""
    from . import upstream
    from .landscape import analyse, snap
    from .terrain import TerrainUnavailable, _in_regions

    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise _error(422, "invalid_request", "invalid bounding box")
    aoi = snap((west, south, east, north))
    if not _in_regions(aoi):
        raise _error(422, "outside_region", "The area is outside the study region.")
    try:
        return JSONResponse(upstream.manifest("landscape", list(aoi) + ["v1"], 30 * 86400, lambda: analyse(aoi),
                                              (upstream.UpstreamError, TerrainUnavailable, OSError)))
    except (TerrainUnavailable, OSError) as exc:
        raise _error(503, "terrain_unavailable", str(exc))


@app.get("/api/terrain/ravine")
def terrain_ravine(lon: float, lat: float):
    """Huayco start-point decision: accepted / rejected / insufficient, with the evidence and eligible corridors."""
    from .ravines import analyse_point

    try:
        return JSONResponse(analyse_point(lon, lat))
    except ValueError as exc:
        raise _error(422, "invalid_request", str(exc))


class ZoneHydroBody(BaseModel):
    geometry: dict[str, Any]


@app.post("/api/zones/hydrology")
def zones_hydrology(body: ZoneHydroBody):
    from .ravines import zone_hydrology
    from .terrain import TerrainUnavailable
    from .zones import ZoneError, validate_polygon

    try:
        return zone_hydrology(validate_polygon(body.geometry))
    except ZoneError as exc:
        raise _error(422, "invalid_zone", str(exc))
    except (TerrainUnavailable, OSError, ValueError) as exc:
        raise _error(503, "terrain_unavailable", str(exc))


app.mount("/app", StaticFiles(directory=REPO_ROOT / "app", check_dir=False), name="app")


@app.get("/api/terrain/point")
def terrain_point(lon: float, lat: float):
    from .territory import inspect_point
    from .terrain import TerrainUnavailable

    try:
        return inspect_point(lon, lat)
    except ValueError as exc:
        raise _error(422, "invalid_terrain_point", str(exc))
    except (TerrainUnavailable, OSError) as exc:
        raise _error(503, "terrain_unavailable", f"Source elevation unavailable: {type(exc).__name__}")


@app.get("/api/terrain/{z}/{x}/{y}.png")
def terrain_tile(z: int, x: int, y: int):
    from fastapi.responses import Response

    from .terrain import TerrainUnavailable, terrain_tile_png

    try:
        data = terrain_tile_png(z, x, y)
    except ValueError as exc:
        raise _error(404, "tile_out_of_range", str(exc))
    except (TerrainUnavailable, OSError) as exc:
        raise _error(503, "terrain_unavailable", f"Copernicus DEM unavailable: {type(exc).__name__}")
    return Response(data, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})


class ZoneIn(BaseModel):
    name: str = Field(default="", max_length=120)
    geometry: dict[str, Any]
    original_geometry: dict[str, Any] | None = None
    role: str = Field(default="candidate", pattern=r"^(candidate|no_go)$")
    species_candidate: str | None = Field(default=None, max_length=64)
    refinement: dict[str, Any] | None = None


class ZonesBody(BaseModel):
    scenario_id: str
    zones: list[ZoneIn] = Field(max_length=20)


@app.post("/api/zones")
def create_zones(body: ZonesBody):
    from .zones import ZoneError, build_zone_dataset

    try:
        out = build_zone_dataset(body.scenario_id, [z.model_dump() for z in body.zones])
    except ZoneError as exc:
        raise _error(422, "invalid_zone", str(exc))
    db.save_dataset(out["dataset_version"], body.scenario_id, out)
    return out


class SuggestBody(BaseModel):
    geometry: dict[str, Any]
    optical_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


@app.post("/api/zones/suggest")
def suggest_zone(body: SuggestBody):
    from .terrain import TerrainUnavailable
    from .zones import ZoneError, suggest_boundary

    try:
        return suggest_boundary(body.geometry, body.optical_date)
    except ZoneError as exc:
        raise _error(422, "invalid_zone", str(exc))
    except (TerrainUnavailable, OSError) as exc:
        raise _error(503, "terrain_unavailable", f"Suggestion needs the Copernicus DEM: {exc}")


@app.get("/api/sources/layers")
def source_layers():
    from .sources import LAYERS

    return LAYERS


@app.get("/api/sources/dates")
def source_dates(layer: str, lon: float, lat: float, start: str, end: str):
    from .sources import SourceUnavailable, available_dates

    try:
        return available_dates(layer, lon, lat, start, end)
    except ValueError as exc:
        raise _error(422, "invalid_request", str(exc))
    except SourceUnavailable as exc:
        raise _error(503, "source_unavailable", str(exc))


@app.get("/api/sources/coverage")
def source_coverage(layer: str, lon: float, lat: float, dates: str):
    from .sources import SourceUnavailable, coverage

    try:
        return coverage(layer, lon, lat, [d for d in dates.split(",") if d][:60])
    except ValueError as exc:
        raise _error(422, "invalid_request", str(exc))
    except SourceUnavailable as exc:
        raise _error(503, "source_unavailable", str(exc))


@app.get("/api/terrain/flowpath")
def terrain_flowpath(lon: float, lat: float, max_km: float = 6.0):
    """Downhill path for a huayco view. The start must be an accepted ravine point (NV-03): checked here, not only
    in the browser, so a direct request cannot start an event outside a supported corridor."""
    from .ravines import analyse_point
    from .terrain import TerrainUnavailable, flow_path

    try:
        decision = analyse_point(lon, lat)
    except ValueError as exc:
        raise _error(422, "invalid_request", str(exc))
    if decision["decision"] != "accepted":
        decision.pop("eligible_corridors", None)
        raise HTTPException(status_code=409, detail={"error": f"ravine_{decision['decision']}", "message": decision["message"],
                                                     "reason": decision["reason"], "decision": decision})
    try:
        corridor = decision.get("corridor") or {}
        if corridor.get("kind") == "flood":
            from .ravines import river_path

            path = river_path(lon, lat, max(0.5, min(max_km, 12.0)))
        else:
            path = flow_path(lon, lat, max(0.5, min(max_km, 12.0)))
            path["properties"]["kind"] = "debris_flow"
        path.setdefault("properties", {})["ravine"] = {k: decision[k] for k in ("decision", "corridor", "catchment", "tolerance_m")}
        return path
    except ValueError as exc:
        raise _error(422, "invalid_request", str(exc))
    except (TerrainUnavailable, OSError) as exc:
        raise _error(503, "terrain_unavailable", str(exc))


@app.get("/api/terrain/highpoint")
def terrain_highpoint(lon: float, lat: float, radius_km: float = 2.0):
    """Highest DEM cell within a radius: a default start for the downhill (huayco) path."""
    import numpy as np
    from shapely.geometry import Point

    from .geo import metric_to_lonlat
    from .terrain import TerrainUnavailable, metric_dem

    try:
        dem, tf, crs, _gm = metric_dem(Point(lon, lat).buffer(max(0.2, min(radius_km, 6.0)) / 111.0), margin_m=0)
    except (ValueError, TerrainUnavailable, OSError) as exc:
        raise _error(503, "terrain_unavailable", str(exc))
    if not np.isfinite(dem).any():
        raise _error(503, "terrain_unavailable", "No DEM values around the point.")
    r, c = np.unravel_index(np.nanargmax(dem), dem.shape)
    x, y = tf * (c + 0.5, r + 0.5)
    hlon, hlat = metric_to_lonlat(x, y, crs)
    return {"lon": round(hlon, 6), "lat": round(hlat, 6), "elevation_m": round(float(dem[r, c]), 1),
            "source": "Copernicus DEM GLO-30 (surface model)"}


@app.get("/api/sources/ponding")
def source_ponding(west: float, south: float, east: float, north: float, date: str):
    """200 with the result when it is already built; otherwise 202 with an idempotent evidence job.

    The DSWx mosaic and polygon extraction run in a worker, so a cold area never ties up API threads.
    """
    import datetime as _dt

    from .sources import ponding_cached

    w, s, e, n = west, south, east, north
    try:
        _dt.date.fromisoformat(date)
    except ValueError:
        raise _error(422, "invalid_request", "date must be YYYY-MM-DD")
    if not (-180 <= w < e <= 180 and -90 <= s < n <= 90) or (e - w) * (n - s) > 0.5:
        raise _error(422, "invalid_request", "bbox must be valid and at most 0.5 square degrees")
    hit = ponding_cached((w, s, e, n), date)
    if hit is not None:
        # Up to ~1 MB of polygons: serialize directly (FastAPI's recursive encoder took ~0.3 s idle).
        return JSONResponse(hit)
    # Not cached (or expired): a ready job for these inputs is re-run rather than returning its old copy.
    return _submit("ponding", {"bounds": [round(v, 4) for v in (w, s, e, n)], "date": date}, None, refresh_ready=True)


@app.get("/api/tiles/{layer}/{date}/{z}/{x}/{y}.png")
def gibs_tile(layer: str, date: str, z: int, x: int, y: int):
    from fastapi.responses import Response

    from .sources import SourceUnavailable, gibs_tile_transparent

    from .terrain import _in_regions, tile_bounds

    if 0 <= x < 2 ** z and 0 <= y < 2 ** z and not _in_regions(tile_bounds(z, x, y)):
        return Response(status_code=204, headers={"Cache-Control": "public, max-age=86400"})  # outside the study region
    try:
        data = gibs_tile_transparent(layer, date, z, x, y)
    except ValueError as exc:
        raise _error(404, "tile_out_of_range", str(exc))
    except SourceUnavailable as exc:
        raise _error(502, "source_unavailable", str(exc))
    return Response(data, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})


@app.get("/api/sources/rainfall")
def source_rainfall(lat: float, lon: float, start: str, end: str):
    from .sources import SourceUnavailable, rainfall

    try:
        return rainfall(lat, lon, start, end)
    except ValueError as exc:
        raise _error(422, "invalid_request", str(exc))
    except SourceUnavailable as exc:
        raise _error(503, "source_unavailable", str(exc))


@app.get("/api/sources/acquisitions")
def source_acquisitions(west: float, south: float, east: float, north: float, start: str, end: str):
    from .sources import SourceUnavailable, acquisitions

    try:
        return acquisitions((west, south, east, north), start, end)
    except ValueError as exc:
        raise _error(422, "invalid_request", str(exc))
    except SourceUnavailable as exc:
        raise _error(503, "source_unavailable", str(exc))


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
