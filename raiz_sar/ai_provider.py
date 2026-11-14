"""Server-side structured generation adapter.

``GeminiProvider`` performs actual inference through the Google Gen AI SDK with a JSON schema
constraint. ``FixtureProvider`` is an explicitly labeled offline development stand-in; its output
is never reported as actual inference. Provider credentials never leave the backend.
"""

from __future__ import annotations

import copy
import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from .config import Settings


class AIError(Exception):
    code = "ai_error"

    def __init__(self, message: str, retry_after_s: float | None = None):
        super().__init__(message)
        self.retry_after_s = retry_after_s


class AIUnavailable(AIError):
    code = "ai_unavailable"


class AITimeout(AIError):
    code = "ai_timeout"


class AIRateLimited(AIError):
    code = "ai_rate_limited"


class AIProviderError(AIError):
    code = "ai_provider_error"


class AIInvalidOutput(AIError):
    code = "ai_invalid_output"


@dataclass
class GenerationResult:
    text: str
    mode: str  # "actual_inference" | "fixture"
    provider: str
    model: str
    response_id: str | None
    latency_ms: int
    usage: dict[str, int] = field(default_factory=dict)


def prompt_hash(system: str, prompt: str, schema: dict[str, Any]) -> str:
    h = hashlib.sha256()
    for part in (system, prompt, repr(sorted(schema.items()))):
        h.update(part.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()[:16]


def inline_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Resolve local ``$ref``/``$defs`` and drop annotation keys for provider schema support."""
    defs = schema.get("$defs", {})

    def walk(node: Any, depth: int = 0) -> Any:
        if depth > 40:
            raise ValueError("schema too deep")
        if isinstance(node, dict):
            if "$ref" in node:
                name = node["$ref"].split("/")[-1]
                return walk(copy.deepcopy(defs[name]), depth + 1)
            out = {}
            for k, v in node.items():
                # minItems/maxItems are rejected by gemini-3.8-flash (HTTP 400, verified 2026-11-14 by
                # bisection). Array lengths are still enforced by Pydantic after generation.
                if k in ("$defs", "title", "default", "minItems", "maxItems"):
                    continue
                if k == "properties" and isinstance(v, dict):
                    # Keys here are property NAMES (a field may be called "title"); keep them all.
                    out[k] = {name: walk(sub, depth + 1) for name, sub in v.items()}
                else:
                    out[k] = walk(v, depth + 1)
            return out
        if isinstance(node, list):
            return [walk(x, depth + 1) for x in node]
        return node

    return walk(schema)


class GeminiProvider:
    name = "google-gemini"

    def __init__(self, settings: Settings):
        if not settings.gemini_api_key:
            raise AIUnavailable("GEMINI_API_KEY is not configured on the server.")
        from google import genai
        from google.genai import types

        self._types = types
        self.model = settings.gemini_model
        self.timeout_s = settings.ai_timeout_s
        self._client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(timeout=int(settings.ai_timeout_s * 1000)),
        )

    def generate_json(self, system: str, prompt: str, schema: dict[str, Any], seed: int | None = None) -> GenerationResult:
        from google.genai import errors
        import httpx

        types = self._types
        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_json_schema=schema,
            temperature=0.4,
            seed=seed,
            max_output_tokens=8192,
        )
        t0 = time.monotonic()
        try:
            resp = self._client.models.generate_content(model=self.model, contents=prompt, config=config)
        except errors.ClientError as exc:
            status = getattr(exc, "code", None)
            if status == 429:
                raise AIRateLimited("The AI provider rate-limited the request.", retry_after_s=30) from exc
            if status in (401, 403):
                raise AIUnavailable("The AI provider rejected the server credentials or model access.") from exc
            if status == 404:
                raise AIUnavailable(f"Model '{self.model}' is not available to this account.") from exc
            raise AIProviderError(f"AI provider client error ({status}).") from exc
        except errors.ServerError as exc:
            raise AIProviderError(f"AI provider server error ({getattr(exc, 'code', None)}).", retry_after_s=10) from exc
        except (httpx.TimeoutException, TimeoutError) as exc:
            raise AITimeout(f"No AI response within {self.timeout_s:g} s.") from exc
        except httpx.HTTPError as exc:
            raise AIProviderError("Network error while contacting the AI provider.") from exc
        latency = int((time.monotonic() - t0) * 1000)
        text = getattr(resp, "text", None)
        if not text:
            raise AIInvalidOutput("The AI provider returned no text (possibly blocked or truncated).")
        usage = {}
        um = getattr(resp, "usage_metadata", None)
        if um is not None:
            for k in ("prompt_token_count", "candidates_token_count", "total_token_count"):
                v = getattr(um, k, None)
                if isinstance(v, int):
                    usage[k] = v
        return GenerationResult(
            text=text, mode="actual_inference", provider=self.name,
            model=getattr(resp, "model_version", None) or self.model,
            response_id=getattr(resp, "response_id", None), latency_ms=latency, usage=usage,
        )


class FixtureProvider:
    """Offline development stand-in. Output is labeled ``fixture`` end to end."""

    name = "fixture"
    model = "fixture-scripted-v1"

    def __init__(self, responder: Callable[[str, dict[str, Any]], str]):
        self._responder = responder

    def generate_json(self, system: str, prompt: str, schema: dict[str, Any], seed: int | None = None) -> GenerationResult:
        return GenerationResult(text=self._responder(prompt, schema), mode="fixture", provider=self.name,
                                model=self.model, response_id=None, latency_ms=0)


def make_provider(settings: Settings, fixture_responder: Callable[[str, dict[str, Any]], str]):
    if settings.ai_provider == "fixture":
        return FixtureProvider(fixture_responder)
    return GeminiProvider(settings)
