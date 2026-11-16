# RAÍZ-SAR AI — Scope and validation contract

Current scope follows the latest [solution source](SOURCE_CONTEXT.md), including the owner's four binding corrections. Prepared November 14, 2026. This is a specification and research setup, not an implemented application.

## Product outcome

Support an environmental/GIS specialist and a municipal planner evaluating vegetation establishment for erosion control and appropriate slope reinforcement, with NISAR-derived evidence where defensible, a transparent planting plan and **required AI-assisted future-state AR**. Avoid claims of universally preventing huaicos or instant reinforcement from newly dispersed seeds.

## Priorities and dependencies

| Priority | Required outcome | Dependency |
| --- | --- | --- |
| Core | Scenario selectors for Carabayllo and lower Piura/Sechura, evidence map, sector detail and discrete timeline | Verified locators/boundaries or labeled fixtures |
| Core | Candidate planting suitability and budget/establishment scenarios | Ecological/geotechnical eligibility, explicit assumptions and evidence quality |
| Core | Interactive AR linked to the selected geospatial sector | Declared supported device, registration, scale/datum and meaningful interaction |
| Core | Actual AI-assisted construction of a future planting scenario for AR | Model/inference path, schema validation, versioned plan and scene assembly |
| Core | Grounded printable planning draft and GIS-import contract | Provenance, report constraints and compatible normalized data |
| Extension | Drone seed/capsule deposition planning | Species/seed feasibility, payload, terrain, energy and authorized operational constraints |
| Later validation | Plant establishment and possible erosion/slope benefits | Independent field records and suitable long-term specialist evaluation |

AR remains core even when a fallback is provided. Drone planting is an extension with an explicitly defined seed-deposition purpose. A lack of field validation must downgrade claims, not erase the mandatory product requirements.

## Prototype packaging

The attached source asks for a single `index.html` frontend using HTML5, Tailwind CDN, Leaflet, Chart.js and icons. [The selected stack](TECHNOLOGY_STACK.md) now resolves the baseline: MindAR/A-Frame image-tracked AR, a Python API/worker pipeline, server-side structured Gemini generation and pinned dependency manifests. Verify implementation conflicts between file-based preview, network dependencies, HTTPS/camera requirements and actual AI access. Never expose a private provider key to satisfy a single-file constraint.

A fixture-only demo, a prototype with actual AI/AR integration and a maintainable production system are distinct delivery modes. A simulated inference response may support development but does not prove the actual AI requirement was completed. The stack definition and dependency-resolution snapshot are not an implemented application or runtime integration test.

## Canonical domain objects to investigate

`StudyArea`, `Sector`, `Observation`, `EvidenceLayer`, `FieldAssessment`, `SpeciesCandidate`, `PlantingPlan`, `BudgetScenario`, `DroneSeedingPlan`, `EstablishmentScenario`, `FutureSceneSpecification`, `ARSession` and `PlanningDraft`.

Every derived object needs input IDs/versions, applicable AOI, temporal context, units, method/parameter version, evidence class and uncertainty. Use separate evidence classes for `observed`, `derived`, `modeled`, `ai_generated`, `illustrative` and `unknown`; a derived/model result is only validated when an independent verification record supports that status.

## Acceptance criteria for later implementation

| ID | Criterion | Verification |
| --- | --- | --- |
| RZ-01 | New prevention-oriented identity and scope | Active UI/docs use RAÍZ-SAR AI and the corrected source |
| RZ-02 | Both scenario locations | Locator provenance; boundaries and data mode labeled |
| RZ-03 | Essential analytical NISAR contribution | Input IDs, band/polarization/quality and meaningful derived evidence; no logo-only integration |
| RZ-04 | Honest science | No unvalidated underground-depth, survival or root-stability claims; unknown values remain unknown |
| RZ-05 | Eligible planting plan | Exclusions before ranking; species/soil/terrain constraints and assumptions inspectable |
| RZ-06 | Consistent quantities and budget | Seeds/capsules, expected germination, established plants and costs remain distinct |
| RZ-07 | Required interactive AR | Recorded interaction on a declared supported device, with scale/registration checks |
| RZ-08 | AI future-state construction | Real inference trace or explicit blocked status, valid scenario schema, deterministic constraints and interactive AR scene |
| RZ-09 | Distinct present and future | Observation versus proposal versus generated scenario never visually conflated |
| RZ-10 | Correct drone extension | Seeds/capsules deposited; planned/ simulated route distinguished from executed flight |
| RZ-11 | Grounded report and printing | Draft label, source dates/units, limitations, no official-approval claim |
| RZ-12 | Compatible GIS import | Normalized English schema, geometry/unit checks and actionable errors |
| RZ-13 | Accessible English UX | Keyboard/text alternative, readable contrast, reduced motion and useful AR fallback |
| RZ-14 | Reproducible software assurance | Property tests, unusual inputs, shrinking/replay and bounded fuzzing for executable boundaries |

RZ-07 and RZ-08 are separate gates: a 3D viewer is not automatically AR; a deterministic vegetation placement routine is not automatically AI. Unavailable inference or unsupported hardware must appear as an unresolved gate, not a completed requirement.

## Science and ecological evidence gates

1. Verify an appropriate NISAR sequence over a proposed location, available channels, collection maturity and comparability. L-band availability does not prove S-band coverage over Peru.
2. Define what the SAR method can estimate and validate against appropriately timed independent measurements. GCOV backscatter is not a direct subsurface-water measurement.
3. Inspect DEM source, horizontal/vertical datum, slope derivation, hazards and field context. A slope percentage is not a geotechnical stability certification.
4. Verify candidate taxa, native range, establishment requirements and seed-based deployment suitability. Dry-forest restoration and slope-bioengineering cases need different assumptions.
5. Define monitoring for deposition, germination, establishment and maintenance. Root contribution develops over time and may be insufficient for the hazard mechanism.
6. Only estimate survival, carbon, erosion reduction or sediment effects with a documented model and evidence; otherwise provide clearly labeled sensitivity scenarios or no estimate.

## AI, AR and drone checks

- Ground AI input in the selected evidence/plan version; validate structured outputs, reject unsupported species/geometry and treat imported text as untrusted data.
- Keep scene construction constrained to approved sectors, terrain/datum, species assets and time assumptions. Root geometry and future vegetation are illustrative unless independently established.
- Handle denied camera/location permission, tracking loss, wrong marker, stale plan, unit/datum mismatch and device limits. Hide misleading field alignment when registration quality is insufficient.
- Enforce candidate drone routes within verified constraints; no-go areas and energy reserve precede distance optimization. If constraints are unknown, mark the plan incomplete. No actual flight or device actuation is authorized.

## Reproducibility and testing

For executable changes, property-based testing is mandatory. Target coordinate round-trips with justified tolerance; nonnegative budget/counts; no seed/tree conflation; candidate points within eligible areas; exclusion preservation; legal state transitions; stale-response rejection; scene/report/version consistency; and unknown evidence that cannot silently become high confidence.

Generate thousands of valid, invalid and boundary cases within explicit budgets, shrink failures and keep replay artifacts. Fuzz malformed GeoJSON, report/AI payloads and scene/import schemas in isolated bounded harnesses. No application/property tests or fuzzing are claimed for the current documentation-only work.

## Timebox and actual team

Plan a 48-hour vertical slice with an environmental engineer validating GIS/ecological assumptions, a systems engineer owning data/contracts/AI and a systems engineer owning map/UI/AR. Roles may be combined according to skills; make integration checkpoints explicit. Freeze evidence/plan/scene contracts early and test the AR hardware and AI path early rather than deferring both mandatory gates to the final hours.

## Revision — November 15, 2026 (ADR 0002)

Additional acceptance criteria for the map-first refactor:

| ID | Criterion | Verification |
| --- | --- | --- |
| RZ-15 | Compliant, keyless basemap | No request to `tile.openstreetmap.org`; OpenFreeMap attribution visible; failure state explained |
| RZ-16 | Legible dated optical context | HLS layer at its native maximum zoom; date chosen among days with pixels; resolution stated |
| RZ-17 | Real SAR on the map | NISAR GCOV and Sentinel-1 RTC imagery from GIBS with mission, date and "rendered imagery" label |
| RZ-18 | User zone delimitation | Draw, edit, delete vertices, close, validate (self-intersection, area, bounds), confirm; original and final geometry stored |
| RZ-19 | Assisted boundary is a proposal | Suggestion shown beside the user polygon with method, sources, IoU and area change; applied only on explicit acceptance |
| RZ-20 | Charts with real data or explicit unavailability | Rainfall (POWER), acquisition timeline (ASF catalog), DEM slope distribution, plan quantities; no placeholder series |
| RZ-21 | Coherent 2D/3D/AR terrain | One DEM source for slope, MapLibre terrain and the AR mesh; vertical exaggeration declared |
| RZ-22 | Guided, map-first UX | Step flow, contextual panel, onboarding, glossary, provenance on every layer; keyboard and 390 px layouts work |

## Revision — November 15, 2026 (ADR 0003)

| ID | Criterion | Verification |
| --- | --- | --- |
| RZ-23 | Ponding sites from observations | DSWx-HLS water polygons for the zone box and a rainy-season date; cloud reported as unknown; source and date shown |
| RZ-24 | At most three low-water species | Scenario has 1–3 species, all `water_need: low`, each with a 3D model |
| RZ-25 | 4–8 vertex zones | User picks the count before placing; API rejects drawn zones outside 4–8; suggestions simplified to ≤ 8 |
| RZ-26 | Before/after and huayco views | Four 3D views render data (water, trees, mud front); huayco path from the DEM; "with trees" assumption declared; video recording available |
| RZ-27 | Legend equals map colours | Every legend swatch is a colour painted by a visible 2D/3D layer |
| RZ-28 | Measured performance | Per-request and per-job timings in `perf.jsonl` and `Server-Timing`; browser marks; `tools/perf_report.py` summary recorded |
## Performance-first acceptance amendment (ADR 0004)

The current [audit and delivery plan](PERFORMANCE_AUDIT.md) supersedes eager radar/relief startup. Historical location selectors and flat-AR descriptions above are not current acceptance evidence.

| ID | Criterion | Verification |
| --- | --- | --- |
| RZ-29 | Conventional default map | Fresh browser loads streets/buildings/land cover with zero DEM, satellite-tile or catalog requests; analytical layers Off |
| RZ-30 | Demand loading and stale-response isolation | Only requested layer/date work; cancellation/deduplication properties; input changes cannot apply old-area results |
| RZ-31 | Priority-area detail within a speed budget | Regional-tile/asset experiment; cold/warm timings and memory/FPS on declared hardware; no flattened replacement for required 3D/AR |
| RZ-32 | Exactness is traceable | Individual trees need measured identity/dimensions or scans; procedural species models retain illustrative status; current AR map texture is not 3D building geometry |
| RZ-33 | Comparable four-view videos | Same camera, dates, plan version and terrain path; water/mud/vegetation parameters disclosed; recording cancellation and physical-device rendering verified |

RZ-29 and software portions of RZ-30 are verified in this increment. RZ-31 through RZ-33 remain partially implemented or pending as detailed in the audit; a screenshot or attractive illustration does not close those gates.

## NISAR water-evidence clarification

RZ-03 requires a traceable NISAR observation → water/change analysis → metrics → candidate assessment → plan/3D/AR path. The current optical DSWx-HLS polygons and a separate NISAR image overlay do not satisfy this gate. Actual local processed files, a documented detection method, references for validation and versioned links to the planting decision are required. See [NISAR_EVIDENCE_INTEGRATION.md](NISAR_EVIDENCE_INTEGRATION.md). Keep missing/low-quality evidence blocked or unknown, preserve the fast conventional map, and do not substitute an optical product under a NISAR label.

## Owner visual/spatial acceptance amendment — November 15, 2026

The owner-reported failures reopen end-to-end tree/huayco/video acceptance. The [integration plan](NISAR_EVIDENCE_INTEGRATION.md) defines the full NV-01–NV-07 work packages and delivery sequence. Additional required gates are:

| ID | Criterion | Required verification |
| --- | --- | --- |
| RZ-34 | Working visible 3D/tree/event flow | Recorded actual user interactions and visible content in the correct scene, not source counts alone |
| RZ-35 | Growth and event timeskip | Visible stage-appropriate geometry growth and huayco arrival; play/pause/scrub/restart determinism; plant age and event seconds distinguished |
| RZ-36 | Ravine start guard | Valid corridor accepted, known outside location rejected with a clear warning, insufficient evidence blocked with a different explanation; API enforcement and stale-version tests |
| RZ-37 | Infrastructure and pedestrian exclusions | Full required placement/clearance envelopes avoid roads, houses/buildings and mapped pedestrian circulation at applicable stages, after geometry transforms and in AR/video/seed-deposition plans |
| RZ-38 | NISAR water-detection quality | Actual local inputs, georeferenced source image/masks/metrics, independent reference evaluation of false/missed detections and unknown coverage; no invented sub-resolution puddles |
| RZ-39 | Correct textured urban context | Reference-based building footprint completeness/correctness, georeferenced park geometry and paths, textured roads/water, readable 2D context and consistent 3D/AR placement |
| RZ-40 | Complete video and performance evidence | All four clips decoded and inspected across their duration, visible growth/event movement, timestamps/duration consistent with the chosen timeline, target-device rendering and startup budget checks |

These gates are pending in this amendment. NISAR supports the water/change evidence; detailed infrastructure/corridor geometry needs appropriate supplementary sources and validation. Unknown exclusions do not establish planting clearance. A water overlay does not establish road passability. Tree/flow visuals retain their assumptions and do not establish protection efficacy. Documentation-only work here creates no new executed application-test or scientific-validation evidence.
