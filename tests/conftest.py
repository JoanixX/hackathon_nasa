"""Shared test configuration. Runs in the Linux/Python 3.12 container (see README)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_RUNTIME = Path(tempfile.mkdtemp(prefix="raiz-test-"))
os.environ.setdefault("RAIZ_RUNTIME_DIR", str(_RUNTIME))
os.environ.setdefault("RAIZ_QUEUE_MODE", "inline")
os.environ.setdefault("RAIZ_AI_PROVIDER", "fixture")
os.environ.setdefault("RAIZ_DATA_DIR", str(_RUNTIME / "data"))

from hypothesis import HealthCheck, settings  # noqa: E402
from hypothesis.database import DirectoryBasedExampleDatabase  # noqa: E402

_DB = DirectoryBasedExampleDatabase(str(Path(__file__).resolve().parent.parent / ".local" / "hypothesis-db"))
settings.register_profile(
    "default", database=_DB, deadline=None, print_blob=True,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large, HealthCheck.function_scoped_fixture],
)
# "thorough" multiplies the per-test budgets for longer recorded campaigns.
settings.register_profile("thorough", parent=settings.get_profile("default"), max_examples=20000)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "default"))


def budget(n: int) -> int:
    """Per-test example budget; scaled by RAIZ_PBT_SCALE for recorded campaigns."""
    return max(1, int(n * float(os.environ.get("RAIZ_PBT_SCALE", "1"))))
