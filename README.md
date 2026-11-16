# Ayumi

SAR-informed planting assessment with an interactive map, AI-assisted future scenarios and camera AR. Formerly RAÍZ-SAR AI; NiñoRadar remains historical research.

**Current baseline — November 15, 2026 (Lima):** locally runnable prototype. Work is limited to small residential–ravine/mountain screening windows around **Canchaque, El Faique and Huancabamba**, not the entire Piura department or Tumbes. Windows are approximate locators for assessment, not official hazard boundaries or approved planting sites. Dry-forest species require particular scrutiny at Andean elevations.

Explore starts with OpenFreeMap streets/land cover and Overture building footprints. Analytical imagery, terrain and area analysis load on request. Steps use bounded pages and explicit detail dialogs. The compact key opens complete sources; **3D settings** opens separately; **Images on/off** controls imagery and AR texture capture. Terrain defaults to ×1; procedural trees, weather, roots and huayco effects are illustrative.

## Run locally

Use Docker Desktop with Linux containers. Keep ArcGIS Pro and global Python environments separate.

```powershell
Copy-Item .env.example .env
docker compose up --build -d
```

Open [localhost:8765](http://localhost:8765). Configure `GEMINI_API_KEY` only in the server `.env` for actual inference. For offline development, set `RAIZ_AI_PROVIDER=fixture` before starting; fixture scenes are labeled and are not actual AI. Never commit credentials.

The Python module, `RAIZ_*` configuration, scenario IDs and AR tracking target keep their existing protocol names for compatibility. The page/API/report product name is Ayumi. Camera AR uses MindAR/A-Frame and the [printed target](assets/ar/target.png), on localhost or HTTPS. Physical-device tracking remains a separate acceptance gate.

## Workflow and report

1. **Explore:** choose a local window; optionally load dated radar, optical, surface-water and rainfall context.
2. **Zones:** draw 4–8 vertices or import GIS boundaries; confirm terrain/infrastructure checks. Out-of-window Piura sectors are rejected before planning.
3. **Evidence / After rain:** inspect coverage, acquisition dates, slope, radar and rainfall; preserve unknown values.
4. **Plan:** select candidate species, assumptions and budget. Capsules, seeds, seedlings and established plants remain distinct. Sampling and route-preview work are bounded; oversized previews require phasing.
5. **Future:** request the server-side Gemini scenario, then inspect it in 3D or actual camera AR. A generated future is a scenario, not a validated prediction.
6. **Report:** generate the complete deterministic municipal-review draft without an AI queue or model charge; open it or print/save as PDF. Optional AI narrative remains available through the existing queued report API.

The report includes geodesic union coverage, species resources, reconciled budget items, formulas, qualitative economic/environmental opportunities, implementation responsibilities/gates, monitoring, risks, sources and unpriced resources. Its total is the **modeled priced scope**, not an approved investment budget. OSCE Opinion 040-2021 supplies historical quantity × unit-price arithmetic; editable rates remain assumptions until locally quoted. No official tariff or current procurement-law approval is implied.

## Validation and speed

```powershell
docker compose exec -T api python -m pytest tests --hypothesis-show-statistics
npm run test:props
node tests/js/ayumi_check.mjs http://127.0.0.1:8765
docker compose exec -T api python tests/fuzz/fuzz_boundaries.py --iterations 10000 --seed 16
```

Install the pinned dev dependencies and Playwright Chromium first. The Ayumi browser check uses real map/DEM data and explicitly synthetic planning inputs, without paid inference. Set `TERRITORY_RENDERER=hardware` to exercise D3D11 instead of SwiftShader. `PLAYWRIGHT_MODULE` and `FAST_CHECK_MODULE` may point to existing module entry points. Earlier browser scripts retain their historical layout assumptions.

Measurements, reproducible commands and open gates are in [the current delivery audit](docs/AYUMI_DELIVERY.md), [performance history](docs/PERFORMANCE_AUDIT.md) and [implementation status](docs/IMPLEMENTATION_STATUS.md). A synthetic 1,000 ha deposition benchmark improved from a 1.175 s median to 65.6 ms; this is not an end-to-end multiplier or a stable-FPS claim.

API/jobs record durations in `<runtime>/logs/perf.jsonl`; responses expose `Server-Timing`. `?perf` enables browser diagnostics. Summarize with `python tools/perf_report.py <path> --since 600`. Bulk warmup is opt-in (`RAIZ_DEM_PREFETCH=1`) and uses local windows.

## Architecture and evidence

| Path | Responsibility |
| --- | --- |
| `index.html`, `app/` | Single HTML entry; native ES modules, MapLibre 5.24.1, lazy tools/charts/territory, bounded steps and camera AR |
| `raiz_sar/api.py`, `contracts.py` | FastAPI, versioned resources and immediate report preview |
| `scenarios.py`, `zones.py`, `terrain.py`, `exclusions.py` | Screening windows, geometry validation, Copernicus DSM and cached exclusions |
| `planning.py`, `plans.py`, `drone.py` | Eligibility, quantities, allocation and bounded candidate deposition routes |
| `report.py`, `municipal.py` | Reproducible municipal-review draft, source-tagged statements and costs |
| `nisar_evidence.py`, `sar/`, `sources.py` | GCOV processing, optical/rainfall reference checks and catalog/imagery provenance |
| `scene.py`, `ai_provider.py`, `jobs.py`, `tasks.py` | Validated Gemini scenes, RQ/Valkey workers and persisted artifacts |
| `tests/` | Hypothesis, fast-check, API/browser checks and bounded fuzzing |

NISAR analysis uses **L-SAR GCOV frequency A, HH and available HV**, approximately 24 cm wavelength. S-band availability over Peru is not assumed. Backscatter is not hidden-water depth, survival probability or root stability. Copernicus terrain is a surface model; incomplete mapping does not establish ground clearance. Keep source dates, coverage and uncertainty with every claim.

Read [source/overrides](docs/SOURCE_CONTEXT.md), [scope/acceptance](docs/SCOPE_AND_VALIDATION.md), [sources](docs/SOURCES_AND_DECISIONS.md), [SAR foundations](docs/SAR_FOUNDATIONS.md), [stack/pins](docs/TECHNOLOGY_STACK.md) and [ADR 0006](docs/decisions/0006-ayumi-bounded-workflow-and-municipal-report.md). Deployment configuration and its provisioning gates are in [DEPLOYMENT.md](docs/DEPLOYMENT.md); configuration files alone do not prove a live site.

## Working rules

English source/UI/docs/artifacts/commits; Spanish conversation. Exactly one tracked path per commit. Keep `context/`, `prompts/`, `.env`, runtime caches and rasters private/ignored. Agents start at local `context/START_HERE.md`; fresh clones use [AGENTS.md](AGENTS.md) if it is missing. See [CONTRIBUTING.md](CONTRIBUTING.md).

The code license remains undecided. Preserve dataset/library attribution. Ayumi is not an official NASA, SERFOR, IGP, INGEMMET or CENEPRED product. Generating a plan does not operate a drone or send an external alert.
