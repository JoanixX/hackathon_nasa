# RAÍZ-SAR AI

### SAR-informed planting assessment, slope bioengineering and AI-assisted AR scenarios

Current solution for the team's **NASA Space Apps Challenge 2026 / Dancing with the SARs** preparation. Repository: `JoanixX/hackathon_nasa` (private). The project has pivoted from the earlier NiñoRadar flood-exposure concept.

**Status: locally runnable prototype.** The API, workers, single-page map, planning modules, GCOV pipeline, AI scene pipeline and camera AR run locally. Sector polygons and SAR layers shown by default are **synthetic fixtures**; actual Gemini inference is **blocked until a server-side key is configured**; physical-device AR is still pending. See [implementation status and acceptance gates](docs/IMPLEMENTATION_STATUS.md).

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

Typical flow: choose a scenario → **Process synthetic GCOV fixture** or place a real GCOV `.h5` in `data/` → **Compute versioned plan** → **Generate AI future scene** → **Start camera AR** → **Generate planning draft** → print.

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

Set `RAIZ_PBT_SCALE` to scale example budgets. Rebuild the AR target with `node tools/build_ar_target.mjs`.

## Read first

Agents first read local [`context/START_HERE.md`](context/START_HERE.md). [`AGENTS.md`](AGENTS.md), [`CLAUDE.md`](CLAUDE.md) and [`GEMINI.md`](GEMINI.md) route agents to shared instructions. `context/` and `prompts/` are ignored and absent from clones; copy them through an authorized private channel when needed. Report missing private context rather than claiming it was read.

## Current solution

Support environmental/GIS specialists and municipal planners evaluating where locally appropriate vegetation could contribute to erosion control and slope reinforcement, informed by NISAR evidence, terrain and field/ecological assessment.

1. A prevention-oriented approach using suitable root-forming trees/vegetation, without guaranteeing that planting prevents every huaico.
2. A drone extension that **plants seeds or seed capsules** (planning only; nothing is flown).
3. A **required interactive geospatial map with AR**.
4. **Required AI-assisted construction of an interactive future planting scenario in AR**, with assumptions and generated content clearly labeled.

The two scenario locators are Río Seco/Carabayllo in northern Lima and lower Piura/Sechura. Their coordinates are approximate, not verified intervention boundaries. Species are source candidates, not approved prescriptions.

## Architecture

| Path | Responsibility |
| --- | --- |
| `index.html` | Single frontend entry point: Leaflet map, modules M1–M8, charts, GIS connector `loadArcGISGeoJSON(url)`, MindAR/A-Frame AR and print view |
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

Earlier files in `docs/research/` remain dated background and do not select product directions.

## Scientific interpretation

Radar backscatter is not automatically a measurement of buried moisture pockets, penetration depth, survival probability or root reinforcement. The attachment's numeric examples remain unverified illustrations. Seeds deposited do not equal established trees, and an attractive future scene does not validate ecological or geotechnical outcomes. Planning defaults are illustrative placeholders to replace with specialist values.

## Working rules

- English deliverables, code/comments, identifiers, file names and UX/UI; Spanish conversation per the recorded owner preference.
- Exactly one tracked path per new commit; preserve published history.
- Keep `context/` and `prompts/` private and ignored.
- Property-based testing is mandatory for executable logic; use bounded fuzzing at malformed-input boundaries.

See [CONTRIBUTING.md](CONTRIBUTING.md). The code license remains undecided. Respect dataset/library/asset terms and attribution; this is not an official NASA, SERFOR or CENEPRED product.
