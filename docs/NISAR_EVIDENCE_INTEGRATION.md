# NISAR evidence integration: current state and required delivery

> Current baseline — November 15, 2026 (Lima): **Ayumi** is the locally runnable product. > Work is limited to small residential–ravine/mountain screening windows around Canchaque, El Faique and Huancabamba; the whole Piura department and Tumbes are not offered. > Windows are locators, not official hazard boundaries or planting approvals. See [current implementation status](IMPLEMENTATION_STATUS.md) and [ADR 0006](decisions/0006-ayumi-bounded-workflow-and-municipal-report.md).

Date: November 15, 2026. Status: code/runtime audit and implementation handoff; the missing scientific workflow is not implemented by this document. This gate is mandatory under the owner's clarification and belongs alongside performance work, before claiming an end-to-end NISAR-informed planting decision.

## Product requirement

NISAR observations must provide analytical evidence for detecting and comparing surface-water/ponding areas, showing the underlying radar image and defensible measurements, and identifying sites for field evaluation of planting with at most three low-maintenance plant types. Displaying radar imagery alone does not satisfy that requirement. Neither a static basemap nor an AI-generated planting scene establishes that the selected sites were derived from NISAR.

## What the platform actually uses

| Component | Current input and code | Verified scope / gap |
| --- | --- | --- |
| Streets, buildings and land cover | OpenFreeMap vector tiles, [map.js](../app/map.js) | Conventional geographic context, not reconstructed from NISAR |
| Elevation and slope | Copernicus DEM, [terrain.py](../raiz_sar/terrain.py) | Terrain context, separate from radar measurements |
| NISAR image overlay | NASA GIBS NISAR GCOV false-colour rendering, [map.js](../app/map.js) | Real radar visualization on available dates; rendered colours are not numeric GCOV samples or a water classifier |
| Acquisition discovery | ASF catalog through [sources.py](../raiz_sar/sources.py) and [discovery.py](../raiz_sar/sar/discovery.py) | Lists candidate observations; does not establish a water detection or complete pixel coverage |
| Current water polygons | DSWx-HLS via GIBS, ponding_sites in [sources.py](../raiz_sar/sources.py) | Extracts open/partial-water classes from an optical water rendering. These polygons are not NISAR-derived |
| Numeric radar processing | [pipeline.py](../raiz_sar/sar/pipeline.py), [gcov.py](../raiz_sar/sar/gcov.py), SAR job in [tasks.py](../raiz_sar/tasks.py) | Supports a GCOV file, windowed arrays, dB outputs, previews, zonal statistics and manifests; no GCOV water-classification step exists |
| Visible evidence panel | [panels.js](../app/panels.js) | Shows slope/catalog information and a backscatter explanation; does not complete the raw-GCOV metrics-to-candidate workflow |
| Planting allocation | [planning.py](../raiz_sar/planning.py), [plans.py](../raiz_sar/plans.py) | Uses exclusions, known slope, area, candidate species, budget and assumptions. Does not require a NISAR water-evidence result |
| AI and AR | [scene.py](../raiz_sar/scene.py), [tasks.py](../raiz_sar/tasks.py) | AI context contains funded zones, slope, quantities and assumptions. An available version-matched radar preview may be attached to the scene, but that overlay does not make candidate selection NISAR-driven |

Read-only runtime check: GET /api/evidence/lower-piura-sechura returned two manifests, both data_mode=synthetic_fixture, with granule IDs SYNTHETIC_FIXTURE_GCOV_lower-piura-sechura_baseline and SYNTHETIC_FIXTURE_GCOV_lower-piura-sechura_post_rainfall. Their January/March dates are fixture values, not proof of real local NISAR acquisitions. No real processed NISAR manifest for Piura was present in that response. This does not deny the separate live GIBS radar display or the availability of files in external catalogs.

## What the challenge resources contribute

The [official Resources tab](https://www.spaceappschallenge.org/2026/challenges/dancing-with-the-sars/?tab=resources) was read in the existing browser after automated web readers failed:

- Earthdata Search and ASF Vertex: discover and obtain data; the platform already uses ASF discovery APIs.
- NISAR Data User Guide: product/access/processing documentation.
- Remote-sensing/SAR introductions and ARSET: methodological training.
- NISAR StoryMaps and application white papers: application examples and interpretation.
- UAVSAR postcards: airborne-radar examples, not NISAR observations of the selected Peruvian sites.
- Partner RCM, RADARSAT-1, SAOCOM and a CSA tutorial: separate missions or learning material. They must retain their own identity and cannot silently replace required NISAR evidence.

A resources list is not a single imagery feed, and referencing a tutorial does not mean its algorithm or data are integrated.

## Required observation-to-planting workflow

1. Discover actual NISAR coverage for a selected priority area and choose an event/time window with useful observations. Record product IDs, acquisition times, maturity/version, polarization, orbit/track, normalization, grid and quality. Do not invent a rainy-season pair if none exists locally.
2. Obtain appropriate real GCOV inputs through the existing authorized server-side path or a supplied local file. Compare compatible observations and validate product-specific masking/metadata against those files. A GCOV mask is not itself a water-detection map.
3. Generate geographically registered radar images and the actual numeric arrays. Keep GIBS browse imagery separate from the scientific raster used for measurements.
4. Implement and document a surface-water/ponding detection and change method. Evaluate local reference observations and failure cases: smooth dry soil, radar shadow, urban scattering, vegetation, partial coverage and mixed pixels. A dark-pixel threshold alone is not an established local water detector.
5. Publish a versioned water-evidence artifact containing masks/polygons, per-date coverage, area and uncertainty/validation metadata. Distinguish newly observed water, persistent water and unknown pixels; observation-to-observation persistence is not continuous monitoring.
6. Create candidate planting-assessment areas linked to that artifact. Consider appropriate margins or terrain near temporary water; permanent water, active channels, protected habitats and unsuitable salinity/drainage require exclusion or specialist review. Water presence does not itself approve planting.
7. Require that evidence reference in the NISAR-informed plan mode. If evidence is missing or incompatible, show a blocked/field-review state. Keep an explicitly labelled demo/manual planning mode if needed. Invalidate dependent metrics, plan and scene when the observation or boundary changes.
8. Show the original radar image, water/change overlay and numeric evidence on the map and zone card. Pass the same evidence/plan versions to 3D, AR and the printable draft. AI may explain or arrange the planting scenario; measurements come from the data pipeline.

## Measurements to display

| Measurement | Unit / derivation | Current status |
| --- | --- | --- |
| Radar backscatter by available polarization | gamma0 or verified convention, usually presented in dB; polygon median and p10/p90 | Backend support; real local processing/UI linkage still to verify |
| Valid pixels and valid coverage | Pixel count and percentage of the requested area actually observed | Backend support; preserve unknown rather than interpreting it as dry |
| Change in backscatter | dB difference between comparable real observations | Required; not a named current pipeline output |
| Water extent | m²/ha from a documented NISAR-derived water classification | Missing NISAR classifier; existing HLS-derived polygons are a separate input |
| Newly observed/receded water | m²/ha change, excluding unknown coverage | Required after classifier and comparable dates |
| Repeated water detections | Number/fraction of valid observation dates classified as water | Required; not exact hours/days of water retention |
| Data identity and scale | Dates, product IDs, processing version, channel, grid spacing, CRS | Required beside every image/metric |
| Classification reliability | Reference-based validation metrics and known limitations | Not an arbitrary confidence percentage or a transferred accuracy from another region |

The [ASF GCOV guide](https://nisar-docs.asf.alaska.edu/gcov/) describes calibrated, terrain-corrected backscatter and acquisition-dependent polarizations/grid spacing. Check the selected product: commonly cited 10/20 m grid spacing is not a guarantee of resolving individual small puddles. RVI is channel-dependent and is not a universal water or root-reinforcement metric.

NISAR imagery alone does not provide planting suitability, fertilizer requirements, exact water depth/volume, fertility, tree survival or root resistance. Retain those as unknown, separately measured or explicitly assumed. Depth used to extrude a water surface in 3D is illustrative unless independently measured.

## Complementary water products and present availability limits

[JPL's DSWx suite](https://www.jpl.nasa.gov/go/opera/products/dswx-product-suite/) distinguishes HLS optical water from products based on Sentinel-1 and NISAR. Its NISAR section still says under development, while the [product table](https://www.jpl.nasa.gov/go/opera/products/) lists a June 2026 schedule. Those statements are not verification of a usable DSWx-NI product over Piura/Tumbes. Investigate catalog/files/quality before selecting that route. No data-source migration is selected here.

[ASF availability](https://nisar-docs.asf.alaska.edu/availability-overview/) distinguishes validated L0–L2 products from still-unvalidated Level-3 soil-moisture products. A validated input product does not validate a new local water classifier or a planting recommendation.

## Performance contract

Preserve the fast conventional initial map and optional overlays. Process selected observations once in existing workers, crop numerical analysis to the area of interest, and publish cached tiles/previews plus compact metric manifests. The browser should fetch only the selected date/extent; it must not download/process whole HDF5 granules on every load. Missing analytical evidence must remain visible as an unresolved state while ordinary map navigation works.

## Acceptance and handoff priority

This is a required scientific gate alongside [the performance plan](PERFORMANCE_AUDIT.md), not an optional visual enhancement:

- Demonstrate at least one real local NISAR scene, then a comparable pair/time series where available, with reproducible source/version evidence.
- Show a traceable radar image → water/change result → measurements → assessment candidate → plan → 3D/AR path for the same zone and versions.
- Withhold unsupported metrics and claims. Independent local references must support any classifier accuracy claim.
- Verify that removing or changing NISAR evidence blocks or invalidates the NISAR-informed recommendation; a decorative radar toggle is insufficient.
- Run contract-derived property tests and bounded fuzzing for executable changes, plus a real-file scientific integration check and pixel/interaction checks. Synthetic tests alone cannot pass the real-data gate.

This clarification changes documentation only. No scene download, new water algorithm, new dependency, actual inference or scientific validation was performed in this clarification turn.

## Owner acceptance update — visible growth, ravines, exclusions and urban fidelity

Date: November 15, 2026. Status: mandatory pending requirements. The owner reports that tree growth in 3D, the huayco visualizations and the video experience are not functioning in the actual workflow. These reports reopen end-to-end acceptance. Earlier source counts, screenshots or successful codec probes do not establish that the user can complete the experience. This documentation update does not claim to have reproduced or fixed every reported defect.

### Required experience and acceptance evidence

| ID | Requirement | Evidence required before marking it complete |
| --- | --- | --- |
| NV-01 | Working 3D trees and huayco views | Open the real user flow for an approved zone; visibly render trees, water and the moving debris front in the intended location. Record actual UI interactions. Source feature counts and a non-empty file alone cannot pass |
| NV-02 | Growth and event arrival on the timeskip | Play, pause, scrub, change speed and restart one coherent timeline. Tree geometry visibly develops with age; in at least one view the huayco arrives after the selected establishment stage. Repeat seeks reproduce the same state |
| NV-03 | Ravine-constrained event start with an explanation | A supported ravine location is accepted. A known non-ravine location is rejected before playback/job creation. Missing evidence is a distinct unresolved state and also blocks playback. The interface explains the reason and highlights eligible corridors |
| NV-04 | No planting collisions with human infrastructure | The entire required planting/maintenance clearance and tree envelope avoids roads, houses/buildings and mapped pedestrian circulation in the map, all timeline stages, AR, exported scenes and proposed seed-deposition locations. Validate on the server as well as in the browser |
| NV-05 | Reliable NISAR-derived water evidence | Real local radar inputs, source image, documented classifier, dated water polygons/metrics and independent reference checks. False water, missed water and unknown coverage are measured and visible; tiny unresolved puddles are not invented |
| NV-06 | Real geographic geometry with textures | Existing parks, building footprints and roads match approved references. Parks have a visible surface, vegetation and paths; road/water surfaces have aligned materials. Missing buildings are corrected from evidence, and false buildings are removed |
| NV-07 | Performance and feature parity | The added geometry/materials load in spatial/detail chunks when needed. Recheck the existing startup and target-device frame-rate budgets, layer controls, 2D/3D/AR alignment, timeline and complete exported clip duration |

### 1. Build a coherent timeskip rather than disconnected snapshots

Use a single versioned scene state shared by 3D, AR and video. Keep plant age (months/years) separate from event elapsed time (seconds), with a declared mapping to the playback clock. The before/after comparison must use the same zone, camera framing, evidence date, terrain and approved intervention inputs.

- Month zero depicts seeds/capsules; subsequent stages show seedlings, trunk/crown development and establishment. A timeskip changes visible geometry, not only the selected label or a number of dots.
- Define per-species geometry/material parameters for the maximum three selected types. Interpolate a supported growth curve; if it is illustrative, label it. Mature trees must not silently appear at an unsupported twelve-month age.
- At least one continuous view must show growth followed by the huayco entering along the permitted ravine. Preserve versions and assumptions while switching between with-intervention and without-intervention views.
- Any visible resistance, bending, flow deflection or stopping is an explicitly declared scenario assumption unless a separately validated physical model supports it. Do not force the terrain path through trees or guarantee that planting stops the event.
- Pause and scrubbing must freeze/reconstruct both trees and flow. Restart, rapid view changes, area/plan changes and cancellation must not leave stale animations, off-screen content or multiple render loops.
- Keep the earlier English UI terminology requirement: use growth, timeline, before/after and scenario views rather than the previously prohibited simulation terminology.

For exported video, decode all four actual clips, inspect early/middle/late frames and verify visible tree growth, event arrival/movement, correct location, labels and attribution. Duration must match the selected timeline within a documented export tolerance; frame dropping must not shorten or accelerate the story. A codec sample or file-size threshold does not close this gate. Record real-time duration, frame timestamps, dropped ticks and hardware/software rendering conditions. Physical-device AR remains a separate required check.

### 2. Reject unsupported huayco start locations and explain why

Maintain a versioned ravine/corridor dataset with geometry, source, date, scale, coverage, quality and review status. Link relevant NISAR observations and water/change evidence to that dataset, with terrain-derived drainage and suitable hydrographic/hazard or field references supporting the channel location. A DEM downhill trace alone does not prove that a point belongs to a quebrada, and a radar image does not automatically provide a precise ravine boundary.

Use three explicit decisions:

| Decision | Behaviour | Example English message |
| --- | --- | --- |
| Supported ravine corridor | Permit the start; show the matched corridor and evidence | Start point accepted in the mapped ravine corridor. |
| Known location outside supported corridors | Reject the start and keep Play/Record disabled for the event | This point is outside a mapped ravine. Choose a highlighted corridor. |
| Unavailable, stale, too coarse or conflicting evidence | Reject automatic playback pending verification; do not label it definitively not a ravine | Ravine evidence is insufficient here. Verify the location before starting the view. |

Perform the same spatial/version check in the API before expensive processing and when restoring a saved scene. A client-side warning cannot be bypassed by submitting coordinates directly. Do not silently snap the selected point elsewhere; offer an eligible location and require explicit selection. Set any geometric tolerance from the source scale and reviewed corridor width, not an arbitrary pixel distance.

### 3. Keep planting out of roads, buildings and pedestrian space

Create one exclusion dataset used by candidate selection, point placement, AI validation, timeline growth, AR, recording and drone seed-deposition planning. Include road surfaces/right-of-way where available, building/house footprints, sidewalks, paths, crossings, accessible routes, plazas/circulation areas and other mapped no-planting constraints. Existing park planting beds may be eligible; park walkways remain circulation space. Unmapped ground is not automatically an approved planting location.

The owner's requested NISAR involvement is retained as evidence for water/change and broad context, combined with appropriate detailed mapping. Street-level house/path boundaries and clearance cannot be guaranteed from NISAR alone. Use reviewed cadastral/municipal or other suitably detailed licensed vectors/imagery and field corrections where needed, with provenance. Missing road width or uncertain footprints must not be converted into a zero-width obstacle or a claim of safe clearance.

Validate more than the tree centre point: check the required seed-placement, trunk, crown and reviewed maintenance/root-clearance envelope across the applicable growth stages, using a metric CRS and documented margins. Do not imply that an illustrative root shape establishes an engineering clearance. Unknown constraints require field review. Reject a conflicting placement with the feature/reason highlighted; an empty eligible area yields an explained infeasible result rather than forced planting.

AI output cannot override these exclusions. Validate final geometry after terrain projection, scaling and asset transforms, and revalidate after any infrastructure, evidence, species, boundary or plan-version change. Required property tests include generated placements/stages on obstacle boundaries, overlapping exclusions, holes, coordinate transforms, malformed geometry and unknown coverage.

### 4. Make NISAR water detection a measured quality gate

The water classifier must produce georeferenced masks/polygons and measurements from actual selected NISAR observations. Match the scene and source-image extent, date and quality; distinguish observed water, newly detected/receded water, persistent water and unknown areas. Keep HLS or other supporting references labelled by their actual mission/product.

Evaluate held-out local examples with independently timed reference imagery or field observations. Report precision, recall and spatial overlap where appropriate, alongside coverage and reference uncertainty. Agree suitability thresholds before accepting the detector rather than choosing only favourable screenshots. Include smooth bare soil, radar shadow, urban/vegetated areas, mixed pixels, no-data and tiny water patches in the failure set. Retain low-quality cases as unresolved rather than falsely dry or water.

Use the selected product's actual spatial support: the [ASF GCOV guide](https://nisar-docs.asf.alaska.edu/gcov/) describes acquisition-dependent grid spacing and channels. It does not establish that individual small puddles, footpaths, houses or detailed ravine edges can all be resolved. Additional detailed data can refine boundaries while preserving the essential NISAR analytical contribution. Water extent does not itself establish fertility, usable depth, plant suitability or a protection benefit.

### 5. Build an accurate textured place, including parks and roads

- Audit footprint alignment, source dates, coverage, CRS, scale and terrain placement against approved reference areas in Sechura, Piura, Paita, Sullana and Talara, then Tumbes. Treat reports of buildings in empty places and missing buildings as geographic defects to reproduce; do not increase density by inventing structures.
- Derive building position/outline from evidence. Heights, roof shapes and facade materials must retain measured versus illustrative status. Include every approved reference footprint at the required detail level; measure omissions and false additions. Unknown areas remain visibly incomplete until corrected.
- Represent existing parks with actual georeferenced area geometry, terrain-conforming grass/soil surfaces, vegetation and mapped paths. Preserve walkways, entrances and access. New proposed planting is a separate plan layer; decorative assets must not masquerade as surveyed objects.
- Give road surfaces and relevant markings a visible aligned texture/material in 2D and 3D. When a water layer overlaps a road, preserve readable road context with a deliberate material/opacity or context-outline control. Surface visibility must not imply the road is safe to use.
- Use appropriate textures/materials for soil, park vegetation, roads, buildings, water and debris rather than relying on solid colour alone. Shared texture coordinates, geometry and legends must agree across 2D, 3D and AR. A generic texture is a display material, not additional observed detail or a sharper satellite measurement.
- Keep observed water extent separate from illustrative water thickness, reflections, ripples and flow animation. Textures must not hide missing coverage or create unsupported depth values.
- Use instancing, shared materials/textures, bounded texture sizes, levels of detail and visible-area chunks. Load assets for the requested neighbourhood/view; retain the conventional fast map and optional analytical layers. No new rendering library or asset provider is selected by this document.

### Ordered delivery and required proof

1. Reproduce the owner's complete failing flow on a declared browser/device, preserving screenshots, console/performance logs and complete clips. Record all NV gates as pending until this workflow succeeds.
2. Establish the real NISAR water-evidence result and the supported ravine/infrastructure/exclusion datasets for one reference neighbourhood. Extend coverage to all required priority areas; do not label the first neighbourhood as the whole-region completion.
3. Make rejection messages, candidate feasibility and collision checks work consistently in the server and UI before generating richer planting assets.
4. Implement the shared growth/event clock and visibly render the three species types, water and huayco along the approved corridor. Confirm the actual camera and pixels, including a positive and a rejected start location.
5. Correct geographic building/park/road defects and add textured geometry under the loading/render budgets. Compare 2D, 3D and AR against the same approved reference snapshots.
6. Decode and inspect all four full videos and run target-device AR interaction checks, including denied camera access and tracking loss. Verify timelines, exclusions, version invalidation, cancellation, unsupported hardware and no-data states.
7. Re-run contract-derived property tests, bounded malformed-input fuzzing, geographic reference checks and performance measurements. Report configured versus executed cases, scientific validation limits, failures and remaining coverage gaps. No feature is accepted solely because an object was added to a data source or a button exists.

These are planning/acceptance additions only. No application fix, new classifier, asset reconstruction, video repair or new functional-test result is claimed by this update.
