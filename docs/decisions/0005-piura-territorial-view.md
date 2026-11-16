# ADR 0005 — Integrate a bounded Piura territorial viewer into MapLibre

> Historical decision record. [ADR 0006](0006-ayumi-bounded-workflow-and-municipal-report.md) supersedes regional navigation, persistent settings, report delivery and sampling policy where they differ. The current public name is Ayumi; original decisions and their evidence are retained below.

- Status: accepted for this local implementation; geographic, device and performance acceptance remain separate.
- Owner request: the attached Piura 1:1 digital-twin specification; later explicit approval to use the available geospatial/research/QA skills instead of the three unavailable named skills.
- Research date: November 15, 2026, America/Lima.
- Scope: existing `index.html`, native ES modules, Python terrain pipeline. No publication, new paid service, dependency upgrade or replacement of AR/AI workflows.

## Problem and constraints

The existing viewer already uses MapLibre GL JS 5.24.1, OpenFreeMap, an Overture building proxy and Copernicus GLO-30 Terrarium tiles. Entering 3D forced zoom 14 even at a regional camera position. Building heights interpolated from zero with zoom. Elevation tint was inserted above mapped cover. These behaviours conflict with regional exploration and a default physical vertical scale of one. There was no compact territorial control or source-aware point inspection.

The requested viewer must preserve coordinates, use real elevation geometry, favour mountains and valleys, distinguish observations from procedural content and stream bounded detail. There is no surveyed regional DTM, complete tree inventory, measured channel cross sections or calibrated hydrodynamic model in this checkout. A 30 m DSM cannot supply those missing measurements.

## Alternatives and evidence

| Alternative | Documented capability and evidence | Decision consequence |
| --- | --- | --- |
| Retain the existing viewer without additions | Lowest migration cost, but the observed framing/height/material defects and missing controls persist | Rejected as insufficient for this request |
| Retain MapLibre and add native WebGL2 detail without a new package | [Custom layers](https://maplibre.org/maplibre-gl-js/docs/API/interfaces/CustomLayerInterface/) share the map camera and depth context; existing raster terrain already streams multiresolution geometry | Selected; no second map, rendering context, build system or terrain scheduler |
| CesiumJS | [Terrain documentation](https://cesium.com/learn/cesiumjs-learn/cesiumjs-terrain/) documents globe terrain, streaming and water effects, including self-provided heightmaps | Stronger globe/3D Tiles path, but replacing/coexisting with the map requires new terrain packaging, state/drawing/AR adapters and another dependency; no local comparative benchmark justifies migration now |
| Three.js | [Instanced geometry documentation](https://threejs.org/docs/) covers instancing and scene assembly | Useful if detailed glTF assets become available; the existing A-Frame bundle stays AR-only. Loading it just for a few bounded meshes would add unnecessary runtime surface |
| deck.gl | [TerrainLayer](https://deck.gl/docs/api-reference/geo-layers/terrain-layer) reconstructs meshes from tiled heightmaps and streams them on demand | Duplicates existing terrain responsibility; no measured benefit established for this workload |
| WebGPU, glTF/GLB and 3D Tiles | Future renderer/asset interfaces, not required just to stream the existing DSM | Deferred until verified assets or a measured WebGL limit justify them; no unsupported fallback claim |

Sources were inspected on the research date. General current MapLibre documentation differs from this pinned version: its custom-layer example uses a changed render signature. The pinned `src/style/style_layer/custom_style_layer.ts` and `src/geo/projection/projection_data.ts` were retrieved from jsDelivr inside the project container. The latter defines `defaultProjectionData.mainMatrix`; runtime testing caught and corrected an initial incorrect matrix-member assumption. Use the pinned source and runtime evidence when documentation disagrees.

## Decision and trade-offs

Keep the selected engine and Python libraries. Add four native modules: pure geographic contracts, a bounded shared-context WebGL2 layer, lifecycle/control integration, and a source-aware Python point/tile-plan module. Lazy-load all new browser modules only when 3D is requested. Keep ordinary 2D startup free of DEM requests.

Terrain uses MapLibre's native tile LOD, depth, normals, interpolation and seams. The default vertical multiplier remains one. Buildings use full mapped/default metre heights once their detail tier is visible, rather than shrinking with zoom. Land-cover and water polygons remain above DEM tint/shading. No procedural channel is cut into the DSM to create fictitious detail.

Bound procedural trees by visible forest/park polygons, full crown clearance from loaded mapped infrastructure/water, candidate/vertex/feature/instance budgets and zoom tiers. These are illustrative trees, not a planting plan or real tree inventory. Waterway ripples use per-segment downstream orientation from the DSM when the height difference supports a direction; flat segments have standing ripples. Width defaults and the small rendering offset are visual choices, not channel/depth measurements.

WebGL2 detail has at most three draw calls (instanced vegetation, batched waterway strips, bounded-opacity visual rain) and explicitly releases buffers, programs and vertex arrays. Hardware animation is opt-in, respects reduced motion and stops while the document is hidden. Repeated software-renderer stalls justified a detected-software fallback with half resolution and static weather. This does not establish regional performance or acceptance of the separate mandatory physical AR gate.

The no-dependency choice reduces supply-chain, download and integration surface, but makes shader/lifecycle maintenance our responsibility. It does not provide photogrammetry, physically based hydraulic modelling, cascaded shadows, ambient occlusion, geoid conversion or individually verified tree positions. Mercator display is regional and conformal, with per-position metre scaling; it is not a global ellipsoidal digital twin. Geodesic measurements and UTM analysis stay in the existing backend.

## Feasibility and verification

See [the territorial delivery and verification report](../PIURA_DIGITAL_TWIN.md). A small real Andean package was generated by the same production tile function: three tiles, 442,164 bytes, with a separate 128 × 128 source audit reporting full valid coverage and a 339.14–3384.17 m elevation range. That audit does not certify every Piura cell or cadastral accuracy.

Property tests cover geographic/metric round trips, uniform local metre scale, polygon holes, exclusion envelopes, stable world positions while panning, homogeneous matrix evaluation, solar bounds, allocation/cleanup and bounded tile plans. Bounded mutation fuzzing targets malformed GeoJSON without external traffic. Browser checks separate real terrain from explicitly labelled renderer fixtures. No vendor benchmark is presented as a local result.

## Adoption and rollback

1. Keep the default map/AI/AR APIs and existing pending work.
2. Replace forced zoom and height interpolation; expose the opt-in territorial controls.
3. Enable bounded detail only after terrain is loaded; inspect source elevations on explicit clicks with cancellation/timeouts.
4. Prepare only bounded offline areas, with hashes, CRS, source terms and missingness in manifests.
5. Validate software, real geography, visible pixels and hardware independently.

Rollback consists of removing the lazy integration and new modules, reverting the small map changes, and removing the point endpoint. The generated packages are ignored local artifacts. No persistent schema migration or new external service is required. Preserve unrelated uncommitted work and the repository's one-path-per-commit policy; this task makes no commits.

## Review triggers

Revisit if target devices fail the graphics/performance budget, new licensed LiDAR/photogrammetry/3D Tiles become available, authoritative water/forest/structure data contradict the present mapping, the pinned MapLibre API changes, a security advisory affects the stack, or the required spatial extent becomes global. Recheck per-layer terms and acquisition/version metadata before distributing a regional package.
