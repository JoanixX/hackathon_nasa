"""Regenerate requirements-linux-py312.lock inside the target image (run in python:3.12-slim-bookworm).

Usage: docker run --rm -v "$PWD:/src" -w /src python:3.12-slim-bookworm python tools/regenerate_lock.py
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys

REPORT = "/tmp/report-target.json"
subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-q", "--no-cache-dir",
                "--root-user-action=ignore", "--dry-run", "--ignore-installed", "--only-binary=:all:",
                "--report", REPORT, "-r", "requirements-dev.txt"], check=True)
report = json.load(open(REPORT))
rows = sorted((i["metadata"]["name"].lower().replace("_", "-"), i["metadata"]["version"],
               i["download_info"]["archive_info"]["hashes"]["sha256"]) for i in report["install"])
env = report["environment"]
header = [
    f"# Target-environment lock: Linux x86-64 / CPython {env['python_full_version']}, regenerated {dt.date.today()} inside",
    f"# python:3.12-slim-bookworm (see Dockerfile) with pip {report['pip_version']} --dry-run --report, binary wheels only.",
    "# Includes runtime and Python QA dependencies; imports and the test suite run in this environment.",
    "# Not a security audit. Regenerate: python tools/regenerate_lock.py (inside the target image).",
    "# Install: pip install --require-hashes -r requirements-linux-py312.lock",
]
with open("requirements-linux-py312.lock", "w", newline="\n") as fh:
    fh.write("\n".join(header + [f"{n}=={v} --hash=sha256:{h}" for n, v, h in rows]) + "\n")
print(len(rows), "packages")
