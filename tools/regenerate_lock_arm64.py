"""Regenerate requirements-linux-arm64-py312.lock: same versions as the x86-64 lock, arm64 wheel hashes.

The free Oracle Cloud VM (Ampere A1) is aarch64. Run inside the target image on arm64:
  docker run --rm --platform linux/arm64 -v "$PWD:/src" -w /src python:3.12-slim-bookworm python tools/regenerate_lock_arm64.py
"""

from __future__ import annotations

import datetime as dt
import json
import platform
import subprocess
import sys

if platform.machine() not in ("aarch64", "arm64"):
    raise SystemExit("run this on linux/arm64")
pins = [ln.split(" ")[0] for ln in open("requirements-linux-py312.lock") if ln.strip() and not ln.startswith("#")]
open("/tmp/x86-pins.txt", "w").write("\n".join(pins) + "\n")
REPORT = "/tmp/report-arm64.json"
subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-q", "--no-cache-dir",
                "--root-user-action=ignore", "--dry-run", "--ignore-installed", "--only-binary=:all:",
                "--report", REPORT, "-r", "requirements-dev.txt", "-c", "/tmp/x86-pins.txt"], check=True)
report = json.load(open(REPORT))
rows = sorted((i["metadata"]["name"].lower().replace("_", "-"), i["metadata"]["version"],
               i["download_info"]["archive_info"]["hashes"]["sha256"]) for i in report["install"])
x86 = {p.split("==")[0]: p.split("==")[1] for p in pins}
diff = [f"{n} {v} (x86 {x86.get(n)})" for n, v, _ in rows if x86.get(n) != v]
if diff or {n for n, _, _ in rows} != set(x86):
    raise SystemExit("Architecture lock must preserve every pinned package/version; refusing to overwrite it.")
env = report["environment"]
header = [
    f"# Target-environment lock: Linux aarch64 / CPython {env['python_full_version']}, regenerated {dt.date.today()} inside",
    "# python:3.12-slim-bookworm (linux/arm64) with the x86-64 lock's versions as constraints; binary wheels only.",
    "# Used by the Dockerfile when building for arm64 (free Oracle Cloud Ampere VM). Regenerate: tools/regenerate_lock_arm64.py",
    "# Install: pip install --require-hashes -r requirements-linux-arm64-py312.lock",
]
with open("requirements-linux-arm64-py312.lock", "w", newline="\n") as fh:
    fh.write("\n".join(header + [f"{n}=={v} --hash=sha256:{h}" for n, v, h in rows]) + "\n")
print(len(rows), "packages; version differences vs x86:", diff or "none")
