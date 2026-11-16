# ADR 0001 — Product-level GCOV pipeline and minimal AI/AR application stack

> Historical decision record. [ADR 0006](0006-ayumi-bounded-workflow-and-municipal-report.md) supersedes regional navigation, persistent settings, report delivery and sampling policy where they differ. The current public name is Ayumi; original decisions and their evidence are retained below.

- **Date:** November 14, 2026.
- **Status:** selected for implementation planning by the agent within the owner's explicit request to define the stack; runtime/scientific acceptance remains pending.
- **Scope:** RAÍZ-SAR AI, 48-hour demonstrator, one environmental/GIS engineer and two systems engineers.

## Context and constraints

The repository contains documentation/prompts, not a legacy application. The source requests a single HTML frontend, Leaflet, charts, a real interactive AR experience and AI-assisted future planting-scene construction. NISAR must contribute meaningful evidence. Browser code must not contain provider/Earthdata secrets. Large scientific work cannot block interactive reads. Keep one tracked path per commit and private context/prompts ignored.

The owner supplied NASA's [SAR introduction](https://www.earthdata.nasa.gov/learn/earth-observation-data-basics/sar), whose software table includes Python-oriented processing choices. Listing software there does not establish that all products/missions are supported or that raw/InSAR processing is needed.

## Decision

Adopt the exact components and versions in [TECHNOLOGY_STACK.md](../TECHNOLOGY_STACK.md): Python 3.12, FastAPI/Pydantic, RQ with Valkey, SQLAlchemy/SQLite, asf_search and earthaccess, h5py/NumPy/SciPy/Rasterio/GeoPandas/Shapely/pyproj, native HTML/JavaScript/Leaflet/Chart.js/Tailwind/Lucide, MindAR 1.2.5 + A-Frame 1.6.0, and server-side Gemini structured scene generation. Use Hypothesis/pytest and fast-check/Playwright for executable assurance.

Use existing corrected GCOV inputs where available. Start with registered tabletop AR and procedural scene assets driven by validated AI JSON. Keep heavier preprocessing, precise field geolocation and generative meshes outside the critical path unless a requirement/evidence gate justifies an amendment.

## Alternatives evaluated

| Alternative | Benefit | Cost/limit and outcome |
| --- | --- | --- |
| Static HTML with fixtures only | Smallest initial UI | Cannot fulfill actual AI or scientific processing; retain explicit demo mode only |
| Raw/InSAR-first with ISCE2/3 | Useful for focusing/interferometry requirements | Additional compilation/data/phase workflow without a current need; not selected for Level-2 backscatter |
| pyroSAR + SNAP/GAMMA as core | Existing orchestration and preprocessing ecosystem | External processor/native dependencies and product support to verify; optional isolated adapter, not core |
| PyRAT desktop analysis as API engine | Specialist postprocessing/GUI workflow | Desktop dependency and integration overhead; use as research tool only |
| Current h5py + Rasterio + numerical/vector libraries | Direct product-level control and a bounded pipeline | Requires explicit metadata, normalization and science tests; selected |
| React/Next/Vue frontend migration | Component/tooling ecosystem | No existing app to preserve and unnecessary build/state overhead for source's single entry point; not selected |
| WebXR field geolocation first | Potential in-situ scale/presence | Hardware/browser/positioning and registration burden; image-tracked tabletop AR selected first |
| Generative meshes/video as the future scene | Rich appearance | Asset latency/cost and weak spatial/evidence control; structured AI parameters + deterministic geometry selected |
| SQLite custom job queue or FastAPI BackgroundTasks | Fewer services | Worker failure/restart and heavy-job isolation require extra custom mechanics; RQ + Valkey selected |
| Celery + distributed infrastructure | Broader orchestration/scaling | More setup/operations than current timebox warrants; revisit only if RQ limits are measured |
| PostgreSQL/PostGIS immediately | Concurrent/spatial database capability | Extra service/migrations before single-host metadata needs it; defined graduation path |

## Evidence and feasibility

Primary references: [GCOV](https://nisar-docs.asf.alaska.edu/gcov/), [asf_search](https://docs.asf.alaska.edu/asf_search/basics/), [earthaccess](https://earthaccess.readthedocs.io/en/latest/), [pyroSAR](https://pyrosar.readthedocs.io/en/latest/), [Rasterio installation](https://rasterio.readthedocs.io/en/stable/installation.html), [RQ](https://python-rq.org/), [Valkey releases](https://valkey.io/download/), [MindAR paired example](https://hiukim.github.io/mind-ar-js-doc/quick-start/overview/), [Gemini model](https://aistudio.google.com/docs/models/gemini-3.8-flash) and [structured outputs](https://ai.google.dev/gemini-api/docs/structured-output).

Checked official package metadata and a Linux-targeted Python 3.12 binary-wheel dry-run resolving 88 packages; no application or target runtime was installed. The resolution was initiated by Python 3.11 on Windows, so target-environment markers/ABI and runtime imports remain unverified. Frontend exact versions follow official release/documentation evidence; artifact delivery/device behavior still needs testing. No local scene download, inference, camera session, throughput/accuracy benchmark or field evaluation was executed.

## Trade-offs

- **Security:** secrets remain in API/workers; model/queue payloads are constrained and no arbitrary generated code executes. Hosted model terms/account access still need verification.
- **Performance:** precomputed small artifacts and separate SAR/AI queues protect read paths. No unmeasured latency, FPS or throughput is promised.
- **Scalability:** worker counts can grow after memory/provider limits are measured; multi-host state requires the database/storage upgrade.
- **Ergonomics/maintenance:** one Python baseline and a simple browser entry point fit the team; binary GIS dependencies and pinned AR versions need regression checks.
- **Cost:** open-source local components avoid requiring a paid GIS server. Provider inference, hosting/egress and operations are real costs, not assumed free.
- **Portability:** no production Node frontend runtime; Python wheel lock is platform-specific, and the current Windows interpreter is not the target environment.
- **Complexity:** queue service is accepted to avoid implementing durable job machinery. No additional UI framework, vector database or ML-training stack is added without evidence.

## Adoption and rollback

Implement contracts/fixtures first, verify actual AR/AI seams early, then ingest a small verified GCOV crop and run generated-input assurance. Preserve original data and artifact versions. A labeled fixture mode is a diagnostic fallback, not proof that hard requirements passed.

If binary-library compatibility fails, regenerate a consistent Conda-forge target environment. If an AR pair/model becomes incompatible/unavailable, record failure evidence and amend this ADR with a tested replacement. Switching a model/provider does not change scientific truth or permit new data sharing automatically.

## Follow-up — implementation check, November 14, 2026

The selected components were installed and exercised on the target image; no evidence required replacing any of them. Recorded adjustments are operational: the slim Python image needs `libexpat1` for the Rasterio wheel, the hashed lock was regenerated on the target, and the API publishes on port 8765 by default because 8000 was occupied locally. Actual Gemini inference, real GCOV inspection and physical-device AR remain open gates; see [implementation status](../IMPLEMENTATION_STATUS.md).

## Review triggers

Revisit on unsupported Python/binary dependencies, security advisories, model retirement/terms changes, failed target-device registration, measured queue/DB contention, a new raw/InSAR requirement or multi-host deployment. A newer release, more stars or an attractive demo alone does not justify changing the stack. No code-license decision or infrastructure deployment is authorized by this ADR.
