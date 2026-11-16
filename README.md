# RAÍZ-SAR AI

Piura territorial 3D extension: select **3D territory** for regional/Andean navigation, default ×1 DEM relief, mapped materials, source-elevation inspection and bounded illustrative vegetation/water/weather. See the [implementation, sources and measured limitations](docs/PIURA_DIGITAL_TWIN.md) and [ADR 0005](docs/decisions/0005-piura-territorial-view.md). This is a local territorial increment; complete geographic reconstruction and hardware performance are not certified.

### SAR-informed planting assessment, slope bioengineering and AI-assisted AR scenarios

Current solution for the team's **NASA Space Apps Challenge 2026 / Dancing with the SARs** preparation. Repository: `JoanixX/hackathon_nasa` (private). The project has pivoted from the earlier NiñoRadar flood-exposure concept.

**Status: locally runnable, map-first prototype focused on Piura and Tumbes** ([ADR 0002](docs/decisions/0002-map-first-frontend-and-real-data.md)). The default view is a coloured street/building map. Analytical layers are Off until selected; terrain, drawing tools and charts load on demand. The map offers real data from free sources: NISAR GCOV and Sentinel-1 OPERA RTC radar and HLS imagery (NASA GIBS), Copernicus DEM terrain, NASA POWER rainfall and the ASF catalog, over an OpenFreeMap basemap. Users draw and confirm their own zones. Gemini generates the future scenario on the server, shown on 3D terrain and in camera AR. Numeric backscatter needs an Earthdata download, and physical-device AR is still pending. See [implementation status and acceptance gates](docs/IMPLEMENTATION_STATUS.md).

## Run locally

Requirements: Docker Desktop (Linux containers). Nothing is installed into ArcGIS Pro or the global Python.

```bash
cp .env.example .env
```

Put `GEMINI_API_KEY` in `.env` for actual AI inference (never in frontend code). Then:

```bash
docker compose up --build -d
```

Open <http://localhost:8765> (override the port with `RAIZ_PORT`). Camera AR needs `localhost` or HTTPS; print or display [`assets/ar/target.png`](assets/ar/target.png) and press **Start camera AR**.

Offline development without a key (scenes are labeled **FIXTURE — not actual AI inference** end to end):

```bash
RAIZ_AI_PROVIDER=fixture docker compose up -d
```

Check actual inference once a key is configured (one tiny structured request, trace returned):

```bash
curl -X POST http://localhost:8765/api/ai/selftest
```

Workflow (top bar): **Explore** (real NISAR, Sentinel-1, HLS and rain layers by date) → **Zones** (draw, edit, optional boundary proposal, confirm; DEM slope measured) → **Evidence** (slope distribution, radar acquisitions) → **After rain** (2026 rainfall and Sentinel-1 before/after) → **Plan** (species, budget; seeds, germination and establishment kept separate) → **Future** (AI scenario on 3D terrain and in camera AR) → **Report** (printable draft). A first-run guide explains each step; **Guide** reopens it.

## Tests

Python property tests, API tests and the stateful job model run in the Linux/Python 3.12 image:

```bash
docker run --rm -w /app -e PYTHONPATH=/app -v "$PWD:/app" raiz-sar-ai:dev python -m pytest tests --hypothesis-show-statistics
```

Bounded mutation fuzzing of GeoJSON, AI scene, report and plan boundaries (findings saved under `.local/fuzz/`):

```bash
docker run --rm -w /app -v "$PWD:/app" raiz-sar-ai:dev python tests/fuzz/fuzz_boundaries.py --iterations 20000 --seed 1
```

Frontend core properties (fast-check) and the camera-pipeline AR check (Chromium fake camera fed with a video of the printed target; the stack must be running):

```bash
node --test tests/js/core.property.test.mjs
```

```bash
docker run --rm -w /app -v "$PWD:/app" raiz-sar-ai:dev python tools/make_fake_camera.py assets/ar/target.png .local/qa/fake-camera.y4m
```

```bash
node tests/js/ar_camera_check.mjs http://localhost:8765 .local/qa/fake-camera.y4m
```

End-to-end walk through every step in headless Chromium (draws a zone with clicks; uses the live sources and, when configured, Gemini), with screenshots in `.local/qa/ui/`:

```bash
node tests/js/ui_flow_check.mjs http://localhost:8765
```

Set `RAIZ_PBT_SCALE` to scale example budgets. Rebuild the AR target with `node tools/build_ar_target.mjs`.

## Read first

Agents first read local [`context/START_HERE.md`](context/START_HERE.md). [`AGENTS.md`](AGENTS.md), [`CLAUDE.md`](CLAUDE.md) and [`GEMINI.md`](GEMINI.md) route agents to shared instructions. `context/` and `prompts/` are ignored and absent from clones; copy them through an authorized private channel when needed. Report missing private context rather than claiming it was read.

## Current solution

Support environmental/GIS specialists and municipal planners evaluating where locally appropriate vegetation could contribute to erosion control and slope reinforcement, informed by NISAR evidence, terrain and field/ecological assessment.

1. A prevention-oriented approach using suitable root-forming trees/vegetation, without guaranteeing that planting prevents every huaico.
2. A drone extension that **plants seeds or seed capsules** (planning only; nothing is flown).
3. A **required interactive geospatial map with AR**.
4. **Required AI-assisted construction of an interactive future planting scenario in AR**, with assumptions and generated content clearly labeled.

Satellite and SAR evidence also points to strategic sites where rainwater ponds after the rains: planted with species that need the least irrigation and fertilizer (at most three types), they become candidate planting sites, not only huayco protection slopes ([ADR 0003](docs/decisions/0003-ponding-sites-piura-tumbes-and-twin-views.md)).

The study area is Piura and Tumbes, focused on Piura, Sullana, Paita, Talara and Sechura; the Carabayllo fixture remains for tests only. Users draw zones with 4 to 8 vertices. 3D views show observed ponding (before), planted trees (after) and a huayco descending a quebrada with and without the trees, on the real DEM; they are illustrative, not hazard models. Species are source candidates, not approved prescriptions.

Performance: every API request and job writes its timings to `<runtime>/logs/perf.jsonl` (and a `Server-Timing` header); summarize with `python tools/perf_report.py <path> --since 600`. Open the app with `?perf` to inspect browser phases, per-operation durations and long tasks. Browser session IDs and API request IDs distinguish slow operations from time since navigation. Background bulk warmup is opt-in (`RAIZ_DEM_PREFETCH=1`). External calls share host-wide slots (`RAIZ_UPSTREAM_SLOTS`, default 12; `RAIZ_UPSTREAM_WAIT_S`, default 20) and answer 503 with `Retry-After` when saturated; ponding extraction runs as an `evidence` job in the workers. Video export: `node tests/js/video_export_check.mjs`. See the [measured audit and phased delivery plan](docs/PERFORMANCE_AUDIT.md) and [ADR 0004](docs/decisions/0004-demand-driven-map-loading.md).

## Architecture

| Path | Responsibility |
| --- | --- |
| `index.html` | Single entry point: page shell and the pure core logic (`raiz-core`) shared with the property tests |
| `app/` | Native ES modules: `main.js` (steps, legend, guide), `panels.js` (one renderer per step), `map.js` (MapLibre, OpenFreeMap, GIBS, DEM terrain), `draw.js` (terra-draw zones), `charts.js`, `ar.js` (MindAR/A-Frame), `styles.css` |
| `raiz_sar/terrain.py`, `zones.py`, `sources.py` | Copernicus DEM tiles and slope, zone validation and boundary proposals, GIBS date availability, NASA POWER rainfall, ASF acquisition timeline |
| `raiz_sar/api.py` | FastAPI resources: scenarios, GIS normalization, versioned plans, scene/report/SAR jobs, evidence files |
| `raiz_sar/contracts.py` | Shared Pydantic contracts and evidence classes |
| `raiz_sar/planning.py`, `drone.py`, `plans.py` | Eligibility-first allocation, seed/plant quantities, delay sensitivity, seed-deposition plan |
| `raiz_sar/scene.py`, `ai_provider.py`, `safety.py` | Gemini structured output → validation → deterministic scene assembly |
| `raiz_sar/report.py` | Planning draft with source-tagged statements |
| `raiz_sar/sar/` | ASF discovery, GCOV inspection/windowing, dB layers, zonal statistics, COG/preview/manifest |
| `raiz_sar/jobs.py`, `tasks.py`, `worker.py`, `db.py` | RQ/Valkey jobs with idempotent IDs, legal transitions, leases and SQLite metadata |
| `tests/` | Hypothesis properties, stateful job model, API tests, fuzz harness, fast-check and AR checks |

Stack, pins and decisions: [TECHNOLOGY_STACK.md](docs/TECHNOLOGY_STACK.md), [ADR 0001](docs/decisions/0001-technology-stack.md), [requirements.txt](requirements.txt), [requirements-dev.txt](requirements-dev.txt), [target lock](requirements-linux-py312.lock) and [frontend manifest](frontend-dependencies.json).

## Source and scope

- [Current solution source and owner overrides](docs/SOURCE_CONTEXT.md).
- [Scope, data contracts and acceptance gates](docs/SCOPE_AND_VALIDATION.md).
- [Sources, scientific constraints and decisions](docs/SOURCES_AND_DECISIONS.md).
- [SAR foundations and Earthdata software evaluation](docs/SAR_FOUNDATIONS.md).
- [Implementation status, evidence and blockers](docs/IMPLEMENTATION_STATUS.md).
- [ADR 0002: map-first frontend, free real-data sources and Piura focus](docs/decisions/0002-map-first-frontend-and-real-data.md).

Earlier files in `docs/research/` remain dated background and do not select product directions.

## Scientific interpretation

Radar backscatter is not automatically a measurement of buried moisture pockets, penetration depth, survival probability or root reinforcement. The attachment's numeric examples remain unverified illustrations. Seeds deposited do not equal established trees, and an attractive future scene does not validate ecological or geotechnical outcomes. Planning defaults are illustrative placeholders to replace with specialist values.

## Working rules

- English deliverables, code/comments, identifiers, file names and UX/UI; Spanish conversation per the recorded owner preference.
- Exactly one tracked path per new commit; preserve published history.
- Keep `context/` and `prompts/` private and ignored.
- Property-based testing is mandatory for executable logic; use bounded fuzzing at malformed-input boundaries.

See [CONTRIBUTING.md](CONTRIBUTING.md). The code license remains undecided. Respect dataset/library/asset terms and attribution; this is not an official NASA, SERFOR or CENEPRED product.

Browser performance regression: `npm run test:perf`. To inspect the four views without spending model quota, build an explicit fixture with `python tools/build_visual_fixture.py`, then run `node tests/js/visual_layers_check.mjs` against the local server. Video export currently has a reproduced empty-encoder issue in headless Chromium; it is an open gate, with diagnostics and an explicit error instead of an empty-file success. See the audit for the exact verification results.

NISAR's required analytical role and the current integration gap are detailed in [NISAR evidence integration](docs/NISAR_EVIDENCE_INTEGRATION.md): the existing surface-water polygons use optical DSWx-HLS, while the radar overlay and GCOV processing path are separate. Real NISAR-derived water metrics must still be connected to planting assessment and its 3D/AR scene.
