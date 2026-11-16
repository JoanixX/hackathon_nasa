# ADR 0003 — Ponding sites, Piura–Tumbes focus, digital-twin views and performance logging

**Status:** Accepted by the owner, November 15, 2026. **Amends:** [ADR 0002](0002-map-first-frontend-and-real-data.md) and [SOURCE_CONTEXT](../SOURCE_CONTEXT.md) §12.

## Context

The owner changed the problem framing and asked for a faster, more legible map and better 3D/AR:

- Satellite and SAR evidence now also identifies **strategic sites where rainwater ponds** after the rains. With species that need the least irrigation and fertilizer, those sites become **candidate planting sites**, not only huayco (debris-flow) protection slopes.
- At most **three plant types** per study area.
- The map is limited to **Piura and Tumbes**, centred on Piura, Sullana, Paita, Talara and Sechura (Tumbes is also a focus button).
- Each drawn zone has a **chosen number of vertices, 4 to 8**, fixed before placing them.
- 3D views must show **before** (observed ponding) and **after** (planted trees), and a huayco descending a quebrada **with** and **without** the planted trees; the interface never calls these "simulations".
- Trees, ponding and the huayco front are drawn as **digital twins**: each planted placement is a 3D tree with its species form; water and mud are drawn where they were observed or derived.
- Legend colours must be the colours actually painted on the 2D and 3D map.
- The system was slow; the owner asked for logs that show where time goes and for fixes that keep every function and visual.

## Decision

1. **Ponding evidence:** OPERA L3 DSWx-HLS (NASA JPL, 30 m) through GIBS. The API classifies its published colormap (open water, partial surface water, cloud, no data) and returns water polygons for a zone box and date (`/api/sources/ponding`). Rainy-season dates with water are offered first (observed over Piura, Sullana and Sechura on February 12 and 27, 2026). Cloud is shown as unknown, never as dry ground. SAR (Sentinel-1 RTC, NISAR GCOV) remains the all-weather context; DSWx is optical and cloud-limited.
2. **Species:** three low-water, dry-forest candidates for Piura — algarrobo (*Prosopis pallida*), sapote (*Colicodendron scabridum*, name to confirm with a botanist) and faique (*Vachellia macracantha*) — each with a 3D form (height, crown radius, crown shape and colour) used by the twin and AR. They remain source candidates, not prescriptions.
3. **Region:** the Piura scenario becomes "Piura and Tumbes" with a region box and six focus areas; the map's bounds and DEM tiles are restricted to it. Carabayllo stays as an unlisted test fixture reachable by id.
4. **Zones:** the user chooses 4–8 vertices, places them by clicks and the ring closes on the last one; the API rejects drawn zones outside that range. Imported GIS zones keep their geometry. Assisted suggestions are simplified to at most 8 vertices (fallback: minimum rotated rectangle) and remain proposals.
5. **Twin views** on the MapLibre terrain (fill-extrusion, no extra 3D library): before (DSWx water), after (species trees by placement), huayco with trees and huayco without trees. The huayco path is the steepest-descent path on the Copernicus DEM from the highest point near the zones (`/api/terrain/highpoint`, `/api/terrain/flowpath`) or from a user-chosen start. It is **not a debris-flow model**: the "with trees" view uses a declared illustrative assumption (the front narrows by half and stops about 240 m inside the first planted zone). Each view can be recorded as a WebM video from the map canvas.
6. **AR** drapes a snapshot of the map (streets, buildings, quebradas, layers) on the DEM mesh, draws species-shaped trees, observed ponding and the huayco front with and without trees.
7. **Performance:** contextvar spans in the API, one JSON line per request and job in `<runtime>/logs/perf.jsonl` plus a `Server-Timing` header, browser phase marks posted to `/api/client-perf`, and `tools/perf_report.py` to summarize them. Fixes: decimated COG reads with per-thread datasets, DEM tiles limited to the region (out-of-region cells skipped — one z7 tile took 78 s reading them remotely), a start-up warm-up of DEM cells, SAR coverage and tiles, a pooled HTTP client for GIBS, a native runtime volume, three API workers and deferred CDN scripts.

## Consequences

- First map idle in a cold headless session went from 208 s to about 24 s (warm cache); GIBS tile fetch p50 from about 1.4 s to 0.3–0.5 s during warm-up. Remaining time is dominated by GIBS latency for uncached tiles and coverage probes.
- Ponding sites are candidates for field checking (soil, salinity, land tenure, flood duration); open-water bodies such as reservoirs or rivers are not planting sites and must be excluded in the field.
- Huayco visuals communicate a planning idea and must never be read as a hazard model or a protection guarantee.

## Follow-up correction — performance audit

[ADR 0004](0004-demand-driven-map-loading.md) supersedes eager radar/relief and default bulk warmup. Its audit contains repeated browser measurements; the older 208 s/24 s comparison above is historical and was not reproduced here. Tree forms are procedural approximations, not exact individual twins; water/mud heights and resistance remain illustrative. The audit removed automatic terrain-path rerouting to force a flow/tree intersection.
