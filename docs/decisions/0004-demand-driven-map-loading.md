# ADR 0004 — Demand-driven map loading and regional delivery roadmap

> Historical decision record. [ADR 0006](0006-ayumi-bounded-workflow-and-municipal-report.md) supersedes regional navigation, persistent settings, report delivery and sampling policy where they differ. The current public name is Ayumi; original decisions and their evidence are retained below.

- Date: November 15, 2026.
- Status: implementation tuning accepted within the owner's explicit performance-fix request. Regional packaging and richer mesh assets remain proposed follow-up work, subject to feasibility evidence.
- Amends ADR 0002 and ADR 0003. No new runtime dependency, renderer migration, public deployment or paid service is selected here.

## Problem and constraints

The owner prioritizes iteration speed, a conventional map by default, individually controllable analytical overlays, Piura/Tumbes scope, and richer 3D/AR in Sechura, Piura, Paita, Sullana and Talara. Exact observation provenance, mandatory actual AR and AI-assisted future construction remain requirements. The latest planting purpose includes strategic ponding sites and at most three low-maintenance plant types.

The existing runtime is MapLibre GL JS 5.24.1, native ES modules, FastAPI/Python 3.12, RQ/Valkey, Copernicus DEM and GIBS imagery, with MindAR 1.2.5/A-Frame 1.6.0 loaded for AR. Startup was doing DEM generation, multiple coverage searches and automatic radar activation before any user selection. See the measured route/browser evidence in PERFORMANCE_AUDIT.md.

## Alternatives

| Alternative | Performance and functionality | Ecosystem and adoption cost | Outcome |
| --- | --- | --- | --- |
| Keep eager layers and warm every city | Preserves visuals but requests data the user may never view; cold warmup competes with reads | No migration; extra bandwidth, storage and restart work | Retain callable warmup, disable it by default |
| Existing renderer with demand loading | Spatial tiling already exists; defer DEM, catalogs and heavy tools; preserve buildings, terrain and AR | No new dependency/license surface; small auditable loader/state changes | Implemented and measured |
| Regional local XYZ vector and DEM tiles | Predictable local delivery; cache only needed spatial/detail chunks | Build/update pipeline, disk budget, provenance and source redistribution terms; no new browser protocol required | Preferred first packaging experiment |
| Regional PMTiles archive | Range-based regional file access, fewer serving components and portable archives | Additional browser protocol/CLI dependency, HTTP Range/CORS/cache tests; style/layer-schema compatibility needs verification | Proposed comparator; no archive downloaded or protocol installed |
| One regional GeoJSON or flattened image | Easy initial packaging | GeoJSON grows in parsing/render cost; a flat image loses building geometry, zoom detail and interaction | Rejected as the primary map |
| Replace MapLibre with a globe/photoreal engine | May support specialized 3D content | New engine, bundles, GPU/device work, integration rewrite and attribution/data costs; no evidence that it fixes the observed startup chain | Deferred; require a failed measured requirement first |

## Primary evidence and feasibility

Consulted November 15, 2026:

- [MapLibre large-data guidance](https://maplibre.org/maplibre-gl-js/docs/guides/large-data/) documents simplification/tiling and source tuning. It supports retaining spatial/detail chunks; it is not a benchmark of this application.
- [OpenFreeMap quick start](https://openfreemap.org/quick_start/) documents the Liberty style and public/self-hosted options. Hosted delivery still depends on the network. Source/asset terms and attribution must be retained for a redistributed regional package.
- [Protomaps extraction guide](https://docs.protomaps.com/guide/getting-started) documents bbox extraction and maximum-zoom limits. This establishes that extraction is available, not its size, speed or schema compatibility for this region.
- [MapLibre custom layers](https://maplibre.org/maplibre-gl-js/docs/API/interfaces/CustomLayerInterface/) supports adding graphics in the map's GL context. Current documentation/examples target newer releases; do not copy newer terrain hooks into pinned 5.24.1 without a compatibility prototype.

Local feasibility: three baseline cold-browser/warm-server runs had median first idle 20.727 s; three final runs with demand loading had median 5.568 s, with zero default DEM/GIBS/catalog requests. Six-city navigation, 3D enablement and building colours were exercised in Chromium. These measurements justify the implemented policy. Regional file size, offline performance, exact tree assets and target-device frame rate are not measured yet.

## Decision and trade-offs

Keep the existing renderer and infrastructure. Start with the coloured vector basemap. Load one explicitly requested analytical layer/date, terrain only for shading/3D, drawing only on Zones, and charts only with data. Dedupe in-flight work and reject results from obsolete inputs. Use existing native caches, not whole-region eager loading.

Security/maintenance: backend credentials remain server-only; new browser telemetry has bounded fields and finite durations. Lazy script loading uses pinned, code-defined URLs. This work is not a dependency vulnerability audit. Performance/scalability: less startup work is measured; server-wide upstream concurrency and cold evidence jobs still need explicit capacity limits. Cost/portability: no new paid service or framework; the existing provider/network dependencies remain. Ergonomics/complexity: logs now correlate requests and browser sessions, but a small new loading module needs regression coverage.

For richer trees, first prototype three reusable instanced species assets, then compare procedural meshes and licensed glTF models under an explicit byte/triangle/FPS budget. Exact individual trees require field identity/dimensions or scans. AR currently has a textured terrain context: actual 3D building geometry is still needed. Keep future scenes and vegetation resistance illustrative unless separately validated.

## Adoption and rollback

Implemented changes preserve API contracts except for strict validation of optional telemetry. Older browser clients without a session ID retain a legacy default. All data layers remain available through explicit controls; no valid observations or GIS geometry are discarded. The source entry remains one index.html with native modules.

Rollback is file-based because there is no data migration: restore eager-loading calls/scripts if required, keeping evidence caches and original inputs intact. Do not rewrite unrelated working-tree changes. No commits were requested.

Next, benchmark local XYZ and regional PMTiles on the same source snapshot/extent/zoom/device, inspect redistribution terms, and record archive size, cold/warm delivery, offline fallback, memory and map/AR feature parity. Review after a measured p95 startup >5 s, cold evidence saturation, missing priority-area geometry, failed 30 fps target-device rendering, incompatible pinned APIs or changed source terms. Targets and phase gates are in PERFORMANCE_AUDIT.md.

## Video feasibility follow-up

Static-view exports reproduced empty WebM output in headless Chromium/SwiftShader despite copied map frames. The browser [recording specification](https://www.w3.org/TR/mediastream-recording/) requires collected data to be delivered before the stop event; checking an anchor download alone was inadequate QA. Capture now reports frame/chunk/byte diagnostics and rejects empty encodes. Robust browser export is still an open acceptance gate; a worker encoder is a proposed comparator, not an installed dependency.


Update (same day): the worker-encoder comparator was tested. WebCodecs `VideoEncoder` (VP8) produced frames where `MediaRecorder` produced none, so recording now uses WebCodecs with a built-in WebM muxer (`app/webm.js`, no new dependency) and falls back to `MediaRecorder`. Exports decode in Chromium (3/3); frame-rate on target hardware is still an open gate. Phase 3 evidence jobs (host-wide upstream slots, bounded retries, single flight, aged manifests, worker-built ponding) are recorded in PERFORMANCE_AUDIT.md.
