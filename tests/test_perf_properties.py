"""Telemetry boundary properties: finite, bounded, correlated timings without provider traffic."""
import math

import pytest
from fastapi.testclient import TestClient
from hypothesis import given, settings, strategies as st
from pydantic import ValidationError

from raiz_sar.api import ClientPerf, app
from raiz_sar.perf import server_timing


@settings(max_examples=2000)
@given(st.floats(allow_nan=True, allow_infinity=True), st.text(max_size=90))
def test_client_timing_rejects_nonfinite_negative_and_oversized_values(ms, name):
    body = {"events": [{"name": name, "ms": ms}]}
    valid = math.isfinite(ms) and 0 <= ms <= 604800000 and len(name) <= 80
    if valid:
        out = ClientPerf.model_validate(body)
        assert out.events[0].ms == ms
    else:
        with pytest.raises(ValidationError):
            ClientPerf.model_validate(body)


@settings(max_examples=1500)
@given(st.lists(st.tuples(st.sampled_from(["gibs.fetch", "dem.read", "cache hit"]), st.floats(min_value=0, max_value=100000, allow_nan=False)), max_size=40))
def test_server_timing_preserves_aggregate_duration(spans):
    events = [{"name": n, "ms": ms} for n, ms in spans]
    header = server_timing(events, 125)
    assert header.startswith("app;dur=125.0")
    parts = dict(part.strip().split(";dur=") for part in header.split(","))
    for name in {n for n, _ in spans}:
        expected = sum(ms for n, ms in spans if n == name)
        assert float(parts[name.replace(".", "_").replace(" ", "_")]) == pytest.approx(expected, abs=0.051)


def test_request_and_browser_timing_correlation(monkeypatch):
    from raiz_sar import perf
    events = []
    monkeypatch.setattr(perf, "log", events.append)
    with TestClient(app) as client:
        response = client.get("/api/scenarios")
        assert response.status_code == 200
        assert len(response.headers["x-request-id"]) == 32
        assert response.headers["x-request-id"] == events[-1]["request_id"]
        assert "app;dur=" in response.headers["server-timing"]
        result = client.post("/api/client-perf", json={"session_id": "test-session", "events": [{"name": "api.request", "ms": 4000, "duration_ms": 5, "detail": "test"}]})
        assert result.status_code == 200
        assert events[-1]["duration_ms"] == 5
        assert events[-1]["session_id"] == "test-session"
        assert client.post("/api/client-perf", json={"events": [{"name": "bad", "ms": -1}]}).status_code == 422
        assert client.post("/api/client-perf", json={"events": [{"name": "bad", "ms": 1}]*201}).status_code == 422
