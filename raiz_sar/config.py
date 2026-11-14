"""Runtime configuration read from environment variables (server side only)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw and raw.strip() else default


def _float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    return float(raw) if raw and raw.strip() else default


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str | None
    gemini_model: str
    ai_provider: str  # "gemini" (actual inference) or "fixture" (labeled offline development only)
    ai_timeout_s: float
    valkey_url: str
    queue_mode: str  # "rq" (default) or "inline" (tests only)
    runtime_dir: Path
    data_dir: Path
    max_queue_depth: int
    job_lease_s: int
    max_job_attempts: int
    earthdata_username: str | None
    earthdata_password: str | None

    @property
    def database_path(self) -> Path:
        return self.runtime_dir / "raiz.sqlite3"

    @property
    def artifact_dir(self) -> Path:
        return self.runtime_dir / "artifacts"

    @property
    def ai_configured(self) -> bool:
        if self.ai_provider == "fixture":
            return True
        return bool(self.gemini_api_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    runtime = Path(os.environ.get("RAIZ_RUNTIME_DIR", REPO_ROOT / ".local" / "runtime"))
    data = Path(os.environ.get("RAIZ_DATA_DIR", REPO_ROOT / "data"))
    provider = os.environ.get("RAIZ_AI_PROVIDER", "gemini").strip().lower()
    if provider not in {"gemini", "fixture"}:
        raise ValueError("RAIZ_AI_PROVIDER must be 'gemini' or 'fixture'")
    queue_mode = os.environ.get("RAIZ_QUEUE_MODE", "rq").strip().lower()
    if queue_mode not in {"rq", "inline"}:
        raise ValueError("RAIZ_QUEUE_MODE must be 'rq' or 'inline'")
    return Settings(
        gemini_api_key=(os.environ.get("GEMINI_API_KEY") or "").strip() or None,
        gemini_model=os.environ.get("GEMINI_MODEL", "gemini-3.8-flash").strip(),
        ai_provider=provider,
        ai_timeout_s=_float("RAIZ_AI_TIMEOUT_S", 60.0),
        valkey_url=os.environ.get("RAIZ_VALKEY_URL", "redis://localhost:6379/0"),
        queue_mode=queue_mode,
        runtime_dir=runtime,
        data_dir=data,
        max_queue_depth=_int("RAIZ_MAX_QUEUE_DEPTH", 20),
        job_lease_s=_int("RAIZ_JOB_LEASE_S", 300),
        max_job_attempts=_int("RAIZ_MAX_JOB_ATTEMPTS", 3),
        earthdata_username=(os.environ.get("EARTHDATA_USERNAME") or "").strip() or None,
        earthdata_password=(os.environ.get("EARTHDATA_PASSWORD") or "").strip() or None,
    )
