"""API contract, versioning, stale-response rejection and failure-path tests."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st

from conftest import budget
from raiz_sar.api import app

client = TestClient(app)


def scenario(sid="carabayllo-rio-seco"):
    return client.get(f"/api/scenarios/{sid}").json()


def make_plan(sid="carabayllo-rio-seco", **extra):
    s = scenario(sid)
    body = {"scenario_id": sid, "dataset_version": s["summary"]["dataset_version"], **extra}
    r = client.post("/api/plans", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_health_reports_modes_without_secrets():
    h = client.get("/api/health").json()
    assert h["ai"]["mode"] in ("fixture", "gemini")
    assert "key" not in json.dumps(h).lower().replace("key not configured", "")


def test_both_scenarios_present_with_locators():
    ids = {s["scenario_id"]: s for s in client.get("/api/scenarios").json()}
    assert set(ids) == {"carabayllo-rio-seco", "lower-piura-sechura"}
    assert ids["carabayllo-rio-seco"]["locator_lat"] == -11.83 and ids["lower-piura-sechura"]["locator_lon"] == -80.65
    assert all(s["data_mode"] == "synthetic_fixture" for s in ids.values())


def test_plan_version_is_deterministic_and_input_sensitive():
    a = make_plan(budget_pen=10000)
    b = make_plan(budget_pen=10000)
    c = make_plan(budget_pen=10001)
    assert a["plan_version"] == b["plan_version"] != c["plan_version"]


def test_stale_dataset_version_rejected():
    r = client.post("/api/plans", json={"scenario_id": "carabayllo-rio-seco", "dataset_version": "old"})
    assert r.status_code == 409 and r.json()["error"] == "plan_input_error"


def test_full_vertical_slice_scene_and_report_share_plan_version():
    plan = make_plan(budget_pen=15000)
    sj = client.post("/api/scenes", json={"plan_version": plan["plan_version"]}).json()
    assert sj["state"] == "ready", sj
    scene = sj["result"]
    assert scene["plan_version"] == plan["plan_version"]
    assert scene["inference"]["mode"] == "fixture"  # labeled; never reported as actual inference
    rj = client.post("/api/reports", json={"plan_version": plan["plan_version"], "scene_job_id": sj["job_id"]}).json()
    assert rj["state"] == "ready", rj
    rep = rj["result"]
    assert rep["plan_version"] == plan["plan_version"] and rep["scene_version"] == scene["scene_version"]
    assert rep["status_label"].startswith("Draft")
    # Idempotent resubmission returns the same job.
    again = client.post("/api/scenes", json={"plan_version": plan["plan_version"]}).json()
    assert again["job_id"] == sj["job_id"]


def test_report_rejects_scene_from_other_plan():
    p1 = make_plan(budget_pen=9000)
    p2 = make_plan(budget_pen=9500)
    sj = client.post("/api/scenes", json={"plan_version": p1["plan_version"]}).json()
    r = client.post("/api/reports", json={"plan_version": p2["plan_version"], "scene_job_id": sj["job_id"]})
    assert r.status_code == 409 and r.json()["error"] == "stale_scene"


def test_scene_requires_funded_sector():
    plan = make_plan(budget_pen=0)
    sj = client.post("/api/scenes", json={"plan_version": plan["plan_version"]}).json()
    assert sj["state"] == "failed" and sj["error_code"] == "ai_invalid_output"


def test_unknown_plan_404_and_payload_limits():
    assert client.post("/api/scenes", json={"plan_version": "deadbeefdeadbeef"}).status_code == 404
    r = client.post("/api/plans", content=b"{" + b" " * (7 * 1024 * 1024) + b"}", headers={"Content-Type": "application/json"})
    assert r.status_code == 413


def test_gis_import_then_plan_with_imported_dataset():
    fc = {"type": "FeatureCollection", "features": [{
        "type": "Feature", "id": "A1", "geometry": {"type": "Polygon", "coordinates": [[[-77.02, -11.84], [-77.015, -11.84], [-77.015, -11.835], [-77.02, -11.835], [-77.02, -11.84]]]},
        "properties": {"nombre": "Ladera importada", "hectareas": 30, "pendiente": 40, "especie": "tara"}}]}
    out = client.post("/api/gis/normalize", json={"scenario_id": "carabayllo-rio-seco", "geojson": fc}).json()
    assert out["sectors"]["features"][0]["properties"]["sector_name"] == "Ladera importada"
    r = client.post("/api/plans", json={"scenario_id": "carabayllo-rio-seco", "dataset_version": out["dataset_version"],
                                        "imported_dataset_version": out["dataset_version"]})
    assert r.status_code == 200, r.text
    assert r.json()["dataset_version"] == out["dataset_version"]


def test_evidence_file_path_rejected():
    assert client.get("/api/evidence-files/../../x/y.png").status_code == 404
    assert client.get("/api/evidence-files/0123456789abcdef/..%2Fmanifest.json").status_code == 404


@settings(max_examples=budget(400))
@given(st.dictionaries(st.sampled_from(["scenario_id", "dataset_version", "mode", "budget_pen", "target_established_plants",
                                        "species_by_sector", "assumptions", "delay_days", "drone", "reference_date", "zzz"]),
                       st.one_of(st.none(), st.integers(-10**9, 10**9), st.floats(allow_nan=False, allow_infinity=False), st.text(max_size=20),
                                 st.lists(st.integers(-5, 400), max_size=14), st.dictionaries(st.text(max_size=8), st.integers(), max_size=3)),
                       max_size=8))
def test_plan_endpoint_never_500s_on_malformed_bodies(body):
    r = client.post("/api/plans", json=body)
    assert r.status_code in (200, 404, 409, 422), (r.status_code, r.text)


def test_ai_unavailable_is_reported_not_simulated(monkeypatch):
    from raiz_sar import config

    s = config.get_settings()
    blocked = s.__class__(**{**s.__dict__, "ai_provider": "gemini", "gemini_api_key": None})
    import raiz_sar.tasks as tasks

    monkeypatch.setattr(tasks, "get_settings", lambda: blocked)
    plan = make_plan(budget_pen=14000)
    sj = client.post("/api/scenes", json={"plan_version": plan["plan_version"]}).json()
    assert sj["state"] == "failed" and sj["error_code"] == "ai_unavailable"
    rj = client.post("/api/reports", json={"plan_version": plan["plan_version"]}).json()
    assert rj["state"] == "partial" and rj["result"]["ai_status"] == "not_generated"
    assert rj["result"]["sections"]["quantities"]  # deterministic sections still produced


@pytest.mark.parametrize("acq", ["baseline", "post_rainfall"])
def test_synthetic_sar_processing_is_labeled(acq):
    st_ = client.post("/api/sar/process", json={"scenario_id": "lower-piura-sechura", "acquisition": acq}).json()
    assert st_["state"] == "ready", st_
    m = st_["result"]
    assert m["data_mode"] == "synthetic_fixture" and m["product"]["synthetic_fixture"]
    assert m["product"]["granule_id"].startswith("SYNTHETIC_FIXTURE")
    assert m["rvi_status"].startswith("not_computed")


@pytest.mark.parametrize("url", [
    "https://evil.example.com/NISAR_L2_PR_GCOV_X.h5",
    "https://nisar.asf.earthdatacloud.nasa.gov/NISAR/x/../../etc/passwd",
    "http://nisar.asf.earthdatacloud.nasa.gov/NISAR/a/NISAR_L2_PR_GCOV_X.h5",
])
def test_granule_download_only_from_official_host(url):
    st_ = client.post("/api/sar/process", json={"scenario_id": "carabayllo-rio-seco", "granule_url": url}).json()
    assert st_["state"] == "failed" and st_["error_code"] == "invalid_input"


def test_granule_download_without_credentials_is_reported():
    url = ("https://nisar.asf.earthdatacloud.nasa.gov/NISAR/NISAR_L2_GCOV_V1/NISAR_L2_PR_GCOV_TEST/"
           "NISAR_L2_PR_GCOV_034_083_D_094_2005_DHDH_M_TEST.h5")
    st_ = client.post("/api/sar/process", json={"scenario_id": "carabayllo-rio-seco", "granule_url": url}).json()
    assert st_["state"] == "failed" and st_["error_code"] == "earthdata_credentials_missing"


def test_sar_real_path_must_stay_in_data_dir():
    st_ = client.post("/api/sar/process", json={"scenario_id": "lower-piura-sechura", "source": "../../etc/passwd.h5"}).json()
    assert st_["state"] == "failed" and st_["error_code"] == "invalid_input"
