"""Gemini adapter error mapping and the scene repair loop, with a fake SDK client (no network)."""

from __future__ import annotations

import json

import httpx
import pytest

from raiz_sar import ai_provider
from raiz_sar.ai_provider import AIInvalidOutput, AIRateLimited, AITimeout, AIUnavailable, AIProviderError, GeminiProvider, GenerationResult
from raiz_sar.config import get_settings
from raiz_sar.contracts import PlanRequest
from raiz_sar.plans import build_plan, resolve_dataset
from raiz_sar.scenarios import get_scenario
from raiz_sar.scene import build_prompt, fixture_scene_responder, generate_scene, scene_context


class FakeModels:
    def __init__(self, behaviour):
        self.behaviour = behaviour
        self.calls = 0

    def generate_content(self, model, contents, config):
        self.calls += 1
        b = self.behaviour(self.calls)
        if isinstance(b, Exception):
            raise b
        return b


class Resp:
    def __init__(self, text):
        self.text = text
        self.response_id = "resp-1"
        self.model_version = "gemini-3.8-flash"
        self.usage_metadata = type("U", (), {"prompt_token_count": 10, "candidates_token_count": 5, "total_token_count": 15})()


def provider_with(behaviour):
    s = get_settings()
    s2 = s.__class__(**{**s.__dict__, "gemini_api_key": "test-not-a-real-key", "ai_provider": "gemini"})
    p = GeminiProvider(s2)
    p._client = type("C", (), {"models": FakeModels(behaviour)})()
    return p


def test_missing_key_is_unavailable():
    s = get_settings()
    with pytest.raises(AIUnavailable):
        GeminiProvider(s.__class__(**{**s.__dict__, "gemini_api_key": None, "ai_provider": "gemini"}))


def _client_error(code):
    from google.genai import errors

    return errors.ClientError(code, {"error": {"code": code, "message": "x", "status": "X"}})


@pytest.mark.parametrize("exc,expected", [
    (lambda: _client_error(429), AIRateLimited),
    (lambda: _client_error(403), AIUnavailable),
    (lambda: _client_error(404), AIUnavailable),
    (lambda: _client_error(400), AIProviderError),
    (lambda: httpx.ReadTimeout("slow"), AITimeout),
    (lambda: httpx.ConnectError("down"), AIProviderError),
])
def test_error_mapping(exc, expected):
    p = provider_with(lambda n: exc())
    with pytest.raises(expected):
        p.generate_json("s", "p", {"type": "object"})


def test_empty_text_is_invalid_output():
    p = provider_with(lambda n: Resp(""))
    with pytest.raises(AIInvalidOutput):
        p.generate_json("s", "p", {"type": "object"})


def test_actual_mode_trace_fields():
    p = provider_with(lambda n: Resp('{"a": 1}'))
    g = p.generate_json("s", "p", {"type": "object"})
    assert g.mode == "actual_inference" and g.response_id == "resp-1" and g.usage["total_token_count"] == 15


def _plan():
    sid = "carabayllo-rio-seco"
    req = PlanRequest(scenario_id=sid, dataset_version=get_scenario(sid)["summary"]["dataset_version"], budget_pen=10000)
    return build_plan(req), resolve_dataset(req)


def test_scene_repair_loop_recovers_on_second_attempt():
    plan, ds = _plan()
    good = fixture_scene_responder(build_prompt(scene_context(plan, ds)), {})
    p = provider_with(lambda n: Resp("not json") if n == 1 else Resp(good))
    spec = generate_scene(plan, ds, p)
    assert spec.inference.attempts == 2 and spec.inference.mode == "actual_inference"
    assert spec.labels["future"] == "AI-generated future scenario"


def test_scene_rejects_persistently_invalid_output():
    plan, ds = _plan()
    bad = json.loads(fixture_scene_responder(build_prompt(scene_context(plan, ds)), {}))
    bad["zones"][0]["sector_id"] = "CRB-04"  # excluded channel bed
    p = provider_with(lambda n: Resp(json.dumps(bad)))
    with pytest.raises(AIInvalidOutput):
        generate_scene(plan, ds, p)


def test_inline_schema_has_no_refs():
    from raiz_sar.scene import ai_schema

    text = json.dumps(ai_schema())
    assert "$ref" not in text and "$defs" not in text


def test_fixture_provider_is_labeled():
    f = ai_provider.FixtureProvider(lambda p, s: "{}")
    g = f.generate_json("s", "p", {})
    assert isinstance(g, GenerationResult) and g.mode == "fixture"
