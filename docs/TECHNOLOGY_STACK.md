# Ayumi technology stack

**Current baseline — November 15, 2026 (Lima):** installed and locally runnable. Scientific validity, physical-device AR and production readiness are independent acceptance gates. [ADR 0006](decisions/0006-ayumi-bounded-workflow-and-municipal-report.md) supersedes broad regional scope and persistent controls; previous ADRs retain historical decisions and source evidence.

## Selected runtime

| Layer | Pinned baseline | Current role |
| --- | --- | --- |
| Python | CPython 3.12, Linux containers | API, numerical/GIS processing and workers; separate from ArcGIS Pro |
| API/contracts | FastAPI, Pydantic | Same-origin resources, evidence classes and versioned plans/scenes/reports |
| Persistence | SQLAlchemy / SQLite, files on a native Docker volume | Single-host metadata, cache and artifact provenance |
| Jobs | RQ 3.0.0 / Valkey 8.1.11 | Separate SAR/evidence and AI queues |
| SAR | earthaccess / h5py 3.16.0 | Authorized discovery/access and preprocessed GCOV window reading |
| Arrays/GIS | NumPy 2.5.4, SciPy 1.18.1, Rasterio 1.5.2, GeoPandas 1.2.0, Shapely 2.2.0, pyproj 3.8.0 | Masked numerical evidence, rasters, geometry and CRS |
| HTTP | HTTPX 0.28.1 | Bounded provider requests, cache/throttle handling |
| AI | google-genai 3.3.0; configured Gemini model | Server-only structured scene construction, validation and deterministic assembly |
| Frontend | One `index.html` entry, native `app/*.js`, plain CSS | No production Node server or framework migration |
| Map | MapLibre GL JS 5.24.1 | OpenFreeMap, Overture MVT, GIBS, native DEM terrain and shared WebGL2 detail |
| Drawing | terra-draw 1.38.0 / MapLibre adapter 1.4.1 | Geographic polygons with 4–8 drawn vertices |
| AR | MindAR 1.2.5 / A-Frame 1.6.0 | Actual image-target camera registration with A-Frame's bundled three.js |
| Charts | Lazy Chart.js, pinned in frontend manifest | Evidence, establishment and allocation charts |
| QA | Node 22 / pinned Playwright and fast-check, Python pytest/Hypothesis | Generated contracts, browser checks and bounded fuzzing |

Exact transitive hashes: [x86-64 lock](../requirements-linux-py312.lock), [arm64 lock](../requirements-linux-arm64-py312.lock), [frontend manifest](../frontend-dependencies.json), [dev manifest](../package.json). Docker installs with `--require-hashes`; lock resolution is not runtime/scientific validation. The local JS campaign used preinstalled Playwright 1.64.1 and a mirrored fast-check 4.10.2 module; this is explicitly distinct from the package.json fast-check 4.8.0 pin.

## Data and science

Work is limited to small Canchaque, El Faique and Huancabamba residential–ravine/mountain screening windows. The stable `lower-piura-sechura` ID is a compatibility key, not the current geographic scope. Source tiles can overlap a window; no full-department view is offered. Browsing and analysis remain distinct.

The analytical radar path reads NISAR L-SAR GCOV frequency A, HH and available HV; validate actual datasets, masks, coordinates and observation dates. L-band is approximately 24 cm. Do not assume local S-band coverage. HLS/DSWx-HLS is optical evidence, Sentinel-1 is C-band and the GIBS GCOV preview is not a local numeric retrieval. Copernicus GLO-30 is a surface model, not surveyed bare earth.

Keep backend credentials out of URLs, frontend bundles and model prompts. The browser receives bounded derived products rather than whole HDF5 scenes. No pyroSAR/ISCE, custom moisture/survival model or generative mesh service is added. Species suitability and root effects require ecological/geotechnical evidence.

## Performance architecture

- Native terrain: Terrarium tiles, 256 px, source zoom 7–12, ×1 default geometry, explicit work-window bounds. Detail uses three bands with zoom hysteresis and bounded illustrative samples in the map's own context.
- Lazy drawing/charts/territory; explicit analytical loads, request cancellation and stale-result guards. No default full-region warmup.
- Bounded seed-deposition sampling and route visits; incremental route length plus independent final checks. Reproducible engine-2 plan identity and saved manual-plan reuse after integrity validation.
- Static DSM aggregates cached by geometry (128 entries); successful infrastructure aggregates cached by geometry/15-minute bucket (64 entries), with detached results. Independent mapping calls use two bounded threads.
- Complete deterministic reports use a synchronous local endpoint; optional AI narrative stays separate from numeric generation. Server calls can remain slow when providers, coverage or first-time processing require work; caches do not establish guaranteed latency.
- Software graphics keeps half-resolution/static weather. Hardware retains native resolution by default because a preceding global low-quality/vector-LOD experiment did not improve the tail.

The [current audit](AYUMI_DELIVERY.md) records actual repetitions and limitations. No library substitution was needed.

## AI, AR and exports

Gemini constructs a structured future-scene specification, validated against species, geometry, counts, timeline and plan version before deterministic rendering. Failures and fixtures are labeled. The model does not approve species or predict validated outcomes. API keys remain server-side.

MindAR image-target registration is real camera AR, not survey-grade geolocation. Use localhost/HTTPS, the versioned printed target and declared scale. Android/physical-camera testing remains separate from synthetic camera pipeline checks. The camera-free map/3D fallback does not fulfill physical AR acceptance. Images can be disabled before AR snapshot capture; an existing ground texture can also be hidden in the AR HUD. Evidence visibility remains separate.

Preserve the four future/event views and their shared timeline. Huayco narrowing/stopping, procedural vegetation and roots are explicitly illustrative. The owner-reported full-duration video/geographic-reference gates remain open unless separately validated; source counts or successful encoding alone do not close them.

## Hosting and evolution

Local Compose uses three API worker processes, separate job workers and Valkey. Production configuration adds Caddy/HTTPS and architecture-specific hash locks; provisioning, secrets and live health are tracked in [DEPLOYMENT.md](DEPLOYMENT.md). No VM or DNS modification is performed by generating a report or running unit tests.

Stay single-host until measured SQLite contention, multi-host writes, spatial SQL or artifact sharing justify PostgreSQL/PostGIS and object storage. No Kubernetes, vector database or agent framework is needed. Review support/security changes, provider releases, sustained latency/memory traces and geographic reference evidence before changing dependencies or adding detail.
