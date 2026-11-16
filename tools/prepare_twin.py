"""Prepare a bounded, hashed Copernicus terrain package using the application's real tile pipeline.

Run in the project image. Example:
  python -m tools.prepare_twin --bbox -79.68 -5.44 -79.56 -5.32 --min-zoom 10 --max-zoom 11 --output .local/qa/territory/terrain
The complete tile budget is checked before reading or writing data. No credentials or paid service.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from raiz_sar.terrain import SOURCE, _in_regions, read_dem, terrain_tile_png, tile_bounds
from raiz_sar.territory import tile_plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bbox", nargs=4, type=float, required=True, metavar=("WEST", "SOUTH", "EAST", "NORTH"))
    parser.add_argument("--min-zoom", type=int, default=10)
    parser.add_argument("--max-zoom", type=int, default=11)
    parser.add_argument("--max-tiles", type=int, default=64)
    parser.add_argument("--output", type=Path, default=Path(".local/twin-terrain"))
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()
    try:
        tiles = tile_plan(args.bbox, args.min_zoom, args.max_zoom, args.max_tiles)
        if not all(_in_regions(tile_bounds(*t)) for t in tiles):
            raise ValueError("The tile plan includes territory outside the configured study regions.")
    except ValueError as exc:
        parser.error(str(exc))
    if args.plan_only:
        print(json.dumps({"tiles": tiles, "count": len(tiles), "processed": False}))
        return
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = {"schema": "raiz-terrain-package-1", "prepared_utc": datetime.now(timezone.utc).isoformat(),
                "bbox": args.bbox, "source": SOURCE, "source_release": "AWS public Copernicus DEM 2021 release",
                "source_url": "https://registry.opendata.aws/copernicus-dem/",
                "license_url": "https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM",
                "horizontal_crs": "EPSG:3857", "source_horizontal_crs": "EPSG:4326", "source_vertical_crs": "EPSG:3855",
                "encoding": "terrarium", "tile_size": 256, "vertical_exaggeration": 1, "source_grid_arcseconds": 1,
                "limitations": ["DSM, not bare-earth DTM", "Raster format represents missing source heights as zero for display; not evidence of sea level.",
                                "Resampled tiles do not add source detail.", "No geoid-to-ellipsoid conversion; this viewer uses EGM2008 heights consistently."], "tiles": []}
    for z, x, y in tiles:
        data = terrain_tile_png(z, x, y)
        relative = Path(str(z)) / str(x) / f"{y}.png"
        path = args.output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        manifest["tiles"].append({"z": z, "x": x, "y": y, "path": relative.as_posix(), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
    w, s, e, n = args.bbox
    # A bounded coarse coverage audit is separate from the display tiles' sea-level nodata fill.
    dem, _tf, covered = read_dem(w, s, e, n, max(1 / 3600, (e-w)/128, (n-s)/128))
    valid = dem[np.isfinite(dem)]
    manifest["source_audit"] = {"covered": covered, "valid_fraction": float(np.isfinite(dem).mean()),
                                "min_m": float(valid.min()) if valid.size else None, "max_m": float(valid.max()) if valid.size else None,
                                "audit_grid": list(dem.shape)}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"tiles": len(tiles), "bytes": sum(t["bytes"] for t in manifest["tiles"]), "source_audit": manifest["source_audit"], "manifest": str(args.output / "manifest.json")}))


if __name__ == "__main__":
    main()
