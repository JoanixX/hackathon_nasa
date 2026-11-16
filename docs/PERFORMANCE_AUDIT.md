# Performance audit and delivery plan

Date: November 15, 2026. Product: RAÍZ-SAR AI. Branch: main; pre-existing uncommitted work preserved. No deployment, commit, new paid inference or drone operation was performed in this audit.

## Outcome

The principal startup problem was unnecessary work, rather than the geographic size of Piura and Tumbes. The basemap already uses viewport tiles. It did not download the world. However, startup added DEM hillshade, probed optical dates, searched ASF, checked several radar/water date lists, and automatically enabled radar. Those operations competed for network, API threads and rendering before the user selected a layer.

The implemented loading policy is: conventional coloured street/building/land-cover map first; dated analytical layers, terrain, charts, drawing tools and AR runtimes only when required. Navigation remains inside the study bounding box. Edge tiles overlap neighbouring territory; this is not an administrative boundary mask.

## Measured evidence

Historical operational log snapshot: <runtime>/logs/perf.jsonl, summarized with tools/perf_report.py. This log mixes older configurations, caches and QA runs: its percentiles identify expensive paths but are not a controlled production benchmark. In particular, 400 plan-validation 422 responses reflect generated invalid inputs; they do not establish 400 user incidents.

| Route | Samples | p50 ms | p95 ms | Maximum ms |
| --- | ---: | ---: | ---: | ---: |
| Terrain tiles | 525 | 59.6 | 35,927.3 | 79,852.4 |
| GIBS image proxy | 365 | 915.1 | 12,554.3 | 54,031.3 |
| Coverage probes | 39 | 1,034.4 | 18,949.7 | 46,603.9 |
| ASF acquisitions | 14 | 153.9 | 18,771.8 | 35,933.1 |
| Available optical dates | 10 | 472.9 | 29,313.3 | 29,313.3 |

Within requests, historical DEM reads reached 78.2 s; GIBS fetches reached 27.7 s. Summed concurrent/nested spans are not wall time. API response timing excludes download/render time in the browser. A single resource snapshot showed the API at 605 MiB and 27.6% CPU; it is not a sustained CPU or memory benchmark.

Controlled browser comparison: Chromium via Playwright 1.64.1, Node 22.23.2, 1280×800, SwiftShader software WebGL, same local API/native runtime volume. Each repetition used a new browser context. Server, OS and upstream caches were retained: these are cold-browser, warm-server measurements, not empty-cache/offline/mobile results. The new default also displays a more detailed city view (zoom 13 versus 10.5) and the Liberty style.

| Metric | Before, three repetitions | After, three final repetitions |
| --- | --- | --- |
| First map idle, seconds | 22.239 / 20.727 / 17.589 | 6.449 / 5.320 / 5.568 |
| Median first idle | 20.727 s | 5.568 s (73.1% lower) |
| Startup heavy-data requests | 48 DEM tiles plus radar/date/coverage work | Zero DEM, GIBS and source-catalog requests |
| Initial diagnostic run request count | 142–144 | 42–44 in the first after-change diagnostic run |

The initial after-change diagnostic sample was 4.398 / 9.939 / 3.809 s. Report the spread: upstream/style delivery still varies. Three samples do not justify a reliable p95 or a general speed guarantee. The final functional session visited all six priority centres in 0.135–2.149 s each with warm server caches. It verified source enablement and rendering, not local ecological coverage or complete building inventories.

Raw local artifacts: .local/qa/performance/before.json, after.json, session.json, visual-check.json, visual-check-quick.json, screenshots, python.xml and operational-snapshot.jsonl. The operational snapshot includes later verification traffic; the historical route table above is the earlier captured summary. Reproduce the final session with node tests/js/perf_session.mjs http://127.0.0.1:8765. Set PLAYWRIGHT_MODULE to an existing installation if needed. The earlier before/after diagnostic harness is retained locally as .local/audit_load.mjs.

## Findings and implemented corrections

| ID | Finding and consequence | Correction / remaining limit |
| --- | --- | --- |
| P1 | Hillshade created a DEM source immediately; at zoom 10.5 the recorded session requested 48 terrain tiles | DEM is created only for explicit terrain shading or 3D. Analytical imagery has study-region source bounds |
| P2 | Catalog → NISAR coverage → RTC coverage → water coverage was a serial startup chain, and NISAR switched on automatically | Startup loads no satellite/catalog data. Each layer has Load available dates, an Off selection and explicit dated activation |
| P3 | Drawing and Chart.js CDN downloads competed with basemap startup | Drawing libraries load on Zones; Chart.js loads only for a chart. Existing camera AR libraries remain lazy |
| P4 | Health was awaited before scenario listing and map construction | Health runs independently. The map does not wait for queue/AI status |
| P5 | Area changes had no stale-response guard; old dates/rain/ponding could overwrite new inputs | Load scopes deduplicate in-flight keys and cancel/invalidate on area or dataset changes. Epoch checks protect even work that ignores abort |
| P6 | Comparison opacity updates recreated raster sources | Same layer/date changes paint opacity in place; switching Off removes the source |
| P7 | Future-panel rerenders eagerly loaded five ponding dates and a terrain path | Evidence loads only when its view opens; rain and catalog loads are deduplicated |
| P8 | Huayco playback rebuilt circle geometry and polygon intersections each frame; interruption could strand its completion promise | Geometry/intersections are prepared once; GeoJSON updates are capped at 24 fps and skipped when unchanged; cancellation settles playback; leaving Future stops it |
| P9 | Browser timestamps since navigation were aggregated as though they were operation durations | Session IDs, separate duration_ms, request IDs, resource timings and long-task events now complement page-relative marks |
| P10 | Legend included hidden hillshade and duplicate building keys; grey styling weakened building context | Liberty basemap, shared 2D/3D building-height palette, conditional legend entries and optional waterway highlighting |
| P14 | A static-view WebM sometimes contained only an encoder header, despite a successful download | Recording now copies labelled frames during rendering, reports frame/chunk/byte diagnostics, rejects empty output and releases all resources. The headless encoder still produces zero bytes in repeated tests; export remains an open compatibility gate |
| P13 | Before/after could populate sources while the camera remained over another city; legend listed content absent from the selected view | Both views frame the scene extent with a pitched camera; hide future-point markers and show view-specific legend entries |
| P12 | Re-rendered panels retained Chart.js instances for discarded canvases | Panel replacement now destroys old charts; pending lazy-chart work checks whether its canvas still exists |
| P11 | AR snapshot could wait indefinitely for a second idle; an outer timeout did not stop that operation | Snapshot waits are bounded and camera/terrain are restored in finally |

Existing native runtime storage, pooled GIBS HTTP client and three API processes were already active at entry. Their earlier claimed gains were not independently re-benchmarked. Keep them, but do not attribute those earlier changes to this audit. Background warmup now defaults to off (RAIZ_DEM_PREFETCH=0); it can still be invoked explicitly. Warming all cities on every restart competes with interactive iteration.

## Delivery sequence and acceptance targets

Targets below are engineering budgets to verify, not measured promises.

| Phase | Work | Exit evidence |
| --- | --- | --- |
| 1 — Delivered | Optional analytical layers, lazy DEM/tools, cancellation, reusable tile sources, conventional map, building palette and correlated timing | Zero heavy-data requests on a fresh default view; current functional/property checks pass |
| 2 — Regional package | Obtain licensed Piura/Tumbes administrative polygons, then build a versioned regional vector/DEM package in spatial tiles; precompute only the five priority urban areas and Tumbes. Include source date, attribution, CRS and checksums. Compare local XYZ tiles against PMTiles before selecting a new dependency | Thirty cold-browser and thirty warm-browser loads on a declared device/network; target visible map p50 ≤3 s and p95 ≤5 s; network-loss test with a retained usable map; verify no unrequested layer work |
| 3 — Evidence jobs | Cache date manifests by layer/AOI/time; expose last-valid dated data with explicit age. Bound server-wide external concurrency and move expensive ponding extraction/DEM generation into existing workers. Reuse the rendered tile cache for mosaics | Repeated identical requests avoid duplicate external work; queue/backpressure/cancellation and upstream 429/5xx tests; interactive health/plan reads stay responsive while a cold evidence job runs |
| 4 — Detailed 3D and AR | Share a versioned asset/placement manifest between map and AR. Use three approved species meshes with instancing, levels of detail and visible-area chunks; add georeferenced buildings, roads, vegetation and verified quebradas in priority neighbourhoods. AR needs actual building geometry, not only a flat snapshot | Same coordinates, scale, species colours, evidence date and plan version across 2D/3D/AR; sample asset budget ≤2 MB per species and ≤5,000 triangles per near-detail model; ≥30 fps on declared target hardware with a bounded visible tree count. Budgets must be tested before mesh adoption |
| 5 — Four-view comparison and video | Keep a common camera/time/evidence context for before ponding, after planting, huayco with intervention and huayco without intervention. Record 3D videos with captions/date/assumptions and accessible text controls; test cancellation/download cleanup | Resolve the reproduced empty-encoder output before accepting WebM export; four complete recordings on target hardware; consistent water/vegetation/mud legend; physical-device AR registration/loss/reacquisition; no unsupported efficacy claims |

Regional extraction is useful for predictable delivery and offline iteration, but does not fix unnecessary work by itself. Keep spatial chunks and level-of-detail loading; do not replace the map with one large region-wide GeoJSON or a flattened screenshot. No archive was downloaded or new renderer installed in this audit. See ADR 0004 for the alternative comparison and research.

## Product coverage and open gates

- Piura/Tumbes focus buttons, optional dated layers, chosen 4–8 drawn vertices, three Piura candidate species, coloured footprints/extrusions and the four-view controls exist. Imported GIS boundaries retain their source geometry; no silent vertex reduction is performed.
- Ponding is candidate-site evidence, not fertility or a planting prescription. Radar remains an important complementary observation; the displayed DSWx-HLS water product is optical. Cloud, salinity, water permanence, land ownership and establishment needs require checks. Species low-water labels do not establish zero irrigation or quantified fertilizer needs.
- Current tree models are procedural approximations by species. They are not exact individual digital twins. Exact trees require an identity, measured dimensions/photographs or a scan, and an approved asset. Heights and crowns in the current catalog are illustrative dimensions, not field measurements.
- Current water thickness, mud spread and vegetation resistance are illustrative. Water depth/volume and a debris-flow event cannot be recovered from these coloured tiles. The same terrain path must be used for comparing interventions; do not move the start point just to force a collision with trees. This audit removed that automatic rerouting.
- AR currently drapes streets/buildings as a texture and adds vegetation/water/mud meshes. Full georeferenced 3D urban geometry, higher-fidelity tree assets and hardware frame-rate validation remain open gates. A camera-free 3D view does not satisfy physical AR acceptance.
- No validated heat/risk raster was identified. Do not add a heat legend without a dated, defined dataset and the corresponding visible layer.

## Verification performed

- Final browser session: startup without heavy-data requests, all six focus areas, terrain/waterway visibility, 4/5/6/7/8 vertex placement, 3D source and building palette, and mobile horizontal-overflow check passed. Screenshots were inspected. No new AI request was made. A fixture-based browser run also exercised all four source layers on real DEM/DSWx inputs and the same terrain path for both huayco views. Its first video export passed a size check, but subsequent checks reproduced zero-byte files, so video acceptance is explicitly not passed. Later view-only checks are recorded separately from export checks.
- JavaScript: 17 existing core property tests plus six new generated properties and one cancellation regression; the new properties execute 10,000 generated cases (5,000 load scope, 1,500 map toggles, 1,500 playback, 1,000 recording cleanup, 1,000 chart lifecycle). Seed 20261115 is fixed for the new properties. The existing core suite executes 49,700 configured generated cases across its named properties.
- Python: 20 telemetry/terrain/zone tests and 20 API tests passed. The targeted telemetry/terrain/zone run reports 17,560 passing property examples, zero failures and 1,727 invalid draws; invalid draws are filtering, not failed assertions. New telemetry properties account for 3,500 passing examples.
- Bounded mutation fuzzing: 5,000 inputs per target × five targets =25,000 executions, 6,194 parseable JSON inputs reaching the respective boundaries, zero findings. Includes the new telemetry boundary. Seed 20261115; 256 KiB input limit, 2 GiB process address-space limit, 5 s per input. This is mutation fuzzing, not coverage-guided fuzzing.
- git diff --check passed. WebM export is not reliable in this headless environment: even with 30–51 copied frames and a nonzero map-image colour range, repeated encoder runs returned no chunks. Standalone codec probes also varied by codec/resolution. This isolates a capture/encoding compatibility problem; it does not yet establish a unique browser or application root cause. Empty files now cause a visible logged error instead of a successful-download claim. Test target browsers and compare a worker-based frame encoder before choosing an additional dependency. Full scientific validation, exact-asset validation, physical-device AR and production load testing are separate, pending gates.

The final tree diagnostic confirmed 2,228 procedural tree features for a 557-placement fixture and 1,686 rendered tile features in the viewport (tile query counts include duplicates). The inspected screenshot shows the canopy markers; these remain small per-species approximations. Waiting for an empty source's loaded flag alone was insufficient to establish that a subsequent update had appeared. Detailed tree readability remains a phase-4 requirement, not a completed exact-twin gate.

## Mandatory NISAR analytical gate — owner clarification

The owner clarified that NISAR must drive the water/ponding evidence, measurements and candidate planting assessment. The current DSWx-HLS water polygons are optical; a GIBS NISAR overlay is a separate visualization. A read-only local evidence query returned two synthetic GCOV manifests and no processed real NISAR manifest for Piura. Current allocation uses slope/area/species/budget rather than requiring a NISAR water result.

Add the mandatory [NISAR evidence integration work package](NISAR_EVIDENCE_INTEGRATION.md) alongside the performance phases and before claiming a complete NISAR-informed planting workflow. It specifies the current code seams, real-data/classifier/metrics/plan/AR gaps and acceptance evidence. Keep processing in workers and serve cached spatial chunks; required analysis does not need to block the conventional initial map.

## Phase 3 and phase 5 progress — November 15, 2026 (later the same day)

Phase 3 — evidence jobs (implemented; `raiz_sar/upstream.py`):

| Gate item | Implementation | Evidence |
| --- | --- | --- |
| Server-wide external concurrency | Every GIBS, NASA POWER and ASF call takes one of `RAIZ_UPSTREAM_SLOTS` (default 12) host-wide slots: file locks under `<runtime>/locks/upstream`, shared by the three API processes and both workers and released if a process dies. A request that cannot get a slot within `RAIZ_UPSTREAM_WAIT_S` (default 20 s) gets **503 `upstream_busy` with `Retry-After`** instead of piling up threads; the browser helper retries after that delay | Property test: 1–4 slots, 2–7 forked processes, peak concurrency never above the slot count; saturation returns 503 in under 2 s |
| Upstream 429/5xx | 429/502/503/504 and transport errors are retried at most twice, with backoff and `Retry-After` capped at 4 s; the slot is released while backing off. GIBS 500 (deterministic for some date/tile pairs) is not retried. A failed date probe is *unknown* (`probe_errors`, `valid_fraction: null`), never cached as "no data" | Property test over 1,500 generated status sequences compares calls, final result and sleeps with an oracle |
| Date manifests with age | Date lists, coverage, rainfall, ASF catalog and ponding are cached per layer / probe tile (AOI) / time range with `cache.cached_at`, `age_s`, `ttl_s`. TTL: 6 h while a range is recent, 7–30 days once it is past, 10 min when incomplete. When a refresh fails the last valid copy is returned with `cache.stale: true` and the interface says "Last valid copy from N h ago" | Tests: stale copy served and labelled; no copy → error; validation errors never fall back |
| Duplicate external work | Cross-process single flight per cache key: identical concurrent builds run once. Raw GIBS tiles are cached once (`gibs_raw`) and shared by the map proxy and the DSWx mosaics | Property test: 2–10 concurrent identical builds → one build; ponding test: repeated identical requests make no external call |
| Ponding extraction off the API | `GET /api/sources/ponding` returns 200 when built, otherwise **202 with an idempotent `ponding` job** on the new `evidence` queue, served by the existing workers (`worker-ai`: `ai,evidence`; `worker-sar`: `evidence,sar`, so a multi-GB SAR download never blocks it). Expired results re-run their job. Mosaic tiles that fail are counted (`tiles_failed`) and shown as unknown | Live: first request 202 → worker built 237 water bodies (Piura, 2026-02-27) → next request 200 from cache in 0.6 s |
| Interactive reads stay responsive | Health and scenario reads do not touch upstream slots | Test: with every slot held, `/api/health` and `/api/scenarios` answer in < 2 s |

Found while verifying phase 3 in the full browser flow: (1) RQ runs each job in a forked child that re-imported the handlers (Gemini client, rasterio, GDAL: about 1.4 s idle); under the CPU load of software-rendered 3D that start-up took about 2 minutes. Workers now import them once in the parent process; a cold Sechura ponding job then took 6.4 s end to end (3.0 s in the worker). (2) The ASF catalog ran the NISAR and OPERA searches one after the other (31 s under load); they now run concurrently (7.8 s cold, idle). Both measurements are single local samples, not benchmarks.

Not done in phase 3: DEM tile rendering and the flow-path/high-point endpoints still run in the API processes (map tiles must answer synchronously; they are bounded by the per-process render semaphore and the region limit). Server-side cancellation of an evidence job is not implemented: the browser stops polling on abort, and the job still finishes and fills the cache (it is idempotent).

Phase 5 — video export (empty-encoder gate):

- Root cause isolated: in headless Chromium `MediaRecorder` returned no chunks, while **WebCodecs `VideoEncoder` (VP8) encoded every frame** (probe: 30/30 frames). Recording now prefers WebCodecs with a dependency-free WebM muxer (`app/webm.js`, EBML/Matroska: one VP8 track, SimpleBlocks in clusters, no Cues) and keeps `MediaRecorder` as the fallback. Frames are copied in MapLibre's render callback and encoded by a fixed-rate clock, so the timeline follows real time even when rendering is slow; the encode queue is bounded (drops are counted).
- `tests/js/video_export_check.mjs` records the 3D map three times and decodes each file in the browser: **3/3 decoded at 1280×800 with picture** (pixel range 202–213 at mid-duration). fast-check: the muxed file parses back to exactly the given frames, timestamps and key flags (1,500 runs) and EBML sizes round-trip (3,000 runs).
- Still open: on software WebGL the encoder drops most ticks (50–62 per 3 s), so videos are short (1.2–2.6 s of 3.2 s) and low-frame-rate. Four complete recordings on target hardware with a GPU remain the acceptance gate, as do physical-device AR checks.

Phases 2 and 4 need owner inputs before work can start: a licensed source and redistribution terms for the Piura/Tumbes administrative polygons and the regional basemap extract (phase 2), and approved species meshes or a decision to keep procedural trees under the stated budget (phase 4).
## Owner-reported failures and required visual/spatial acceptance update

The owner reports that the actual tree-growth, 3D huayco and video workflow is not functioning, and that buildings/parks/roads/water do not adequately represent the real place. These reports reopen end-to-end acceptance even where narrower codec/source tests previously passed. They are recorded as owner-reported defects; no fresh reproduction or executable fix is claimed in this documentation update.

The mandatory [visual, spatial and water-quality work package](NISAR_EVIDENCE_INTEGRATION.md) now contains NV-01 through NV-07: a working growth timeskip with event arrival; ravine-only starts with clear invalid/unknown messages and server enforcement; planting exclusions for roads, houses and pedestrian circulation; validated real NISAR water detection; correct building coverage and textured parks/roads/water; consistent 2D/3D/AR views and full-duration decoded videos under the speed budgets.

NISAR remains essential analytical evidence, supported by terrain, hydrography and suitably detailed geographic references for ravines and infrastructure. Do not promise that radar alone resolves individual houses, sidewalks or tiny puddles. Preserve missing-evidence states, avoid invented buildings, and do not accept source counts, isolated encoder probes or non-empty files as proof that the user workflow works. Follow the ordered delivery and acceptance evidence in that work package. Existing phase-3/5 implementation notes above remain scoped historical evidence, not final acceptance of these newly clarified requirements.
