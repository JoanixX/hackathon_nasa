"""Catalog discovery (asf_search) and authorized download (earthaccess) for NISAR GCOV.

Discovery is an anonymous catalog query. Download requires Earthdata credentials configured on
the server; without them the step is reported as blocked rather than simulated.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any


def _pol_mode(granule_id: str) -> str | None:
    parts = granule_id.split("_")
    for token in parts:
        if len(token) == 4 and token[0] in "SDQC" and token.isalpha() and token.isupper() and token not in ("GCOV", "NISAR"):
            return token
    return None


def discover_gcov(aoi_wkt: str, start: str, end: str, max_results: int = 25) -> dict[str, Any]:
    import asf_search as asf

    started = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    query = {"dataset": "NISAR", "processingLevel": "GCOV", "intersectsWith": aoi_wkt, "start": start, "end": end,
             "maxResults": max_results}
    results = asf.search(**query)
    items = []
    for r in results:
        p = r.properties
        gid = p.get("sceneName") or p.get("fileID") or ""
        sizes = p.get("bytes") if isinstance(p.get("bytes"), dict) else {}
        h5 = {k: v for k, v in sizes.items() if str(k).endswith(".h5")}
        h5_bytes = sum(int(v.get("bytes", 0)) for v in h5.values() if isinstance(v, dict)) or None
        items.append({
            "granule_id": gid,
            "start_time_utc": p.get("startTime"), "stop_time_utc": p.get("stopTime"),
            "platform": p.get("platform"), "processing_level": p.get("processingLevel"),
            # NISAR names encode the polarization mode, e.g. SHSH (single HH) or DHDH (dual HH/HV).
            "polarization_mode_from_name": _pol_mode(gid),
            "flight_direction": p.get("flightDirection"),
            "path": p.get("pathNumber"), "frame": p.get("frameNumber"), "h5_bytes": h5_bytes,
            "url": p.get("url"),
        })
    return {"status": "catalog_discovery", "queried_at_utc": started, "query": {k: v for k, v in query.items()},
            "count": len(items), "results": items,
            "note": "Catalog discovery only: nothing was downloaded, inspected or processed."}


def download_granule(url: str, dest_dir: Path, username: str | None, password: str | None) -> Path:
    if not (username and password):
        raise PermissionError("Earthdata credentials are not configured on the server (EARTHDATA_USERNAME/PASSWORD).")
    import os

    import earthaccess

    os.environ["EARTHDATA_USERNAME"] = username
    os.environ["EARTHDATA_PASSWORD"] = password
    earthaccess.login(strategy="environment")
    dest_dir.mkdir(parents=True, exist_ok=True)
    files = earthaccess.download([url], local_path=str(dest_dir))
    if not files:
        raise RuntimeError("Download returned no files.")
    return Path(files[0])
