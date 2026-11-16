# ADR 0006 — Ayumi, local screening windows and bounded workflow work

**Decision:** implemented locally, November 15, 2026 (Lima). This supersedes regional navigation and persistent territorial controls in ADR 0005, the broad Piura/Tumbes locators in ADRs 0002/0003 and queued-only report delivery. Existing protocol IDs, source histories, AI/AR requirements and scientific gates remain.

## Problem and constraints

The owner reported inconsistent latency, a slow territorial plan, overflowing steps, a bulky legend and permanently intrusive Piura controls. The product must be named Ayumi, use only residential interfaces near ravines/mountains in Piura, allow image texture removal and produce a comprehensive municipal-review report. Preserve the single `index.html` entry, pinned runtime, real AR and server-side AI credentials; add no dependency without a demonstrated need. Product speed must not be inferred from map loading alone.

## Reconnaissance and alternatives

| Alternative | Evaluation |
| --- | --- |
| Keep the full-region renderer and existing sampling unchanged | Lowest code change; retains unnecessary scope and unbounded grid/route work. Does not satisfy the owner. |
| Retain MapLibre 5.24.1 / native WebGL2; restrict local work and bound CPU work | Selected. Reuses one graphics context and existing data pipelines; no package/license change. Requires explicit scope/cache and DOM lifecycle tests. |
| Replace the frontend with Cesium, a second three.js scene or a new terrain engine | New memory/context/dependency, conversion and regression costs. Does not resolve deposition sampling or report queues. No measured requirement justifies migration. |
| Always lower graphics resolution and vector LOD | Rejected as a universal default. The preceding hardware experiment worsened tail latency; quality changes remain explicit, with a separate software profile. |
| Require AI for every municipal report | Keeps external latency, quota and queue dependence for deterministic calculations. Retain optional narrative API, but make the complete numeric/source draft local. |

Hard constraints take precedence over an artificial weighted score: scope correctness, source fidelity, usable panel height and credential isolation are required; the selected option minimizes migration/maintenance cost while addressing measured CPU work.

## Implementation

- Offer three approximately 0.03° × 0.03° screening windows around Canchaque, El Faique and Huancabamba. Restrict map navigation to the selected locality; use the union for zone/import/plan checks and terrain/building tile intersection. Tile edges may overlap a window. These are **not** official hazard polygons or cadastral boundaries.
- IGP El Faique and INGEMMET Canchaque/critical-zone publications support the locality context. Residential adjacency, channel/runout extent and planting suitability still require detailed sources and field checks. Dry-forest candidates are not presumed appropriate at Andean elevations.
- Replace the floating legend rectangle with small chips and an explicit source dialog. Keep 3D settings in an on-demand dialog. Partition steps by available panel height; oversized cards open explicitly in detail dialogs, where scrolling is permitted.
- Keep DEM tile size 256 and source maximum zoom 12. Three detail bands use zoom hysteresis; progressively admit trees at usable local elevations, retain withheld water effects until source readiness and preserve software static-weather behavior.
- Bound grid candidates and deposition nodes; incrementally update route length, verify each closed sortie independently, conserve capsule counts and reject previews over 6,000 visits with an explicit phasing message. Bump the plan engine identity to `plan-engine-2`.
- Reuse saved manual plans after dataset integrity checks. Revalidate NISAR-bound evidence rather than shortcutting it. Cache successful terrain aggregates (128 entries) and infrastructure aggregates (64 entries, 15-minute buckets); return copies and retry unavailable sources. Fetch independent road/park and building mapping concurrently with two workers.
- Add a deterministic `/api/reports/preview` endpoint. Preserve the scene/plan version check. Municipal content includes union area, resources, exact cent totals, assumptions/formula, species opportunities, unpriced costs, implementation gates, risk ownership and source URLs.
- Image controls hide analytical rasters and can omit the AR snapshot; camera AR also allows hiding an existing ground texture without restarting tracking. Evidence visibility remains a separate control.

## Evidence and limits

See [AYUMI_DELIVERY.md](../AYUMI_DELIVERY.md) for actual measurements, generated properties, browser checks and open gates. The isolated 1,000 ha deposition workload improved from a 1,174.613 ms median to 65.617 ms across three repetitions. That does not establish an equivalent end-to-end improvement or network-independent latency. Prior regional/software measurements are historical baselines with a different scope.

Technical references checked November 15/16, 2026: [MapLibre map API](https://maplibre.org/maplibre-gl-js/docs/API/classes/Map/), [raster DEM source specification](https://maplibre.org/maplibre-style-spec/sources/#raster-dem), [native dialogs](https://developer.mozilla.org/en-US/docs/Web/HTML/Element/dialog), and [Python bounded thread pools](https://docs.python.org/3.12/library/concurrent.futures.html). Browser behavior is verified against the pinned local runtime; current documentation alone does not prove that every new API exists in 5.24.1.

Official context and budget/plant sources are linked in [the municipal method](../MUNICIPAL_REPORT.md). OSCE 040-2021 is used for historical cost arithmetic, not current procurement-law advice. No official unit tariff, quantified local benefit, universal huaico prevention, instant root establishment or S-band-over-Peru claim is introduced.

## Deployment, rollback and review triggers

The owner separately approved including the concurrently prepared deployment/DNS/arm64 configuration. See [deployment status](../DEPLOYMENT.md); committed configuration is distinct from provisioned cloud resources, secrets, DNS and a healthy live site. This change does not execute the DNS script or provision a VM.

Rollback uses new forward commits, one path each, preserving history and persisted data. Cached old plans remain versioned; a new request produces engine-2 identity. Historical rasters and research are preserved, not deleted. Revisit the decision after new official risk polygons, ecological approval, changed source releases, sustained target-device traces, memory growth, security/support changes or measured resource limits. Do not increase detail merely because smaller windows make it possible.
