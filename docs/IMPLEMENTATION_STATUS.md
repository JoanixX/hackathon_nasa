# RAÍZ-SAR AI — Implementation status and acceptance evidence

**Date:** November 14, 2026 (America/Lima). **Scope:** first runnable implementation of the selected stack. Everything below distinguishes what was executed from what remains blocked. Software tests are not ecological, geotechnical or user validation.

## Map-first refactor (ADR 0002) — November 15, 2026

[ADR 0002](decisions/0002-map-first-frontend-and-real-data.md) replaced the module-ordered interface with a guided, map-first workflow on real free data. Verified in headless Chromium (`tests/js/ui_flow_check.mjs`, `relief_check.mjs`, `ar_camera_check.mjs`) and the Linux/Python 3.12 test image:

| Gate | Status | Evidence |
| --- | --- | --- |
| RZ-15 Compliant basemap | Met | OpenFreeMap only; no request to `tile.openstreetmap.org`; `Referrer-Policy: strict-origin-when-cross-origin`; Leaflet flag removed with Leaflet |
| RZ-16 Legible optical context | Met | HLS S30 at its native GIBS level, dates limited to days with pixels; VIIRS only regional |
| RZ-17 Real SAR on the map | Met | NISAR GCOV (June–October 2026) and Sentinel-1 OPERA RTC (January–May 2026) via GIBS; dates filtered by measured coverage; black no-data made transparent by the API proxy without changing data pixels |
| RZ-18 Zone delimitation | Met | Drawing by clicks, vertex editing, self-intersection, area, region and overlap checks; original and confirmed geometry stored |
| RZ-19 Assisted boundary is a proposal | Met | SLIC (scikit-image) on DEM slope and HLS colour; shown beside the zone with IoU, area change and largest shift; applied only on "Use the proposal" |
| RZ-20 Charts with real data | Met | NASA POWER rainfall with ASF acquisition markers; DEM slope distribution; plan quantities; delay chart only with an entered half-life |
| RZ-21 Coherent 2D/3D/AR terrain | Met in software | One Copernicus DEM for slope, MapLibre terrain/hillshade (local cell cache, ~1 s per tile) and the AR mesh; declared exaggeration (×1/×3/×6 on the map, capped and declared in AR); OSM buildings extruded at city zoom with tag-based or default heights, declared. Physical-device AR still pending |
| RZ-22 Guided UX | Met for this increment | Seven-step flow, gated steps that say why, first-run guide, provenance legend, phone layout without overflow; no user study yet |

Run results on November 15, 2026: AI scene by actual inference (`gemini-3.8-flash`) on DEM terrain; camera-pipeline AR 10/10; fast-check 17 properties, about 43,700 cases, all passed. The full-budget Hypothesis campaign was running when this revision was committed; the last reduced-budget run passed after the fixes below.

Defects found and fixed in this phase: panel not refreshed after asynchronous actions; funded share drawn as an arbitrary southern strip (now the zone core, declared); evidence image stretched over the whole AR target; terrain using the vegetation exaggeration; jobs stuck as ready after artifact loss (now re-queued); original geometry not stored when omitted; concurrent requests for one terrain tile sharing a temporary file; slow remote DEM reads (local cell cache); one-cell GCOV axes treated as zero width. Oracle errors found and documented in tests: two star-polygon counterexamples confirmed self-intersecting by Shapely; sub-0.05 ha slivers correctly rejected by the area rule.

## Evidence classes used in the product

| Class | Meaning in this build | Examples |
| --- | --- | --- |
| Real data | Fetched from an external authoritative source | ASF catalog discovery results; OpenStreetMap and NASA GIBS basemap tiles |
| Synthetic fixture | Generated for development, labeled end to end | Default sector polygons; `SYNTHETIC_FIXTURE_GCOV_*` HDF5 products and their derived layers |
| Derived | Computed from an input by a documented method | Geodesic areas, dB layers, zonal medians, tabletop coordinates |
| Modeled | Computed under user-entered assumptions | Capsules, seeds, expected germination/establishment, costs, delay sensitivity |
| AI-generated / fixture scene | Model output after validation, or the labeled fixture stand-in | Scene patterns, stage parameters, captions, report narrative |
| Illustrative | Placeholder or conceptual | Default planning assumptions, slope placeholders, root cutaway |
| Unknown | Not available; never coerced to zero | SAR values before processing, dielectric constant, survival, erosion/carbon/protected homes |

## Acceptance gates

| ID | Status | Evidence / blocker |
| --- | --- | --- |
| RZ-01 Identity and scope | Met | UI, API and docs use RAÍZ-SAR AI and the prevention-oriented wording; no guarantee claims (enforced by `safety.py`) |
| RZ-02 Both scenarios | Met with fixture geometry | Both selectors work; polygons are labeled synthetic; GIS import replaces them with real boundaries |
| RZ-03 Essential NISAR contribution | **Partially met** | GCOV pipeline implemented and tested on synthetic HDF5. Live ASF query found NISAR L2 GCOV granules over both AOIs (Carabayllo: `SHSH` single-pol, ~1.35 GB; lower Piura: `DHDH` dual-pol, ~6.48 GB). **Blocked:** download/inspection needs Earthdata credentials (`EARTHDATA_USERNAME/PASSWORD`) or a manually placed `.h5` in `data/` |
| RZ-04 Honest science | Met in software | Unknown values stay null; RVI is computed only with HH, HV and VV; normalization read from metadata; banned-claim filter on all model text |
| RZ-05 Eligible planting plan | Met | Exclusions and unknown slope are applied before allocation; properties verify excluded sectors never receive capsules |
| RZ-06 Consistent quantities and budget | Met | Integer centimos; seeds = capsules × seeds per capsule; established ≤ germinated ≤ seeds; property-tested |
| RZ-07 Required interactive AR | **Partially met** | MindAR 1.2.5 + A-Frame 1.6.0 tracked the printed target from real camera frames (Chromium fake camera fed with a recorded video): target found 2.4 s after start, tracking loss hides overlays, reacquisition, horizon change, zone inspection, camera released on exit, permission denial reported. **Pending:** a recorded session on a physical device (desktop webcam and Android Chrome over HTTPS) |
| RZ-08 AI future-state construction | **Met (actual inference)** | With the owner's server-side key: `/api/ai/selftest` returned a schema-valid, correct answer from `gemini-3.8-flash` (3.9 s). Scenes for both scenarios were generated through the AI queue, validated and assembled (Carabayllo response `wNb4auWFEZau0_gPus6z-Qs`, 16.6 s; lower Piura `29b4atO5KuaYiLMPvfHgkQs`, 18.6 s). In both cases the validator rejected the first model output and the repair attempt passed. Not yet shown on a physical AR device |
| RZ-09 Distinct present and future | Met | Separate colours, labels, map layers and AR layers for evidence, proposal and future; month 0 shows seeds only |
| RZ-10 Correct drone extension | Met | Seed/capsule deposition nodes and sorties bounded by payload and route limit; status always `candidate_plan_incomplete`, `execution: not_executed`; unverified constraints listed |
| RZ-11 Grounded report and printing | Met (narrative AI blocked) | Draft label, sources, dates, units, coordinates, limitations and authorship per statement; print stylesheet. Without a key the report is `partial` with deterministic sections only |
| RZ-12 Compatible GIS import | Met | `loadArcGISGeoJSON(url)` and file import; legacy keys normalized; geometry/units/area checks; rejected features reported without changing the current plan |
| RZ-13 Accessible English UX | Partially met | Keyboard tabs, skip link, live regions, reduced motion, text alternatives; no user study or full contrast audit yet |
| RZ-14 Software assurance | Met for this increment | Counts below; minimized failures retained as regressions |

## Executed verification

| Check | Environment | Result |
| --- | --- | --- |
| Dependency lock regenerated on the target | `python:3.12-slim-bookworm` (CPython 3.12.16, linux x86-64), pip 25.0.1 dry-run report | 86 hashed packages; image builds with `--require-hashes`; all 19 direct imports succeed |
| Python property/API/stateful tests | Same image | See "Test campaign" |
| Mutation fuzzing (not coverage-guided) | Same image, 2 GB address-space cap, 5 s per input | 80,000 inputs (4 targets × 20,000), 27,541 parseable JSON reaching target logic, 0 findings |
| Frontend core properties | Node 22.23.2, fast-check 4.10.2 | 11 properties, 30,700 generated cases, all passed |
| Camera-pipeline AR | Chromium (Playwright 1.64.1 build) with fake camera video of the target, SwiftShader WebGL | 9/9 checks passed (`.local/qa/ar-check.json`) |
| Full stack | Docker Compose: API, SAR worker, AI worker, Valkey 8.1.11 | Plan → scene → report → SAR jobs completed through RQ |
| Live ASF catalog query | asf_search 14.1.0 | NISAR GCOV granules listed for both AOIs; nothing downloaded |

### Test campaign

Final run: `python -m pytest tests --hypothesis-show-statistics` in the target image — **69 passed in 390 s**. Hypothesis executed 22 property/stateful tests with **36,550 passing cases, 0 failing, 927 invalid (filtered) draws**. Counts are Hypothesis-reported executions, not configured budgets.

| Property test | Passing | Failing | Invalid |
| --- | ---: | ---: | ---: |
| Budget and quantity invariants | 3,000 | 0 | 73 |
| More budget never reduces planting (metamorphic)\* | 1,500 | 0 | 31 |
| Target mode meets target or reports infeasible\* | 1,500 | 0 | 26 |
| Establishment scenarios monotone and ordered | 1,500 | 0 | 40 |
| Cents conversion exactness | 2,000 | 0 | 0 |
| UTM round trip / zone formula | 3,000 / 2,000 | 0 | 0 |
| Geodesic vs projected area | 1,500 | 0 | 0 |
| Polygon reprojection identity | 500 | 0 | 171 |
| Tabletop round trip and containment / uniform scale | 3,000 / 1,000 | 0 | 0 |
| Model output cannot override constraints (18 mutation classes) | 1,200 | 0 | 0 |
| Scene validator on arbitrary text/JSON | 2,000 | 0 | 62 |
| Drone plan geometry, payload and route | 150 | 0 | 0 |
| GIS: valid legacy exports / arbitrary JSON / structured mutations | 1,500 / 3,000 / 2,000 | 0 | 48 / 220 / 113 |
| Plan endpoint never returns 500 | 400 | 0 | 46 |
| dB conversion / window indices / RVI bounds | 2,000 / 2,000 / 1,500 | 0 | 28 / 0 / 50 |
| Stateful job lifecycle (25 steps each) | 300 | 0 | 19 |

\* These two properties apply to one planning mode; generated requests of the other mode return early, so roughly half of their cases exercise the property. Concurrency tests (12 simultaneous identical submissions; 10 racing executions) and fixed regressions run in addition. Replay: failing examples print a `@reproduce_failure` blob and are stored in `.local/hypothesis-db`.

### Findings and their resolution

| Finding | Type | Resolution |
| --- | --- | --- |
| Rasterio 1.5.2 wheel fails to import on `python:3.12-slim` (`libexpat.so.1` missing) | Reproduced runtime defect | Dockerfile installs `libexpat1`; HTTP Debian mirrors returned 403 on this network, so apt uses HTTPS |
| Previous lock contained Windows-only `colorama`/`tzdata` and a different `cryptography` wheel | Resolver-host artifact | Lock regenerated inside the target image |
| `InstancedMesh` culled vegetation forever after a 0-instance first stage | Reproduced rendering defect | `frustumCulled = false` on per-stage instanced meshes |
| MindAR reports every camera failure as `VIDEO_FAIL` | Integration limitation | Permission preflight classifies `NotAllowedError` before MindAR starts |
| dB round-trip oracle overflowed at float max (`1.79769313e+308`) | Test-oracle defect | Log-domain oracle; minimized case kept as regression |
| GIS mutators crashed after `null_props` / `point_geom` | Test-harness defect | Destructive mutations ordered last; null-properties regression added |
| `vm`-context arrays fail strict `deepEqual` | Test-harness defect | Length-based assertion |
| Actual Gemini calls returned HTTP 400 for the scene schema | Reproduced integration defect (found by real inference) | Annotation stripping removed the property named `title` (unsatisfiable `required`); bisection showed `gemini-3.8-flash` rejects `minItems`/`maxItems`. The sent schema keeps property names and omits array-length keywords; Pydantic still enforces lengths. Regressions added |
| npm reported `@playwright/test@1.65.1` as non-existent | Network artifact, not a stack defect | Debug log shows `ECONNRESET` to registry.npmjs.org and stale cache; jsDelivr lists 1.65.1. Local QA used Playwright 1.64.1 (npx cache) and fast-check 4.10.2 from jsDelivr's ESM build. Re-run `npm install` on an unrestricted network |

## Blocked gates and the exact inputs needed

1. **Real GCOV (RZ-03):** `EARTHDATA_USERNAME` and `EARTHDATA_PASSWORD` in `.env` (an Earthdata Login account), then **Search NISAR catalog → Download & process** in the UI. Downloads are restricted to `https://nisar.asf.earthdatacloud.nasa.gov/NISAR/` `.h5` granules and reused once complete. Alternatively place a downloaded `.h5` in `data/` and call `POST /api/sar/process` with its relative path. Prefer a `DHDH` granule (HH+HV); `SHSH` granules are single-pol.
2. **Physical-device AR (RZ-07):** a printed target and a webcam (localhost) or an Android phone reaching the server over HTTPS (for example `uvicorn --ssl-keyfile/--ssl-certfile` with a locally trusted certificate).
3. **Science:** DEM-derived slope, surveyed boundaries, specialist species/density values and field references; none is claimed.

## Known limitations

- No DEM is ingested: the AR terrain is a flat reference plane and slopes are placeholders unless imported.
- The GCOV `mask` semantics (0 and 255 invalid) follow the product layout used by the reader and must be rechecked against a real product.
- Tailwind runs from the development browser CDN; compile CSS before any production delivery. CDN asset hashes are not yet pinned with SRI.
- SQLite and the single-host queue are pilot choices; see the stack document for the graduation path.
